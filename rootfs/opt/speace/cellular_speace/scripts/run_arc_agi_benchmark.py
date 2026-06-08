#!/usr/bin/env python
"""ARC-AGI benchmark runner for SPEACE.

Usage:
    python scripts/run_arc_agi_benchmark.py --split training --limit 100
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from speace_core.cellular_brain.cognition.few_shot_program_induction_engine import (
    FewShotProgramInductionEngine,
)
from speace_core.cellular_brain.cognition.spatial_symbolic_reasoning_layer import (
    SpatialSymbolicReasoningLayer,
)
from speace_core.cellular_brain.cognition.meta_learning_program_composer import (
    MetaLearningProgramComposer,
)
from speace_core.cellular_brain.cognition.neural_symbolic_primitive_learner import (
    NSPLEngine,
)
from speace_core.cellular_brain.cognition.llm_augmented_program_synthesis import (
    LLMAugmentedProgramSynthesis,
)
from speace_core.cellular_brain.cognition.program_models import (
    _PRIMITIVE_REGISTRY,
)
from speace_core.cellular_brain.language.linguistic_cortical_bridge import (
    LinguisticCorticalBridge,
)
from speace_core.benchmark.arc_agi_adapter import ARCAGIAdapter
from speace_core.dna.parser import load_genome
from speace_core.orchestrator import CellularBrainOrchestrator


def _build_synthetic_nspl_tasks(registry):
    """Generate tiny synthetic tasks so NSPL has something to train on."""
    import random
    tasks = []
    # Pick a few simple primitives that work on 3x3 patches
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ARC-AGI benchmark on SPEACE")
    parser.add_argument("--split", default="training", help="ARC split to evaluate")
    parser.add_argument("--limit", type=int, default=None, help="Max tasks to evaluate")
    parser.add_argument("--genome", default=None, help="Path to genome YAML")
    parser.add_argument("--data-dir", default="data/arc_agi", help="Path to ARC JSON files")
    parser.add_argument("--output-dir", default="reports/arc_agi", help="Report output directory")
    parser.add_argument("--evaluation-mode", action="store_true", help="Enable evaluation mode (bypass human gates)")
    args = parser.parse_args()

    genome_path = args.genome or Path(__file__).resolve().parent.parent / "speace_core" / "dna" / "genome" / "default_genome.yaml"
    genome = load_genome(genome_path)

    # Build enriched engine with AGI-phase modules
    spatial = SpatialSymbolicReasoningLayer()
    nspl = NSPLEngine(_PRIMITIVE_REGISTRY)
    # Quick synthetic NSPL warm-up (not required for benchmark but primes the model)
    synth_tasks = _build_synthetic_nspl_tasks(_PRIMITIVE_REGISTRY)
    nspl_data = nspl.build_training_data(synth_tasks, max_pairs=50)
    nspl.train(nspl_data, epochs=3, lr=0.05)

    mlpc = MetaLearningProgramComposer()
    bridge = LinguisticCorticalBridge(mock_mode=True)
    llm_aps = LLMAugmentedProgramSynthesis(
        bridge=bridge, primitive_registry=_PRIMITIVE_REGISTRY,
        meta_composer=mlpc, evaluation_mode=args.evaluation_mode,
    )

    engine = FewShotProgramInductionEngine(
        spatial_layer=spatial,
        nspl_engine=nspl,
        meta_learning_composer=mlpc,
        llm_aps=llm_aps,
        max_program_depth=3,
        max_candidates=150,
    )

    orchestrator = CellularBrainOrchestrator.build_mvp(genome)
    orchestrator.arc_agi_benchmark_enabled = True
    orchestrator.evaluation_mode = args.evaluation_mode
    # Re-init adapter with updated flags
    from speace_core.benchmark.arc_agi_adapter import ARCAGIAdapter
    orchestrator._arc_agi_adapter = ARCAGIAdapter(
        engine=engine,
        data_dir=args.data_dir,
        evaluation_mode=args.evaluation_mode,
    )

    async def _run() -> None:
        report = await orchestrator.run_arc_agi_benchmark(
            split=args.split, limit=args.limit
        )
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        json_path = output_dir / f"arc_agi_report_{ts}.json"
        json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        md_path = output_dir / f"arc_agi_report_{ts}.md"
        adapter = orchestrator.get_arc_agi_adapter()
        if adapter is not None:
            md_path.write_text(adapter.report(report), encoding="utf-8")
        print(f"JSON report written to: {json_path}")
        print(f"Markdown report written to: {md_path}")
        print(f"Top-1 Accuracy: {report.get('top1_accuracy', 0.0):.2%}")
        print(f"Correct / Attempted: {report.get('correct', 0)} / {report.get('attempted', 0)}")

    asyncio.run(_run())
    return 0


if __name__ == "__main__":
    sys.exit(main())
