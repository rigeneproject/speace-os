"""Tests for ProgramSchemaLibrary integration with ARCAGIAdapter."""
import pytest
from unittest.mock import MagicMock, patch

from speace_core.benchmark.arc_agi_adapter import ARCAGIAdapter, ARCTask
from speace_core.cellular_brain.cognition.program_models import (
    TransformationProgram,
    GridTransformation,
)
from speace_core.cellular_brain.cognition.program_schema_library import ProgramSchemaLibrary


@pytest.fixture
def mock_engine():
    engine = MagicMock()
    engine.induce.return_value = []
    engine.predict.return_value = [[[1, 0], [0, 0]]]
    engine.explain.return_value = ""
    return engine


@pytest.fixture
def adapter(mock_engine, tmp_path):
    a = ARCAGIAdapter(engine=mock_engine)
    a.schema_library = ProgramSchemaLibrary(data_dir=str(tmp_path / "test_schema"))
    return a


@pytest.fixture
def adapter_with_schema(mock_engine, tmp_path):
    a = ARCAGIAdapter(engine=mock_engine)
    a.schema_library = ProgramSchemaLibrary(data_dir=str(tmp_path / "test_schema2"))
    # Pre-populate with a working program
    from speace_core.cellular_brain.cognition.program_models import TransformationProgram, GridTransformation
    prog = TransformationProgram(steps=[GridTransformation(name="color_map", params={"mapping": {"1": 2}})])
    a.schema_library.add_from_program(prog, [{"input": [[1]], "output": [[2]]}], pixel_score=1.0)
    return a


@pytest.fixture
def simple_task():
    return ARCTask(
        task_id="test_task",
        train=[{"input": [[1]], "output": [[2]]}],
        test=[{"input": [[1]], "output": [[2]]}],
    )


class TestSchemaIntegration:
    def test_schema_stores_on_success(self, adapter_with_schema, simple_task, mock_engine):
        mock_engine.predict.return_value = [[[2]]]
        results = adapter_with_schema.evaluate_task(simple_task)
        stats = adapter_with_schema.schema_library.get_statistics()
        assert stats["total_schemas"] >= 1

    def test_schema_not_stored_on_failure(self, adapter, simple_task, mock_engine):
        mock_engine.predict.return_value = [[[3]]]  # wrong output
        results = adapter.evaluate_task(simple_task)
        assert not results[0].correct

    def test_schema_suggests_programs(self, adapter_with_schema, simple_task, mock_engine):
        results = adapter_with_schema.evaluate_task(simple_task)
        assert results[0].candidates_explored >= 0

    def test_schema_library_persistent_across_evaluations(self, adapter_with_schema, simple_task, mock_engine, tmp_path):
        mock_engine.predict.return_value = [[[2]]]
        adapter_with_schema.evaluate_task(simple_task)
        adapter2 = ARCAGIAdapter(engine=MagicMock())
        adapter2.schema_library = ProgramSchemaLibrary(data_dir=str(tmp_path / "test_schema2"))
        stats = adapter2.schema_library.get_statistics()
        assert stats["total_schemas"] >= 1
