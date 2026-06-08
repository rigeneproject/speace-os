import json
import pytest

from speace_core.benchmark.arc_agi_adapter import ARCAGIAdapter
from speace_core.benchmark.arc_agi_curriculum_engine import ARCAGICurriculumEngine
from speace_core.cellular_brain.cognition.few_shot_program_induction_engine import (
    FewShotProgramInductionEngine,
)
from speace_core.cellular_brain.cognition.spatial_symbolic_reasoning_layer import (
    SpatialSymbolicReasoningLayer,
)


class TestARCAGICurriculumEngine:
    def test_difficulty_score_range(self):
        adapter = ARCAGIAdapter(
            engine=FewShotProgramInductionEngine(spatial_layer=SpatialSymbolicReasoningLayer()),
            data_dir="data/arc_agi",
        )
        tasks = adapter.load_tasks("training", limit=10)
        engine = ARCAGICurriculumEngine(adapter)
        for t in tasks:
            d = engine.difficulty_score(t)
            assert 0.0 <= d <= 1.0

    def test_build_curriculum_splits_tasks(self):
        adapter = ARCAGIAdapter(
            engine=FewShotProgramInductionEngine(spatial_layer=SpatialSymbolicReasoningLayer()),
            data_dir="data/arc_agi",
        )
        tasks = adapter.load_tasks("training", limit=20)
        engine = ARCAGICurriculumEngine(adapter)
        curriculum = engine.build_arc_curriculum(tasks)
        assert len(curriculum) > 0
        total_in_stages = sum(len(s.tasks) for s in curriculum)
        assert total_in_stages == len(tasks)
        # Difficulty should increase across stages
        for i in range(1, len(curriculum)):
            assert curriculum[i].difficulty_min >= curriculum[i - 1].difficulty_min

    def test_train_curriculum_runs(self):
        adapter = ARCAGIAdapter(
            engine=FewShotProgramInductionEngine(spatial_layer=SpatialSymbolicReasoningLayer()),
            data_dir="data/arc_agi",
            evaluation_mode=True,
        )
        tasks = adapter.load_tasks("training", limit=5)
        engine = ARCAGICurriculumEngine(adapter)
        curriculum = engine.build_arc_curriculum(tasks, stage_names=["easy", "hard"])
        result = engine.train_curriculum(curriculum, eval_interval=2)
        assert len(result.stage_results) > 0
        assert result.overall_tasks_attempted == len(tasks)
