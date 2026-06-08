"""Tests for ProgramSchemaLibrary."""
import pytest
from speace_core.cellular_brain.cognition.program_schema_library import (
    ProgramSchema,
    ProgramSchemaLibrary,
    compute_task_signature,
    compute_signature_similarity,
)
from speace_core.cellular_brain.cognition.program_models import (
    TransformationProgram,
    GridTransformation,
)


@pytest.fixture
def library(tmp_path):
    return ProgramSchemaLibrary(data_dir=str(tmp_path / "schema_library"))


@pytest.fixture
def sample_program():
    return TransformationProgram(steps=[
        GridTransformation(name="rotate_90", params={}),
        GridTransformation(name="color_map", params={"mapping": {"1": "2"}}),
    ])


@pytest.fixture
def sample_task_pairs():
    return [
        {"input": [[1, 1], [0, 0]], "output": [[0, 1], [0, 1]]},
        {"input": [[1, 0], [1, 0]], "output": [[0, 0], [1, 1]]},
    ]


class TestComputeTaskSignature:
    def test_signature_structure(self):
        pairs = [{"input": [[1, 0], [0, 1]], "output": [[0, 1], [1, 0]]}]
        sig = compute_task_signature(pairs)
        assert "in_" in sig
        assert "out_" in sig
        assert "cin_" in sig

    def test_signature_stable_same_task(self):
        pairs1 = [{"input": [[1, 0], [0, 1]], "output": [[2, 2], [2, 2]]}]
        pairs2 = [{"input": [[1, 0], [0, 1]], "output": [[2, 2], [2, 2]]}]
        assert compute_task_signature(pairs1) == compute_task_signature(pairs2)


class TestComputeSignatureSimilarity:
    def test_identical_scores_one(self):
        assert compute_signature_similarity("in_3x3_out_3x3", "in_3x3_out_3x3") == 1.0

    def test_different_scores_below_one(self):
        assert compute_signature_similarity("in_3x3_out_3x3", "in_5x5_out_5x5") < 1.0

    def test_empty_returns_zero(self):
        assert compute_signature_similarity("", "") == 0.0


class TestProgramSchema:
    def test_instantiate_returns_program(self):
        schema = ProgramSchema(
            schema_id="test",
            steps=[GridTransformation(name="rotate_90", params={})],
            parameter_defaults={"dx": 1},
        )
        prog = schema.instantiate({"dx": 2})
        assert isinstance(prog, TransformationProgram)
        assert len(prog.steps) == 1
        assert prog.steps[0].params["dx"] == 2


class TestProgramSchemaLibrary:
    def test_add_from_program_returns_schema_id(self, library, sample_program, sample_task_pairs):
        sid = library.add_from_program(sample_program, sample_task_pairs, pixel_score=0.9)
        assert sid is not None
        assert sid.startswith("schema_")

    def test_add_duplicate_increments_success_count(self, library, sample_program, sample_task_pairs):
        sid1 = library.add_from_program(sample_program, sample_task_pairs, pixel_score=0.9)
        sid2 = library.add_from_program(sample_program, sample_task_pairs, pixel_score=0.8)
        assert sid1 == sid2
        stats = library.get_statistics()
        assert stats["total_schemas"] == 1

    def test_add_empty_program_returns_none(self, library, sample_task_pairs):
        empty = TransformationProgram(steps=[])
        assert library.add_from_program(empty, sample_task_pairs) is None

    def test_get_schemas_for_task(self, library, sample_program, sample_task_pairs):
        library.add_from_program(sample_program, sample_task_pairs, pixel_score=0.9)
        schemas = library.get_schemas_for_task(sample_task_pairs, min_similarity=0.1)
        assert len(schemas) >= 1

    def test_suggest_programs(self, library, sample_program, sample_task_pairs):
        library.add_from_program(sample_program, sample_task_pairs, pixel_score=0.9)
        programs = library.suggest_programs(sample_task_pairs, top_k=2)
        assert len(programs) >= 1
        assert all(isinstance(p, TransformationProgram) for p in programs)

    def test_get_statistics_empty(self, library):
        stats = library.get_statistics()
        assert stats["total_schemas"] == 0

    def test_get_statistics_after_add(self, library, sample_program, sample_task_pairs):
        library.add_from_program(sample_program, sample_task_pairs, pixel_score=0.9)
        stats = library.get_statistics()
        assert stats["total_schemas"] == 1
        assert stats["total_successes"] == 1

    def test_clear_removes_all(self, library, sample_program, sample_task_pairs):
        library.add_from_program(sample_program, sample_task_pairs, pixel_score=0.9)
        library.clear()
        assert library.get_statistics()["total_schemas"] == 0

    def test_persistence_across_reload(self, tmp_path, sample_program, sample_task_pairs):
        d = str(tmp_path / "schema_lib")
        lib1 = ProgramSchemaLibrary(data_dir=d)
        lib1.add_from_program(sample_program, sample_task_pairs, pixel_score=0.9)
        lib2 = ProgramSchemaLibrary(data_dir=d)
        stats = lib2.get_statistics()
        assert stats["total_schemas"] == 1
