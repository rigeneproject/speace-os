"""ARC-AGI Adapter — loads ARC tasks, evaluates predictions, produces reports.

Expects ARC JSON format:
{
  "task_id": {
    "train": [{"input": [[...]], "output": [[...]]}, ...],
    "test":  [{"input": [[...]], "output": [[...]]}, ...]
  }
}
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.cognition.few_shot_program_induction_engine import (
    FewShotProgramInductionEngine,
    ProgramCandidate,
)
from speace_core.cellular_brain.cognition.program_schema_library import (
    ProgramSchemaLibrary,
    compute_task_signature,
)
from speace_core.cellular_brain.cognition.program_models import (
    TransformationProgram,
)
from speace_core.benchmark.failure_memory import FailureMemoryStore, FailureRecord

logger = logging.getLogger(__name__)


class ARCTask(BaseModel):
    task_id: str
    train: List[Dict[str, Any]] = Field(default_factory=list)
    test: List[Dict[str, Any]] = Field(default_factory=list)


class ARCPrediction(BaseModel):
    task_id: str
    test_index: int
    predicted_outputs: List[List[List[int]]] = Field(default_factory=list)
    program_explanation: str = ""


class ARCEvaluationResult(BaseModel):
    task_id: str
    test_index: int
    correct: bool = False
    match_score: float = 0.0
    prediction: Optional[ARCPrediction] = None
    elapsed_ms: float = 0.0
    candidates_explored: int = 0


class ARCAGIAdapter:
    """Adapter for ARC-AGI benchmark evaluation."""

    def __init__(
        self,
        engine: FewShotProgramInductionEngine,
        data_dir: str = "data/arc_agi",
        evaluation_mode: bool = False,
    ) -> None:
        self.engine = engine
        self.data_dir = Path(data_dir)
        self.evaluation_mode = evaluation_mode
        self.failure_memory = FailureMemoryStore()
        self.schema_library = ProgramSchemaLibrary(data_dir="data/schema_library")
        self._schema_store_threshold: float = 0.6

    # ------------------------------------------------------------------ #
    # Loading
    # ------------------------------------------------------------------ #

    def load_tasks(self, split: str = "training", limit: Optional[int] = None) -> List[ARCTask]:
        path = self.data_dir / f"{split}.json"
        if not path.exists():
            logger.warning("ARC data file not found: %s", path)
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        tasks: List[ARCTask] = []
        for task_id, payload in raw.items():
            tasks.append(
                ARCTask(
                    task_id=task_id,
                    train=[{"input": p["input"], "output": p["output"]} for p in payload.get("train", [])],
                    test=[{"input": p["input"], "output": p.get("output")} for p in payload.get("test", [])],
                )
            )
            if limit and len(tasks) >= limit:
                break
        return tasks

    # ------------------------------------------------------------------ #
    # Evaluation
    # ------------------------------------------------------------------ #

    def evaluate_task(self, task: ARCTask) -> List[ARCEvaluationResult]:
        results: List[ARCEvaluationResult] = []
        start = time.perf_counter()

        # Phase 0: Schema Library quick-suggest for zero-shot generalization
        schema_programs = self.schema_library.suggest_programs(task.train, top_k=3)
        if schema_programs:
            candidates: List[ProgramCandidate] = []
            for sp in schema_programs:
                matches = sum(1 for pair in task.train if self._program_matches(sp, pair))
                candidates.append(ProgramCandidate(program=sp, train_matches=matches, confidence=0.5))
            candidates.sort(key=lambda c: -c.train_matches)
        else:
            candidates = self.engine.induce(task.train)

        # If induced candidates are empty, fall back to schema suggestions
        if not candidates and schema_programs:
            candidates = [ProgramCandidate(program=sp, train_matches=0, confidence=0.3) for sp in schema_programs[:2]]

        elapsed = (time.perf_counter() - start) * 1000.0
        self.engine.set_candidates(candidates)
        for idx, test_pair in enumerate(task.test):
            test_input = test_pair["input"]
            test_output = test_pair.get("output")
            predictions = self.engine.predict(test_input, top_k=2)
            correct = False
            match_score = 0.0
            explanation = ""
            if candidates:
                explanation = self.engine.explain(candidates[0])
            if test_output is not None:
                for pred in predictions:
                    if self._grid_eq(pred, test_output):
                        correct = True
                        match_score = 1.0
                        break
                if not correct and predictions:
                    match_score = self._pixel_accuracy(predictions[0], test_output)
            result = ARCEvaluationResult(
                task_id=task.task_id,
                test_index=idx,
                correct=correct,
                match_score=match_score,
                prediction=ARCPrediction(
                    task_id=task.task_id,
                    test_index=idx,
                    predicted_outputs=predictions,
                    program_explanation=explanation,
                ),
                elapsed_ms=elapsed,
                candidates_explored=len(candidates),
            )
            # Auto-record failures to permanent Failure Memory
            if not correct and test_output is not None:
                inp_shape = self._shape_str(test_input)
                out_shape = self._shape_str(test_output)
                record = self.failure_memory.classify_failure(
                    task_id=task.task_id,
                    candidates=len(candidates),
                    match_score=match_score,
                    train_count=len(task.train),
                    test_count=len(task.test),
                    input_shape=inp_shape,
                    output_shape=out_shape,
                    best_explanation=explanation,
                )
                self.failure_memory.record_failure(record)
            # Store successful programs in schema library for future reuse
            if correct and candidates:
                best = candidates[0]
                pixel_score = self._compute_program_pixel_score(best.program, task.train)
                if pixel_score >= self._schema_store_threshold:
                    self.schema_library.add_from_program(best.program, task.train, pixel_score)
            results.append(result)
        return results

    def run_benchmark(
        self, tasks: Optional[List[ARCTask]] = None, limit: Optional[int] = None
    ) -> Dict[str, Any]:
        if tasks is None:
            tasks = self.load_tasks(split="training", limit=limit)
        total = len(tasks)
        correct = 0
        attempted = 0
        per_task: List[Dict[str, Any]] = []
        for task in tasks:
            results = self.evaluate_task(task)
            task_correct = all(r.correct for r in results)
            if results:
                attempted += 1
            if task_correct:
                correct += 1
            per_task.append(
                {
                    "task_id": task.task_id,
                    "correct": task_correct,
                    "results": [r.model_dump() for r in results],
                }
            )
        top1 = correct / attempted if attempted > 0 else 0.0
        failure_summary = self.failure_memory.get_summary()
        report = {
            "total_tasks": total,
            "attempted": attempted,
            "correct": correct,
            "top1_accuracy": round(top1, 4),
            "per_task": per_task,
            "failure_memory": failure_summary,
        }
        return report

    def report(self, benchmark_result: Dict[str, Any]) -> str:
        lines = [
            "# ARC-AGI Benchmark Report",
            f"- Tasks evaluated: {benchmark_result['attempted']}/{benchmark_result['total_tasks']}",
            f"- Correct (exact match): {benchmark_result['correct']}",
            f"- Top-1 Accuracy: {benchmark_result['top1_accuracy']:.2%}",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _shape_str(grid: List[List[int]]) -> str:
        if not grid:
            return "0x0"
        return f"{len(grid)}x{len(grid[0])}"

    @staticmethod
    def _grid_eq(a: List[List[int]], b: List[List[int]]) -> bool:
        if len(a) != len(b):
            return False
        return all(len(row_a) == len(row_b) and row_a == row_b for row_a, row_b in zip(a, b))

    @staticmethod
    def _pixel_accuracy(pred: List[List[int]], target: List[List[int]]) -> float:
        if len(pred) != len(target):
            return 0.0
        total = 0
        correct = 0
        for row_p, row_t in zip(pred, target):
            if len(row_p) != len(row_t):
                return 0.0
            total += len(row_p)
            correct += sum(1 for p, t in zip(row_p, row_t) if p == t)
        return correct / total if total > 0 else 0.0

    @staticmethod
    def _program_matches(program: TransformationProgram, pair: Dict[str, Any]) -> bool:
        result = program.apply(pair["input"])
        if result is None:
            return False
        expected = pair["output"]
        if len(result) != len(expected):
            return False
        return all(len(r) == len(e) and r == e for r, e in zip(result, expected))

    @staticmethod
    def _compute_program_pixel_score(program: TransformationProgram, pairs: List[Dict[str, Any]]) -> float:
        if not pairs:
            return 0.0
        total = 0.0
        for pair in pairs:
            result = program.apply(pair["input"])
            if result is None:
                continue
            expected = pair["output"]
            if len(result) != len(expected):
                continue
            correct = 0
            total_px = 0
            for r_row, e_row in zip(result, expected):
                if len(r_row) != len(e_row):
                    continue
                total_px += len(r_row)
                correct += sum(1 for r, e in zip(r_row, e_row) if r == e)
            if total_px > 0:
                total += correct / total_px
        return total / len(pairs) if pairs else 0.0
