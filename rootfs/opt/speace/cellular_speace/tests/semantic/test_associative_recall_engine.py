import pytest

from speace_core.cellular_brain.memory.semantic.assembly_association import (
    AssemblyAssociation,
)
from speace_core.cellular_brain.memory.semantic.cell_assembly import CellAssembly
from speace_core.cellular_brain.memory.semantic.associative_learning_engine import (
    AssociativeLearningEngine,
)
from speace_core.cellular_brain.memory.semantic.associative_recall_engine import (
    AssociativeRecallEngine,
)


class FakeMorphologicalMemory:
    def __init__(self):
        self.events = []

    def log_event(self, event):
        self.events.append(event)


class FakeSemanticRecallEngine:
    def __init__(self, best_match_id):
        self._best_match_id = best_match_id

    def recall(self, pattern):
        from speace_core.cellular_brain.memory.semantic.cell_assembly import (
            SemanticRecallResult,
        )

        return SemanticRecallResult(
            query_signature=pattern,
            recall_success=bool(self._best_match_id),
            best_match_id=self._best_match_id,
        )


class TestAssociativeRecallEngine:
    def test_recall_from_assembly_success(self):
        learn = AssociativeLearningEngine()
        a = CellAssembly(assembly_id="asm-a", strength=0.5)
        b = CellAssembly(assembly_id="asm-b", strength=0.5)
        for tick in range(1, 8):
            learn.observe_assemblies([a, b], tick=tick)
        recall = AssociativeRecallEngine(learn, recall_threshold=0.25)
        result = recall.recall_from_assembly("asm-a")
        assert result.success is True
        assert "asm-b" in result.recalled_assembly_ids

    def test_recall_from_assembly_below_threshold_fails(self):
        learn = AssociativeLearningEngine()
        a = CellAssembly(assembly_id="asm-a", strength=0.5)
        b = CellAssembly(assembly_id="asm-b", strength=0.5)
        learn.observe_assemblies([a, b], tick=1)
        # Single coactivation gives low score; raise threshold to force failure
        recall = AssociativeRecallEngine(learn, recall_threshold=0.99)
        result = recall.recall_from_assembly("asm-a")
        assert result.success is False

    def test_recall_returns_best_match(self):
        learn = AssociativeLearningEngine()
        a = CellAssembly(assembly_id="asm-a", strength=0.5)
        b = CellAssembly(assembly_id="asm-b", strength=0.5)
        c = CellAssembly(assembly_id="asm-c", strength=0.5)
        for _ in range(5):
            learn.observe_assemblies([a, b, c], tick=1)
        # Reinforce a-b more than a-c
        for _ in range(5):
            learn.observe_assemblies([a, b], tick=2)
        recall = AssociativeRecallEngine(learn, recall_threshold=0.25)
        result = recall.recall_from_assembly("asm-a")
        assert result.best_match_id is not None
        assert result.best_match_score > 0.0

    def test_recall_respects_max_recall(self):
        learn = AssociativeLearningEngine()
        a = CellAssembly(assembly_id="asm-a", strength=0.5)
        b = CellAssembly(assembly_id="asm-b", strength=0.5)
        c = CellAssembly(assembly_id="asm-c", strength=0.5)
        d = CellAssembly(assembly_id="asm-d", strength=0.5)
        for _ in range(5):
            learn.observe_assemblies([a, b, c, d], tick=1)
        recall = AssociativeRecallEngine(learn, recall_threshold=0.1, max_recall=2)
        result = recall.recall_from_assembly("asm-a")
        assert len(result.recalled_assembly_ids) <= 2

    def test_recall_updates_success_count(self):
        learn = AssociativeLearningEngine()
        a = CellAssembly(assembly_id="asm-a", strength=0.5)
        b = CellAssembly(assembly_id="asm-b", strength=0.5)
        for _ in range(5):
            learn.observe_assemblies([a, b], tick=1)
        recall = AssociativeRecallEngine(learn, recall_threshold=0.25)
        recall.recall_from_assembly("asm-a")
        assoc = learn.list_associations()[0]
        assert assoc.recall_success_count >= 1

    def test_recall_updates_failure_count(self):
        learn = AssociativeLearningEngine()
        a = CellAssembly(assembly_id="asm-a", strength=0.5)
        b = CellAssembly(assembly_id="asm-b", strength=0.5)
        for tick in range(1, 8):
            learn.observe_assemblies([a, b], tick=tick)
        recall = AssociativeRecallEngine(learn, recall_threshold=0.99)
        recall.recall_from_assembly("asm-a")
        assoc = learn.list_associations()[0]
        # Should have incremented failure because score >= 0.5 * threshold but below threshold
        assert assoc.recall_failure_count >= 1

    def test_recall_from_pattern_uses_semantic_recall_engine(self):
        learn = AssociativeLearningEngine()
        a = CellAssembly(assembly_id="asm-a", strength=0.5)
        b = CellAssembly(assembly_id="asm-b", strength=0.5)
        for _ in range(5):
            learn.observe_assemblies([a, b], tick=1)
        fake_sem = FakeSemanticRecallEngine("asm-a")
        recall = AssociativeRecallEngine(learn, recall_threshold=0.25)
        result = recall.recall_from_pattern([0.1, 0.2], semantic_recall_engine=fake_sem)
        assert result.success is True
        assert "asm-b" in result.recalled_assembly_ids

    def test_recall_from_pattern_without_semantic_engine_fails(self):
        learn = AssociativeLearningEngine()
        recall = AssociativeRecallEngine(learn, recall_threshold=0.25)
        result = recall.recall_from_pattern([0.1, 0.2])
        assert result.success is False

    def test_associative_recall_logs_success_and_failure(self):
        fake_mem = FakeMorphologicalMemory()
        learn = AssociativeLearningEngine()
        a = CellAssembly(assembly_id="asm-a", strength=0.5)
        b = CellAssembly(assembly_id="asm-b", strength=0.5)
        for _ in range(5):
            learn.observe_assemblies([a, b], tick=1)
        recall = AssociativeRecallEngine(learn, memory=fake_mem, recall_threshold=0.25)
        recall.recall_from_assembly("asm-a")
        types = [str(e.event_type) for e in fake_mem.events]
        assert any("ASSOCIATIVE_RECALL_SUCCEEDED" in t for t in types)

    def test_score_association_formula(self):
        assoc = AssemblyAssociation(
            id="assoc-001",
            source_assembly_id="asm-a",
            target_assembly_id="asm-b",
            strength=0.8,
            confidence=0.6,
            recall_success_count=4,
            recall_failure_count=1,
        )
        score = AssociativeRecallEngine.score_association(assoc)
        expected = (
            0.50 * 0.8
            + 0.25 * 0.6
            + 0.15 * 0.8
            - 0.10 * 0.2
        )
        assert abs(score - expected) < 1e-6
