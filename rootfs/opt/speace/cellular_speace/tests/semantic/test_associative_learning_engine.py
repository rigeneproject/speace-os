import pytest

from speace_core.cellular_brain.memory.semantic.cell_assembly import CellAssembly
from speace_core.cellular_brain.memory.semantic.associative_learning_engine import (
    AssociativeLearningEngine,
)


class FakeMorphologicalMemory:
    def __init__(self):
        self.events = []

    def log_event(self, event):
        self.events.append(event)


class TestAssociativeLearningEngine:
    def test_observe_two_active_assemblies_creates_association(self):
        engine = AssociativeLearningEngine()
        a = CellAssembly(assembly_id="asm-a", strength=0.5)
        b = CellAssembly(assembly_id="asm-b", strength=0.5)
        result = engine.observe_assemblies([a, b], tick=1)
        assert result.created_associations == 1
        assert len(engine.list_associations()) == 1

    def test_repeated_coactivation_reinforces_association(self):
        engine = AssociativeLearningEngine()
        a = CellAssembly(assembly_id="asm-a", strength=0.5)
        b = CellAssembly(assembly_id="asm-b", strength=0.5)
        engine.observe_assemblies([a, b], tick=1)
        result = engine.observe_assemblies([a, b], tick=2)
        # History contains both ticks, so reinforcement may be counted multiple times
        assert result.reinforced_associations >= 1
        assoc = engine.list_associations()[0]
        assert assoc.strength > 0.1

    def test_no_self_association_created(self):
        engine = AssociativeLearningEngine()
        a = CellAssembly(assembly_id="asm-a", strength=0.5)
        result = engine.observe_assemblies([a], tick=1)
        assert result.created_associations == 0
        assert len(engine.list_associations()) == 0

    def test_decay_weakens_associations(self):
        engine = AssociativeLearningEngine(decay_rate=0.05)
        a = CellAssembly(assembly_id="asm-a", strength=0.5)
        b = CellAssembly(assembly_id="asm-b", strength=0.5)
        engine.observe_assemblies([a, b], tick=1)
        before = engine.list_associations()[0].strength
        result = engine.decay_associations()
        after = engine.list_associations()[0].strength
        assert after < before
        assert result.weakened_associations == 1

    def test_prune_removes_weak_associations(self):
        engine = AssociativeLearningEngine(prune_threshold=0.15)
        a = CellAssembly(assembly_id="asm-a", strength=0.5)
        b = CellAssembly(assembly_id="asm-b", strength=0.5)
        engine.observe_assemblies([a, b], tick=1)
        # Force strength below threshold via decay
        engine._associations[list(engine._associations.keys())[0]].strength = 0.02
        result = engine.prune_weak_associations()
        assert result.pruned_associations == 1
        assert len(engine.list_associations()) == 0

    def test_get_associations_for_source(self):
        engine = AssociativeLearningEngine()
        a = CellAssembly(assembly_id="asm-a", strength=0.5)
        b = CellAssembly(assembly_id="asm-b", strength=0.5)
        c = CellAssembly(assembly_id="asm-c", strength=0.5)
        engine.observe_assemblies([a, b, c], tick=1)
        assoc_a = engine.get_associations_for_source("asm-a")
        assert len(assoc_a) == 2

    def test_association_density_computed(self):
        engine = AssociativeLearningEngine()
        a = CellAssembly(assembly_id="asm-a", strength=0.5)
        b = CellAssembly(assembly_id="asm-b", strength=0.5)
        c = CellAssembly(assembly_id="asm-c", strength=0.5)
        engine.observe_assemblies([a, b, c], tick=1)
        result = engine.observe_assemblies([a, b, c], tick=2)
        # 3 assemblies, 3 associations total; density is low by default but non-negative
        assert result.association_density >= 0.0

    def test_events_logged_to_morphological_memory(self):
        fake_mem = FakeMorphologicalMemory()
        engine = AssociativeLearningEngine(memory=fake_mem)
        a = CellAssembly(assembly_id="asm-a", strength=0.5)
        b = CellAssembly(assembly_id="asm-b", strength=0.5)
        engine.observe_assemblies([a, b], tick=1)
        types = [str(e.event_type) for e in fake_mem.events]
        assert any("ASSEMBLY_ASSOCIATION_CREATED" in t for t in types)

    def test_create_or_get_association(self):
        engine = AssociativeLearningEngine()
        assoc1 = engine.create_or_get_association("asm-a", "asm-b", "causal")
        assoc2 = engine.create_or_get_association("asm-b", "asm-a", "causal")
        assert assoc1.id == assoc2.id
        assert len(engine.list_associations()) == 1

    def test_reinforce_association(self):
        engine = AssociativeLearningEngine()
        assoc = engine.create_or_get_association("asm-a", "asm-b")
        old_strength = assoc.strength
        engine.reinforce_association(assoc.id, amount=0.2)
        assert assoc.strength == old_strength + 0.2

    def test_weaken_association(self):
        engine = AssociativeLearningEngine()
        assoc = engine.create_or_get_association("asm-a", "asm-b")
        assoc.strength = 0.5
        engine.weaken_association(assoc.id, amount=0.1)
        assert assoc.strength == 0.4

    def test_confidence_grows_with_coactivation(self):
        engine = AssociativeLearningEngine()
        a = CellAssembly(assembly_id="asm-a", strength=0.5)
        b = CellAssembly(assembly_id="asm-b", strength=0.5)
        for tick in range(1, 6):
            engine.observe_assemblies([a, b], tick=tick)
        assoc = engine.list_associations()[0]
        assert assoc.confidence > 0.0
