import pytest

from speace_core.cellular_brain.memory.semantic.cell_assembly import CellAssembly
from speace_core.cellular_brain.memory.semantic.semantic_memory_store import (
    SemanticMemoryStore,
)
from speace_core.dna.models import SharedGenome
from speace_core.orchestrator import CellularBrainOrchestrator


class TestOrchestratorAssociativeIntegration:
    def test_orchestrator_initializes_associative_learning_lazy(self):
        genome = SharedGenome()
        orch = CellularBrainOrchestrator.build_mvp(genome)
        orch.semantic_memory_enabled = True
        orch.associative_learning_enabled = True
        engine = orch.get_associative_learning_engine()
        assert engine is not None
        assert orch._associative_learning_engine is engine

    def test_orchestrator_manual_associative_learning_cycle(self):
        from speace_core.cellular_brain.memory.semantic.semantic_memory_store import (
            SemanticMemoryStore,
        )

        genome = SharedGenome()
        orch = CellularBrainOrchestrator.build_mvp(genome)
        orch.semantic_memory_enabled = True
        orch.associative_learning_enabled = True
        # Manually create store since semantic_memory_enabled was False at build time
        orch._semantic_memory_store = SemanticMemoryStore()
        store = orch._semantic_memory_store
        store.save(CellAssembly(assembly_id="asm-a", active=True, strength=0.5))
        store.save(CellAssembly(assembly_id="asm-b", active=True, strength=0.5))
        result = orch.run_associative_learning_cycle()
        assert result is not None
        assert result.created_associations == 1

    def test_orchestrator_associative_recall_lazy(self):
        from speace_core.cellular_brain.memory.semantic.semantic_memory_store import (
            SemanticMemoryStore,
        )

        genome = SharedGenome()
        orch = CellularBrainOrchestrator.build_mvp(genome)
        orch.semantic_memory_enabled = True
        orch.associative_learning_enabled = True
        orch.associative_recall_enabled = True
        orch._semantic_memory_store = SemanticMemoryStore()
        store = orch._semantic_memory_store
        store.save(CellAssembly(assembly_id="asm-a", active=True, strength=0.5))
        store.save(CellAssembly(assembly_id="asm-b", active=True, strength=0.5))
        orch.run_associative_learning_cycle()
        result = orch.recall_associative_memory("asm-a")
        assert result is not None

    def test_benchmark_reports_associative_metrics_defaults(self):
        from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import (
            BenchmarkMetrics,
        )

        m = BenchmarkMetrics()
        assert m.assembly_association_count == 0
        assert m.mean_association_strength == 0.0
        assert m.associative_memory_effect_score == 0.0
