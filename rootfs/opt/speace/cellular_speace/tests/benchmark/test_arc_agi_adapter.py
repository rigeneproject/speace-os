"""Tests for ARC-AGI adapter, spatial reasoning, and program induction."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from speace_core.benchmark.arc_agi_adapter import ARCAGIAdapter, ARCTask
from speace_core.cellular_brain.cognition.few_shot_program_induction_engine import (
    FewShotProgramInductionEngine,
    GridTransformation,
    TransformationProgram,
)
from speace_core.cellular_brain.cognition.spatial_symbolic_reasoning_layer import (
    GridScene,
    SpatialSymbolicReasoningLayer,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture
def spatial_layer():
    return SpatialSymbolicReasoningLayer()


@pytest.fixture
def induction_engine(spatial_layer):
    return FewShotProgramInductionEngine(spatial_layer=spatial_layer)


@pytest.fixture
def tmp_arc_data(tmp_path: Path):
    data = {
        "rotate_90": {
            "train": [
                {
                    "input": [[1, 0, 0], [1, 0, 0], [1, 0, 0]],
                    "output": [[1, 1, 1], [0, 0, 0], [0, 0, 0]],
                },
                {
                    "input": [[0, 2], [0, 2]],
                    "output": [[0, 0], [2, 2]],
                },
            ],
            "test": [{"input": [[3, 0], [3, 0]], "output": [[3, 3], [0, 0]]}],
        },
        "translate_right": {
            "train": [
                {
                    "input": [[1, 0, 0], [0, 0, 0], [0, 0, 0]],
                    "output": [[0, 1, 0], [0, 0, 0], [0, 0, 0]],
                },
                {
                    "input": [[0, 0, 0], [2, 0, 0], [0, 0, 0]],
                    "output": [[0, 0, 0], [0, 2, 0], [0, 0, 0]],
                },
            ],
            "test": [{"input": [[0, 0, 0], [3, 0, 0], [0, 0, 0]], "output": [[0, 0, 0], [0, 3, 0], [0, 0, 0]]}],
        },
        "color_map": {
            "train": [
                {
                    "input": [[1, 1], [2, 2]],
                    "output": [[3, 3], [4, 4]],
                },
                {
                    "input": [[1, 2], [2, 1]],
                    "output": [[3, 4], [4, 3]],
                },
            ],
            "test": [{"input": [[2, 1], [1, 2]], "output": [[4, 3], [3, 4]]}],
        },
        "compose_rotate_flip": {
            "train": [
                {
                    "input": [[1, 0], [0, 0]],
                    "output": [[0, 0], [0, 1]],
                },
                {
                    "input": [[2, 0], [0, 0]],
                    "output": [[0, 0], [0, 2]],
                },
            ],
            "test": [{"input": [[3, 0], [0, 0]], "output": [[0, 0], [0, 3]]}],
        },
    }
    arc_dir = tmp_path / "arc_agi"
    arc_dir.mkdir()
    path = arc_dir / "training.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(arc_dir)


# --------------------------------------------------------------------------- #
# Spatial Symbolic Reasoning Layer
# --------------------------------------------------------------------------- #

class TestSpatialSymbolicReasoningLayer:
    def test_extract_objects_single(self, spatial_layer):
        grid = [[1, 1, 0], [1, 0, 0], [0, 0, 2]]
        scene = spatial_layer.parse_grid(grid)
        assert len(scene.objects) == 2
        colors = {obj.color for obj in scene.objects}
        assert colors == {1, 2}

    def test_compute_relations(self, spatial_layer):
        grid = [[1, 0, 0], [0, 0, 0], [0, 0, 2]]
        scene = spatial_layer.parse_grid(grid)
        rels = spatial_layer.compute_relations(scene)
        assert len(rels) == 2

    def test_diff_scenes_translation(self, spatial_layer):
        before = spatial_layer.parse_grid([[1, 0, 0], [0, 0, 0], [0, 0, 0]])
        after = spatial_layer.parse_grid([[0, 1, 0], [0, 0, 0], [0, 0, 0]])
        diff = spatial_layer.diff_scenes(before, after)
        assert len(diff.moved) == 1
        assert diff.moved[0]["vector"] == (1, 0)

    def test_diff_scenes_color_change(self, spatial_layer):
        before = spatial_layer.parse_grid([[1, 0], [0, 0]])
        after = spatial_layer.parse_grid([[2, 0], [0, 0]])
        diff = spatial_layer.diff_scenes(before, after)
        assert len(diff.recolored) == 1
        assert diff.recolored[0]["old_color"] == 1
        assert diff.recolored[0]["new_color"] == 2


# --------------------------------------------------------------------------- #
# Few-Shot Program Induction Engine
# --------------------------------------------------------------------------- #

class TestFewShotProgramInductionEngine:
    def test_induce_rotation_90(self, induction_engine):
        train = [
            {
                "input": [[1, 0, 0], [1, 0, 0], [1, 0, 0]],
                "output": [[1, 1, 1], [0, 0, 0], [0, 0, 0]],
            },
            {
                "input": [[0, 2], [0, 2]],
                "output": [[0, 0], [2, 2]],
            },
        ]
        candidates = induction_engine.induce(train)
        assert candidates
        top = candidates[0]
        assert top.train_matches == len(train)
        pred = top.program.apply([[3, 0], [3, 0]])
        assert pred == [[3, 3], [0, 0]]

    def test_induce_translation(self, induction_engine):
        train = [
            {
                "input": [[1, 0, 0], [0, 0, 0], [0, 0, 0]],
                "output": [[0, 1, 0], [0, 0, 0], [0, 0, 0]],
            },
            {
                "input": [[0, 0, 0], [2, 0, 0], [0, 0, 0]],
                "output": [[0, 0, 0], [0, 2, 0], [0, 0, 0]],
            },
        ]
        candidates = induction_engine.induce(train)
        assert candidates
        top = candidates[0]
        assert top.train_matches == len(train)
        pred = top.program.apply([[0, 0, 0], [3, 0, 0], [0, 0, 0]])
        assert pred == [[0, 0, 0], [0, 3, 0], [0, 0, 0]]

    def test_induce_color_map(self, induction_engine):
        train = [
            {
                "input": [[1, 1], [2, 2]],
                "output": [[3, 3], [4, 4]],
            },
            {
                "input": [[1, 2], [2, 1]],
                "output": [[3, 4], [4, 3]],
            },
        ]
        candidates = induction_engine.induce(train)
        assert candidates
        top = candidates[0]
        assert top.train_matches == len(train)
        pred = top.program.apply([[2, 1], [1, 2]])
        assert pred == [[4, 3], [3, 4]]

    def test_predict_top_k(self, induction_engine):
        train = [
            {
                "input": [[1, 0], [0, 0]],
                "output": [[0, 0], [0, 1]],
            }
        ]
        candidates = induction_engine.induce(train)
        induction_engine.set_candidates(candidates)
        preds = induction_engine.predict([[2, 0], [0, 0]], top_k=2)
        assert len(preds) <= 2

    def test_explain(self, induction_engine):
        prog = TransformationProgram(steps=[GridTransformation(name="rotate_90")])
        cand = induction_engine.induce([])
        # empty train yields no candidates; test explain manually
        from speace_core.cellular_brain.cognition.few_shot_program_induction_engine import (
            ProgramCandidate,
        )

        candidate = ProgramCandidate(program=prog, train_matches=1, confidence=1.0)
        explanation = induction_engine.explain(candidate)
        assert "rotate_90" in explanation
        assert "1 matches" in explanation


# --------------------------------------------------------------------------- #
# ARC-AGI Adapter
# --------------------------------------------------------------------------- #

class TestARCAGIAdapter:
    def test_load_tasks(self, tmp_arc_data):
        engine = FewShotProgramInductionEngine()
        adapter = ARCAGIAdapter(engine=engine, data_dir=tmp_arc_data)
        tasks = adapter.load_tasks(split="training")
        assert len(tasks) == 4
        task_ids = {t.task_id for t in tasks}
        assert task_ids == {"rotate_90", "translate_right", "color_map", "compose_rotate_flip"}

    def test_evaluate_task(self, tmp_arc_data):
        engine = FewShotProgramInductionEngine()
        adapter = ARCAGIAdapter(engine=engine, data_dir=tmp_arc_data)
        tasks = adapter.load_tasks(split="training")
        task = next(t for t in tasks if t.task_id == "rotate_90")
        results = adapter.evaluate_task(task)
        assert len(results) == 1
        assert results[0].correct is True
        assert results[0].match_score == 1.0

    def test_run_benchmark(self, tmp_arc_data):
        engine = FewShotProgramInductionEngine()
        adapter = ARCAGIAdapter(engine=engine, data_dir=tmp_arc_data)
        report = adapter.run_benchmark()
        assert report["total_tasks"] == 4
        assert report["correct"] >= 2
        assert report["top1_accuracy"] >= 0.4

    def test_evaluate_compositional_task(self, tmp_arc_data):
        engine = FewShotProgramInductionEngine()
        adapter = ARCAGIAdapter(engine=engine, data_dir=tmp_arc_data)
        tasks = adapter.load_tasks(split="training")
        task = next((t for t in tasks if t.task_id == "compose_rotate_flip"), None)
        assert task is not None
        results = adapter.evaluate_task(task)
        assert len(results) == 1
        # The compositional task requires rotate_90 + flip_vertical.
        # Our engine with max depth 3 should be able to discover it.
        assert results[0].correct is True
        assert results[0].match_score == 1.0

    def test_evaluation_mode_bypasses_gate(self, tmp_arc_data):
        engine = FewShotProgramInductionEngine()
        adapter = ARCAGIAdapter(engine=engine, data_dir=tmp_arc_data, evaluation_mode=True)
        assert adapter.evaluation_mode is True

    def test_multimodal_grounding(self, induction_engine):
        assert induction_engine.ground("rotate 90 degrees") == "rotate_90"
        assert induction_engine.ground("flip horizontally") == "flip_horizontal"
        assert induction_engine.ground("change color") == "color_map"
        assert induction_engine.ground("unknown phrase") is None

    def test_no_silent_exceptions_in_new_files(self):
        import ast
        import inspect

        from speace_core.benchmark import arc_agi_adapter
        from speace_core.cellular_brain.cognition import (
            few_shot_program_induction_engine,
            spatial_symbolic_reasoning_layer,
        )

        for mod in [
            arc_agi_adapter,
            few_shot_program_induction_engine,
            spatial_symbolic_reasoning_layer,
        ]:
            source = inspect.getsource(mod)
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler):
                    body = node.body
                    if len(body) == 1 and isinstance(body[0], ast.Pass):
                        pytest.fail(f"Bare except:pass found in {mod.__name__}")
