"""ARC-AGI Curriculum Engine — automatic curriculum learning for ARC tasks.

Orders tasks by estimated difficulty and trains the induction engine
progressively through staged difficulty bands.
"""

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from speace_core.benchmark.arc_agi_adapter import ARCAGIAdapter, ARCTask
from speace_core.cellular_brain.cognition.few_shot_program_induction_engine import (
    FewShotProgramInductionEngine,
)


class CurriculumStage(BaseModel):
    name: str
    difficulty_min: float = 0.0
    difficulty_max: float = 1.0
    tasks: List[ARCTask] = Field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)


class CurriculumLearningResult(BaseModel):
    stage_results: List[Dict[str, Any]] = Field(default_factory=list)
    overall_top1: float = 0.0
    overall_tasks_attempted: int = 0
    overall_tasks_correct: int = 0

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ARCAGICurriculumEngine:
    """Builds and executes a difficulty-based curriculum over ARC-AGI tasks."""

    def __init__(self, adapter: ARCAGIAdapter) -> None:
        self.adapter = adapter

    @staticmethod
    def difficulty_score(task: ARCTask) -> float:
        """Estimate task difficulty heuristically.

        Factors:
        - grid size (larger = harder)
        - number of colors used (more = harder)
        - number of train examples (more = easier, but also more constraints)
        - output variance (higher = harder)
        """
        train = task.train
        if not train:
            return 0.5

        all_inputs = [pair["input"] for pair in train]
        all_outputs = [pair["output"] for pair in train]

        max_h = max(len(g) for g in all_inputs + all_outputs)
        max_w = max(len(g[0]) for g in all_inputs + all_outputs if g)
        grid_size_score = min(1.0, (max_h * max_w) / 400.0)

        all_colors: set = set()
        for g in all_inputs + all_outputs:
            for row in g:
                all_colors.update(row)
        color_score = min(1.0, len(all_colors) / 10.0)

        n_examples = len(train)
        example_score = max(0.0, 1.0 - (n_examples - 1) * 0.15)

        # output variance: how different are outputs from inputs?
        diffs = []
        for inp, out in zip(all_inputs, all_outputs):
            if len(inp) == len(out) and len(inp[0]) == len(out[0]):
                total = len(inp) * len(inp[0])
                same = sum(
                    1 for y in range(len(inp)) for x in range(len(inp[0])) if inp[y][x] == out[y][x]
                )
                diffs.append(1.0 - same / total)
        variance_score = sum(diffs) / len(diffs) if diffs else 0.5

        # Weighted aggregate
        return (
            0.30 * grid_size_score
            + 0.25 * color_score
            + 0.15 * example_score
            + 0.30 * variance_score
        )

    def build_arc_curriculum(
        self,
        tasks: List[ARCTask],
        stage_names: Optional[List[str]] = None,
    ) -> List[CurriculumStage]:
        """Sort tasks by difficulty and split into stages."""
        scored = [(self.difficulty_score(t), t) for t in tasks]
        scored.sort(key=lambda x: x[0])

        if stage_names is None:
            stage_names = [
                "visual_recognition",
                "relational",
                "compositional",
                "parametric",
                "abstract",
            ]

        n = len(scored)
        if n == 0:
            return []
        per_stage = max(1, n // len(stage_names))
        stages: List[CurriculumStage] = []
        for i, name in enumerate(stage_names):
            start = i * per_stage
            end = start + per_stage if i < len(stage_names) - 1 else n
            slice_tasks = [t for _, t in scored[start:end]]
            min_d = scored[start][0] if slice_tasks else 0.0
            max_d = scored[end - 1][0] if end <= n and slice_tasks else 1.0
            stages.append(
                CurriculumStage(
                    name=name,
                    difficulty_min=round(min_d, 4),
                    difficulty_max=round(max_d, 4),
                    tasks=slice_tasks,
                )
            )
        return stages

    def train_curriculum(
        self,
        curriculum: List[CurriculumStage],
        eval_interval: int = 10,
    ) -> CurriculumLearningResult:
        """Progressively train/evaluate through curriculum stages."""
        result = CurriculumLearningResult()
        all_evaluated: List[ARCTask] = []

        for stage in curriculum:
            stage_correct = 0
            stage_attempted = 0
            for task in stage.tasks:
                task_results = self.adapter.evaluate_task(task)
                stage_attempted += 1
                if all(r.correct for r in task_results):
                    stage_correct += 1
                all_evaluated.append(task)
                if eval_interval > 0 and len(all_evaluated) % eval_interval == 0:
                    interim = self.adapter.run_benchmark(tasks=all_evaluated)
                    result.stage_results.append(
                        {
                            "stage": stage.name,
                            "tasks_so_far": len(all_evaluated),
                            "interim_top1": interim["top1_accuracy"],
                        }
                    )
            stage_report = self.adapter.run_benchmark(tasks=stage.tasks)
            result.stage_results.append(
                {
                    "stage": stage.name,
                    "tasks_in_stage": len(stage.tasks),
                    "stage_top1": stage_report["top1_accuracy"],
                    "stage_correct": stage_correct,
                    "stage_attempted": stage_attempted,
                }
            )

        final = self.adapter.run_benchmark(tasks=all_evaluated)
        result.overall_top1 = final["top1_accuracy"]
        result.overall_tasks_attempted = final["attempted"]
        result.overall_tasks_correct = final["correct"]
        return result
