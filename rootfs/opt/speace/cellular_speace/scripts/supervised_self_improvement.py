#!/usr/bin/env python
"""Supervised Self-Improvement Loop for SPEACE.

Iterative curriculum-learning cycle over ARC-AGI tasks:
  1. Load a batch of tasks ordered by difficulty.
  2. Benchmark the current engine on the batch.
  3. Extract NSPL training patches from the batch.
  4. Train NSPL incrementally.
  5. Run MLPC guided search to discover successful programs and update transitions.
  6. Re-benchmark and record improvement delta.
  7. Save checkpoint (NSPL weights + MLPC transition model).
  8. Generate JSON/Markdown report.

Governance:
- No autonomous runtime actions are taken.
- The script only modifies the isolated program-induction engine.
- A human may review the report before the next batch unless --auto-advance.

Usage:
    python scripts/supervised_self_improvement.py --batches 8 --batch-size 50 --auto-advance
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from speace_core.benchmark.arc_agi_adapter import ARCAGIAdapter
from speace_core.benchmark.arc_agi_curriculum_engine import ARCAGICurriculumEngine
from speace_core.cellular_brain.cognition.few_shot_program_induction_engine import (
    FewShotProgramInductionEngine,
)
from speace_core.cellular_brain.cognition.meta_learning_program_composer import (
    MetaLearningProgramComposer,
)
from speace_core.cellular_brain.cognition.neural_symbolic_primitive_learner import (
    NSPLEngine,
)
from speace_core.cellular_brain.cognition.program_models import _PRIMITIVE_REGISTRY
from speace_core.cellular_brain.cognition.spatial_symbolic_reasoning_layer import (
    SpatialSymbolicReasoningLayer,
)


def _build_synthetic_nspl_tasks(registry: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Tiny synthetic warm-up tasks so NSPL is not completely cold."""
    import random
    tasks = []
    simple = [n for n in registry if n in (
        "identity", "rotate_90", "flip_horizontal", "flip_vertical",
        "fill_holes", "outline", "invert_colors", "remove_noise",
    )]
    for name in simple:
        fn = registry.get(name)
        if fn is None:
            continue
        for _ in range(5):
            grid = [[random.randint(0, 3) for _ in range(3)] for _ in range(3)]
            try:
                out = fn(grid, {})
            except Exception:
                continue
            if out is None:
                continue
            tasks.append({"train": [{"input": grid, "output": out}]})
    return tasks


def _ensure_dirs() -> None:
    for d in ("data/self_improvement/checkpoints", "reports/self_improvement"):
        Path(d).mkdir(parents=True, exist_ok=True)


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def save_checkpoint(
    nspl: NSPLEngine,
    mlpc: MetaLearningProgramComposer,
    batch_idx: int,
    ckpt_dir: str = "data/self_improvement/checkpoints",
) -> None:
    base = Path(ckpt_dir)
    base.mkdir(parents=True, exist_ok=True)
    nspl.save(str(base / f"nspl_batch_{batch_idx}.npz"))
    mlpc.save(str(base / f"mlpc_batch_{batch_idx}.json"))


def load_latest_checkpoint(
    nspl: NSPLEngine,
    mlpc: MetaLearningProgramComposer,
    ckpt_dir: str = "data/self_improvement/checkpoints",
) -> int:
    """Return the latest batch index restored, or -1 if none found."""
    base = Path(ckpt_dir)
    if not base.exists():
        return -1
    nspl_files = sorted(base.glob("nspl_batch_*.npz"), key=lambda p: int(p.stem.split("_")[-1]))
    mlpc_files = sorted(base.glob("mlpc_batch_*.json"), key=lambda p: int(p.stem.split("_")[-1]))
    if not nspl_files or not mlpc_files:
        return -1
    latest_nspl = nspl_files[-1]
    latest_mlpc = mlpc_files[-1]
    idx_nspl = int(latest_nspl.stem.split("_")[-1])
    idx_mlpc = int(latest_mlpc.stem.split("_")[-1])
    if idx_nspl != idx_mlpc:
        return -1
    nspl.load(str(latest_nspl))
    mlpc.load(str(latest_mlpc))
    return idx_nspl


def run_batch_benchmark(
    adapter: ARCAGIAdapter,
    tasks: List[Any],
) -> Dict[str, Any]:
    report = adapter.run_benchmark(tasks=tasks)
    return report


def extract_nspl_dataset(
    nspl: NSPLEngine,
    tasks: List[Any],
    max_pairs: int = 200,
) -> List[Any]:
    """Convert a batch of ARC tasks into NSPL (patch, label) tuples."""
    raw_tasks = []
    for t in tasks:
        raw_tasks.append(
            {"train": [{"input": p["input"], "output": p["output"]} for p in t.train]}
        )
    return nspl.build_training_data(raw_tasks, max_pairs=max_pairs)


def update_mlpc_from_batch(
    mlpc: MetaLearningProgramComposer,
    engine: FewShotProgramInductionEngine,
    tasks: List[Any],
    max_depth: int = 2,
    max_candidates: int = 50,
) -> int:
    """Run guided search on each task; for successes, update MLPC. Return success count."""
    successes = 0
    for t in tasks:
        train_pairs = [{"input": p["input"], "output": p["output"]} for p in t.train]
        primitives = engine._generate_primitive_hypotheses(train_pairs)
        cands = mlpc.guided_search(
            train_pairs,
            primitives,
            engine,
            max_depth=max_depth,
            max_candidates=max_candidates,
        )
        if cands and cands[0].train_matches == len(train_pairs):
            successes += 1
    return successes


def build_engine(
    nspl: Optional[NSPLEngine] = None,
    mlpc: Optional[MetaLearningProgramComposer] = None,
) -> FewShotProgramInductionEngine:
    spatial = SpatialSymbolicReasoningLayer()
    if nspl is None:
        nspl = NSPLEngine(_PRIMITIVE_REGISTRY)
        synth = _build_synthetic_nspl_tasks(_PRIMITIVE_REGISTRY)
        data = nspl.build_training_data(synth, max_pairs=50)
        nspl.train(data, epochs=3, lr=0.05)
    if mlpc is None:
        mlpc = MetaLearningProgramComposer()
    return FewShotProgramInductionEngine(
        spatial_layer=spatial,
        nspl_engine=nspl,
        meta_learning_composer=mlpc,
        max_program_depth=3,
        max_candidates=120,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="SPEACE Supervised Self-Improvement Loop")
    parser.add_argument("--data-dir", default="data/arc_agi", help="Path to ARC JSON files")
    parser.add_argument("--batch-size", type=int, default=50, help="Tasks per batch")
    parser.add_argument("--batches", type=int, default=8, help="Number of batches (max 400/batch-size)")
    parser.add_argument("--nspl-epochs", type=int, default=5, help="NSPL training epochs per batch")
    parser.add_argument("--nspl-lr", type=float, default=0.05, help="NSPL learning rate")
    parser.add_argument("--auto-advance", action="store_true", help="Do not pause for human Enter between batches")
    parser.add_argument("--resume", action="store_true", help="Resume from latest checkpoint")
    parser.add_argument("--output-dir", default="reports/self_improvement", help="Report output directory")
    parser.add_argument("--ckpt-dir", default="data/self_improvement/checkpoints", help="Checkpoint directory")
    args = parser.parse_args()

    _ensure_dirs()

    # Initialize or resume engine
    nspl = NSPLEngine(_PRIMITIVE_REGISTRY)
    mlpc = MetaLearningProgramComposer()
    start_batch = -1
    if args.resume:
        start_batch = load_latest_checkpoint(nspl, mlpc, ckpt_dir=args.ckpt_dir)
        if start_batch >= 0:
            print(f"[RESUME] Restored checkpoint from batch {start_batch}")
        else:
            print("[RESUME] No checkpoint found; starting from scratch")

    engine = build_engine(nspl=nspl, mlpc=mlpc)
    adapter = ARCAGIAdapter(engine=engine, data_dir=args.data_dir, evaluation_mode=True)

    # Load tasks and build curriculum
    all_tasks = adapter.load_tasks("training")
    if not all_tasks:
        print("[ERROR] No ARC training tasks found.")
        return 1

    curriculum_engine = ARCAGICurriculumEngine(adapter)
    curriculum = curriculum_engine.build_arc_curriculum(all_tasks)

    # Flatten curriculum stages into ordered list
    ordered_tasks: List[Any] = []
    for stage in curriculum:
        ordered_tasks.extend(stage.tasks)

    total_batches = min(args.batches, (len(ordered_tasks) + args.batch_size - 1) // args.batch_size)

    batch_reports: List[Dict[str, Any]] = []

    for b in range(total_batches):
        if b <= start_batch:
            print(f"[SKIP] Batch {b + 1}/{total_batches} already processed in checkpoint")
            continue

        offset = b * args.batch_size
        batch_tasks = ordered_tasks[offset : offset + args.batch_size]
        print(f"\n{'='*60}")
        print(f"[BATCH {b + 1}/{total_batches}] Tasks {offset + 1}-{offset + len(batch_tasks)}")
        print(f"{'='*60}")

        # 1. Baseline benchmark
        t0 = time.perf_counter()
        baseline_report = run_batch_benchmark(adapter, batch_tasks)
        baseline_acc = baseline_report.get("top1_accuracy", 0.0)
        print(f"[BASELINE] Top-1 accuracy: {baseline_acc:.2%} ({baseline_report['correct']}/{baseline_report['attempted']})")

        # 2. Extract NSPL training data from batch
        nspl_dataset = extract_nspl_dataset(engine.nspl_engine, batch_tasks, max_pairs=300)
        print(f"[NSPL] Extracted {len(nspl_dataset)} patch-label pairs")

        # 3. Train NSPL
        if nspl_dataset:
            engine.nspl_engine.train(nspl_dataset, epochs=args.nspl_epochs, lr=args.nspl_lr)
            print(f"[NSPL] Trained for {args.nspl_epochs} epochs")

        # 4. Update MLPC via guided search successes
        mlpc_successes = update_mlpc_from_batch(
            engine.meta_learning_composer, engine, batch_tasks, max_depth=2, max_candidates=60
        )
        print(f"[MLPC] Recorded {mlpc_successes} successful programs")

        # 5. Post-training benchmark
        post_report = run_batch_benchmark(adapter, batch_tasks)
        post_acc = post_report.get("top1_accuracy", 0.0)
        delta = post_acc - baseline_acc
        print(f"[POST]   Top-1 accuracy: {post_acc:.2%} ({post_report['correct']}/{post_report['attempted']})")
        print(f"[DELTA]  Improvement: {delta:+.2%}")

        # 6. Save checkpoint
        save_checkpoint(engine.nspl_engine, engine.meta_learning_composer, b, ckpt_dir=args.ckpt_dir)
        print(f"[CHECKPOINT] Saved to {args.ckpt_dir}/batch_{b}")

        # 7. Record batch report
        batch_report = {
            "batch_index": b,
            "task_range": [offset + 1, offset + len(batch_tasks)],
            "baseline": {
                "accuracy": baseline_acc,
                "correct": baseline_report["correct"],
                "attempted": baseline_report["attempted"],
            },
            "post": {
                "accuracy": post_acc,
                "correct": post_report["correct"],
                "attempted": post_report["attempted"],
            },
            "delta": delta,
            "nspl_pairs": len(nspl_dataset),
            "mlpc_successes": mlpc_successes,
            "elapsed_sec": round(time.perf_counter() - t0, 2),
        }
        batch_reports.append(batch_report)

        # 8. Human pause unless auto-advance
        if not args.auto_advance:
            input("[PAUSE] Press Enter to proceed to next batch (or Ctrl+C to stop)...")

    # Final report
    final = {
        "run_timestamp": _timestamp(),
        "total_batches": total_batches,
        "batch_size": args.batch_size,
        "batch_reports": batch_reports,
        "summary": {
            "total_correct_baseline": sum(r["baseline"]["correct"] for r in batch_reports),
            "total_correct_post": sum(r["post"]["correct"] for r in batch_reports),
            "total_attempted": sum(r["post"]["attempted"] for r in batch_reports),
            "overall_delta": round(
                sum(r["delta"] for r in batch_reports) / len(batch_reports), 4
            ) if batch_reports else 0.0,
        },
    }
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = _timestamp()
    json_path = out_dir / f"self_improvement_report_{ts}.json"
    json_path.write_text(json.dumps(final, indent=2), encoding="utf-8")
    md_path = out_dir / f"self_improvement_report_{ts}.md"
    md_path.write_text(_render_markdown(final), encoding="utf-8")
    print(f"\n[FINAL] JSON report: {json_path}")
    print(f"[FINAL] Markdown report: {md_path}")
    print(f"[FINAL] Overall delta: {final['summary']['overall_delta']:+.2%}")
    return 0


def _render_markdown(report: Dict[str, Any]) -> str:
    lines = [
        "# SPEACE Supervised Self-Improvement Report",
        f"- Run timestamp: {report['run_timestamp']}",
        f"- Total batches: {report['total_batches']}",
        "",
        "## Summary",
        f"- Total correct (baseline): {report['summary']['total_correct_baseline']}",
        f"- Total correct (post):     {report['summary']['total_correct_post']}",
        f"- Total attempted:          {report['summary']['total_attempted']}",
        f"- Overall delta per batch:  {report['summary']['overall_delta']:+.2%}",
        "",
        "## Batch Details",
        "| Batch | Tasks | Baseline | Post | Delta | NSPL Pairs | MLPC Successes | Elapsed (s) |",
        "|-------|-------|----------|------|-------|------------|----------------|-------------|",
    ]
    for r in report["batch_reports"]:
        lines.append(
            f"| {r['batch_index'] + 1} | {r['task_range'][0]}-{r['task_range'][1]} | "
            f"{r['baseline']['correct']}/{r['baseline']['attempted']} ({r['baseline']['accuracy']:.1%}) | "
            f"{r['post']['correct']}/{r['post']['attempted']} ({r['post']['accuracy']:.1%}) | "
            f"{r['delta']:+.1%} | {r['nspl_pairs']} | {r['mlpc_successes']} | {r['elapsed_sec']} |"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
