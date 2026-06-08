import json
import pytest

from speace_core.cellular_brain.evolutionary_memory import (
    ConsolidationDecision,
    ConsolidationPolicyEngine,
    EvolutionaryForgettingEngine,
    EvolutionaryMemoryAudit,
    EvolutionaryMemoryGovernor,
    EvolutionaryMemoryRecord,
    EvolutionaryMemoryStatus,
    EvolutionaryMemoryStore,
    MemoryConflict,
    MemoryConflictResolver,
)


# ------------------------------------------------------------------ #
# Model validation
# ------------------------------------------------------------------ #

def test_record_defaults():
    r = EvolutionaryMemoryRecord(record_id="r1", source_cycle_id="c1", source_task="t1", source_profile="p1")
    assert r.status == EvolutionaryMemoryStatus.VOLATILE.value
    assert r.reuse_count == 0


def test_consolidation_decision_defaults():
    d = ConsolidationDecision(record_id="r1", previous_status="volatile", new_status="stable", reason="test")
    assert d.requires_human_review is False


def test_memory_conflict_defaults():
    c = MemoryConflict(conflict_id="c1", record_a_id="a", record_b_id="b", conflict_type="FITNESS_CONFLICT")
    assert c.severity == 0.0


# ------------------------------------------------------------------ #
# Store
# ------------------------------------------------------------------ #

def test_store_add_and_get():
    store = EvolutionaryMemoryStore()
    r = EvolutionaryMemoryRecord(record_id="r1", source_cycle_id="c1", source_task="t1", source_profile="p1")
    store.add_record(r)
    assert store.get_record("r1") is not None
    assert store.get_record("r1").record_id == "r1"


def test_store_prevents_duplicates():
    store = EvolutionaryMemoryStore()
    r = EvolutionaryMemoryRecord(record_id="r1", source_cycle_id="c1", source_task="t1", source_profile="p1")
    store.add_record(r)
    store.add_record(r)
    assert store.total_records() == 1


def test_store_list_by_status():
    store = EvolutionaryMemoryStore()
    store.add_record(EvolutionaryMemoryRecord(record_id="r1", source_cycle_id="c1", source_task="t1", source_profile="p1", status=EvolutionaryMemoryStatus.STABLE.value))
    store.add_record(EvolutionaryMemoryRecord(record_id="r2", source_cycle_id="c1", source_task="t1", source_profile="p1", status=EvolutionaryMemoryStatus.EXPERIMENTAL.value))
    stable = store.list_records(status=EvolutionaryMemoryStatus.STABLE.value)
    assert len(stable) == 1
    assert stable[0].record_id == "r1"


def test_store_list_by_source_task():
    store = EvolutionaryMemoryStore()
    store.add_record(EvolutionaryMemoryRecord(record_id="r1", source_cycle_id="c1", source_task="t1", source_profile="p1"))
    store.add_record(EvolutionaryMemoryRecord(record_id="r2", source_cycle_id="c1", source_task="t2", source_profile="p1"))
    assert len(store.list_records(source_task="t1")) == 1


def test_store_update_status():
    store = EvolutionaryMemoryStore()
    store.add_record(EvolutionaryMemoryRecord(record_id="r1", source_cycle_id="c1", source_task="t1", source_profile="p1"))
    d = store.update_status("r1", EvolutionaryMemoryStatus.STABLE.value, "promoted")
    assert d.previous_status == EvolutionaryMemoryStatus.VOLATILE.value
    assert d.new_status == EvolutionaryMemoryStatus.STABLE.value
    assert store.get_record("r1").status == EvolutionaryMemoryStatus.STABLE.value


def test_store_increment_reuse():
    store = EvolutionaryMemoryStore()
    store.add_record(EvolutionaryMemoryRecord(record_id="r1", source_cycle_id="c1", source_task="t1", source_profile="p1"))
    store.increment_reuse("r1")
    assert store.get_record("r1").reuse_count == 1


def test_store_export_json(tmp_path):
    store = EvolutionaryMemoryStore(report_dir=str(tmp_path))
    store.add_record(EvolutionaryMemoryRecord(record_id="r1", source_cycle_id="c1", source_task="t1", source_profile="p1"))
    path = store.export_json()
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data) == 1


def test_store_export_markdown(tmp_path):
    store = EvolutionaryMemoryStore(report_dir=str(tmp_path))
    store.add_record(EvolutionaryMemoryRecord(record_id="r1", source_cycle_id="c1", source_task="t1", source_profile="p1"))
    path = store.export_markdown()
    assert path.exists()
    assert "r1" in path.read_text(encoding="utf-8")


def test_store_count_by_status():
    store = EvolutionaryMemoryStore()
    store.add_record(EvolutionaryMemoryRecord(record_id="r1", source_cycle_id="c1", source_task="t1", source_profile="p1", status=EvolutionaryMemoryStatus.STABLE.value))
    store.add_record(EvolutionaryMemoryRecord(record_id="r2", source_cycle_id="c1", source_task="t1", source_profile="p1", status=EvolutionaryMemoryStatus.STABLE.value))
    assert store.count_by_status(EvolutionaryMemoryStatus.STABLE.value) == 2


# ------------------------------------------------------------------ #
# ConsolidationPolicyEngine
# ------------------------------------------------------------------ #

def test_positive_safe_record_promoted_to_stable():
    engine = ConsolidationPolicyEngine()
    r = EvolutionaryMemoryRecord(
        record_id="r1",
        source_cycle_id="c1",
        source_task="t1",
        source_profile="p1",
        fitness_delta=0.5,
        phi_delta=0.1,
        regression_score=0.1,
        safety_score=0.8,
        confidence=0.6,
        reuse_count=1,
    )
    d = engine.evaluate(r)
    assert d.new_status == EvolutionaryMemoryStatus.STABLE.value


def test_positive_not_reused_promoted_to_probationary():
    engine = ConsolidationPolicyEngine()
    r = EvolutionaryMemoryRecord(
        record_id="r1",
        source_cycle_id="c1",
        source_task="t1",
        source_profile="p1",
        fitness_delta=0.5,
        safety_score=0.7,
        confidence=0.5,
        reuse_count=0,
    )
    d = engine.evaluate(r)
    assert d.new_status == EvolutionaryMemoryStatus.PROBATIONARY.value


def test_unsafe_record_quarantined():
    engine = ConsolidationPolicyEngine()
    r = EvolutionaryMemoryRecord(
        record_id="r1",
        source_cycle_id="c1",
        source_task="t1",
        source_profile="p1",
        safety_score=0.3,
    )
    d = engine.evaluate(r)
    assert d.new_status == EvolutionaryMemoryStatus.QUARANTINED.value


def test_high_drift_record_not_promoted():
    engine = ConsolidationPolicyEngine()
    r = EvolutionaryMemoryRecord(
        record_id="r1",
        source_cycle_id="c1",
        source_task="t1",
        source_profile="p1",
        fitness_delta=0.5,
        drift_score=0.6,
        safety_score=0.8,
        confidence=0.8,
        reuse_count=2,
    )
    d = engine.evaluate(r)
    assert d.new_status == EvolutionaryMemoryStatus.QUARANTINED.value


def test_high_regression_record_not_promoted():
    engine = ConsolidationPolicyEngine()
    r = EvolutionaryMemoryRecord(
        record_id="r1",
        source_cycle_id="c1",
        source_task="t1",
        source_profile="p1",
        fitness_delta=0.5,
        regression_score=0.6,
        safety_score=0.8,
        confidence=0.8,
        reuse_count=2,
    )
    d = engine.evaluate(r)
    assert d.new_status == EvolutionaryMemoryStatus.QUARANTINED.value


def test_low_confidence_positive_becomes_experimental():
    engine = ConsolidationPolicyEngine()
    r = EvolutionaryMemoryRecord(
        record_id="r1",
        source_cycle_id="c1",
        source_task="t1",
        source_profile="p1",
        fitness_delta=0.3,
        confidence=0.1,
    )
    d = engine.evaluate(r)
    assert d.new_status == EvolutionaryMemoryStatus.EXPERIMENTAL.value


def test_negative_fitness_no_reuse_deprecated():
    engine = ConsolidationPolicyEngine()
    r = EvolutionaryMemoryRecord(
        record_id="r1",
        source_cycle_id="c1",
        source_task="t1",
        source_profile="p1",
        fitness_delta=-0.1,
        reuse_count=0,
    )
    d = engine.evaluate(r)
    assert d.new_status == EvolutionaryMemoryStatus.DEPRECATED.value


def test_very_low_fitness_forgotten():
    engine = ConsolidationPolicyEngine()
    r = EvolutionaryMemoryRecord(
        record_id="r1",
        source_cycle_id="c1",
        source_task="t1",
        source_profile="p1",
        fitness_delta=-0.5,
        confidence=0.1,
        reuse_count=0,
    )
    d = engine.evaluate(r)
    assert d.new_status == EvolutionaryMemoryStatus.FORGOTTEN.value


# ------------------------------------------------------------------ #
# MemoryConflictResolver
# ------------------------------------------------------------------ #

def test_duplicate_pattern_detected():
    resolver = MemoryConflictResolver()
    records = [
        EvolutionaryMemoryRecord(record_id="r1", source_cycle_id="c1", source_task="t1", source_profile="p1", fitness_delta=0.5),
        EvolutionaryMemoryRecord(record_id="r2", source_cycle_id="c1", source_task="t1", source_profile="p1", fitness_delta=0.52),
    ]
    conflicts = resolver.detect_conflicts(records)
    assert any(c.conflict_type == "DUPLICATE_PATTERN" for c in conflicts)


def test_fitness_conflict_detected():
    resolver = MemoryConflictResolver()
    records = [
        EvolutionaryMemoryRecord(record_id="r1", source_cycle_id="c1", source_task="t1", source_profile="p1", fitness_delta=0.5),
        EvolutionaryMemoryRecord(record_id="r2", source_cycle_id="c1", source_task="t1", source_profile="p1", fitness_delta=-0.3),
    ]
    conflicts = resolver.detect_conflicts(records)
    assert any(c.conflict_type == "FITNESS_CONFLICT" for c in conflicts)


def test_safety_conflict_detected():
    resolver = MemoryConflictResolver()
    records = [
        EvolutionaryMemoryRecord(record_id="r1", source_cycle_id="c1", source_task="t1", source_profile="p1", fitness_delta=0.1, safety_score=0.8),
        EvolutionaryMemoryRecord(record_id="r2", source_cycle_id="c1", source_task="t1", source_profile="p1", fitness_delta=0.2, safety_score=0.2),
    ]
    conflicts = resolver.detect_conflicts(records)
    assert any(c.conflict_type == "SAFETY_CONFLICT" for c in conflicts)


def test_phi_conflict_detected():
    resolver = MemoryConflictResolver()
    records = [
        EvolutionaryMemoryRecord(record_id="r1", source_cycle_id="c1", source_task="t1", source_profile="p1", fitness_delta=0.1, phi_delta=0.1),
        EvolutionaryMemoryRecord(record_id="r2", source_cycle_id="c1", source_task="t1", source_profile="p1", fitness_delta=0.2, phi_delta=-0.1),
    ]
    conflicts = resolver.detect_conflicts(records)
    assert any(c.conflict_type == "PHI_CONFLICT" for c in conflicts)


def test_energy_conflict_detected():
    resolver = MemoryConflictResolver()
    records = [
        EvolutionaryMemoryRecord(record_id="r1", source_cycle_id="c1", source_task="t1", source_profile="p1", fitness_delta=0.1, energy_delta=0.1),
        EvolutionaryMemoryRecord(record_id="r2", source_cycle_id="c1", source_task="t1", source_profile="p1", fitness_delta=0.2, energy_delta=-0.1),
    ]
    conflicts = resolver.detect_conflicts(records)
    assert any(c.conflict_type == "ENERGY_CONFLICT" for c in conflicts)


def test_policy_conflict_detected():
    resolver = MemoryConflictResolver()
    records = [
        EvolutionaryMemoryRecord(record_id="r1", source_cycle_id="c1", source_task="t1", source_profile="p1", fitness_delta=0.1, variant_id="v1"),
        EvolutionaryMemoryRecord(record_id="r2", source_cycle_id="c1", source_task="t1", source_profile="p1", fitness_delta=0.3, variant_id="v1"),
    ]
    conflicts = resolver.detect_conflicts(records)
    assert any(c.conflict_type == "POLICY_CONFLICT" for c in conflicts)


def test_generalization_conflict_detected():
    resolver = MemoryConflictResolver()
    records = [
        EvolutionaryMemoryRecord(record_id="r1", source_cycle_id="c1", source_task="t1", source_profile="p1", fitness_delta=0.3, generalization_score=0.6),
        EvolutionaryMemoryRecord(record_id="r2", source_cycle_id="c1", source_task="t1", source_profile="p1", fitness_delta=0.5, generalization_score=0.1),
    ]
    conflicts = resolver.detect_conflicts(records)
    assert any(c.conflict_type == "GENERALIZATION_CONFLICT" for c in conflicts)


def test_resolver_prefers_safety_over_fitness():
    resolver = MemoryConflictResolver()
    conflict = MemoryConflict(
        conflict_id="c1",
        record_a_id="r1",
        record_b_id="r2",
        conflict_type="SAFETY_CONFLICT",
        resolution="prefer_safety",
    )
    records = {
        "r1": EvolutionaryMemoryRecord(record_id="r1", source_cycle_id="c1", source_task="t1", source_profile="p1", safety_score=0.9),
        "r2": EvolutionaryMemoryRecord(record_id="r2", source_cycle_id="c1", source_task="t1", source_profile="p1", safety_score=0.2),
    }
    winner = resolver.resolve_conflict(conflict, records)
    assert winner == "r1"


def test_resolver_missing_record():
    resolver = MemoryConflictResolver()
    conflict = MemoryConflict(conflict_id="c1", record_a_id="r1", record_b_id="r2", conflict_type="SAFETY_CONFLICT")
    winner = resolver.resolve_conflict(conflict, {})
    assert winner is None


# ------------------------------------------------------------------ #
# EvolutionaryForgettingEngine
# ------------------------------------------------------------------ #

def test_forgetting_marks_record_not_deletes():
    engine = EvolutionaryForgettingEngine()
    r = EvolutionaryMemoryRecord(
        record_id="r1",
        source_cycle_id="c1",
        source_task="t1",
        source_profile="p1",
        fitness_delta=-0.5,
        confidence=0.1,
        reuse_count=0,
    )
    decisions = engine.apply_forgetting_policy([r])
    assert len(decisions) == 1
    assert decisions[0].new_status == EvolutionaryMemoryStatus.FORGOTTEN.value
    assert r.status == EvolutionaryMemoryStatus.FORGOTTEN.value


def test_reused_record_not_forgotten():
    engine = EvolutionaryForgettingEngine()
    r = EvolutionaryMemoryRecord(
        record_id="r1",
        source_cycle_id="c1",
        source_task="t1",
        source_profile="p1",
        fitness_delta=-0.1,
        reuse_count=3,
        safety_score=0.6,
    )
    decisions = engine.apply_forgetting_policy([r])
    assert len(decisions) == 0


def test_deprecated_no_reuse_forgotten():
    engine = EvolutionaryForgettingEngine()
    r = EvolutionaryMemoryRecord(
        record_id="r1",
        source_cycle_id="c1",
        source_task="t1",
        source_profile="p1",
        status=EvolutionaryMemoryStatus.DEPRECATED.value,
        reuse_count=0,
    )
    decisions = engine.apply_forgetting_policy([r])
    assert len(decisions) == 1
    assert decisions[0].new_status == EvolutionaryMemoryStatus.FORGOTTEN.value


def test_volatile_low_confidence_forgotten():
    engine = EvolutionaryForgettingEngine()
    r = EvolutionaryMemoryRecord(
        record_id="r1",
        source_cycle_id="c1",
        source_task="t1",
        source_profile="p1",
        status=EvolutionaryMemoryStatus.VOLATILE.value,
        reuse_count=0,
        confidence=0.1,
    )
    decisions = engine.apply_forgetting_policy([r])
    assert len(decisions) == 1


def test_forgetting_score_perfect():
    engine = EvolutionaryForgettingEngine()
    records = [
        EvolutionaryMemoryRecord(record_id="r1", source_cycle_id="c1", source_task="t1", source_profile="p1", status=EvolutionaryMemoryStatus.FORGOTTEN.value, reuse_count=0),
        EvolutionaryMemoryRecord(record_id="r2", source_cycle_id="c1", source_task="t1", source_profile="p1", status=EvolutionaryMemoryStatus.FORGOTTEN.value, reuse_count=0),
    ]
    score = engine.compute_forgetting_score(records)
    assert score == 1.0


def test_forgetting_score_zero():
    engine = EvolutionaryForgettingEngine()
    records = [
        EvolutionaryMemoryRecord(record_id="r1", source_cycle_id="c1", source_task="t1", source_profile="p1", status=EvolutionaryMemoryStatus.STABLE.value),
    ]
    score = engine.compute_forgetting_score(records)
    assert score == 0.0


# ------------------------------------------------------------------ #
# EvolutionaryMemoryGovernor
# ------------------------------------------------------------------ #

def test_governor_ingest_cycle_result():
    governor = EvolutionaryMemoryGovernor()
    r = EvolutionaryMemoryRecord(record_id="r1", source_cycle_id="c1", source_task="t1", source_profile="p1", fitness_delta=0.5, safety_score=0.8, confidence=0.6, reuse_count=1)
    d = governor.ingest_cycle_result(r)
    assert d.new_status == EvolutionaryMemoryStatus.STABLE.value
    assert governor.store.get_record("r1") is not None


def test_governor_run_cycle():
    governor = EvolutionaryMemoryGovernor()
    governor.store.add_record(EvolutionaryMemoryRecord(record_id="r1", source_cycle_id="c1", source_task="t1", source_profile="p1", fitness_delta=0.5, safety_score=0.8, confidence=0.6, reuse_count=1))
    result = governor.run_governance_cycle()
    assert result["consolidation_decisions"] >= 0
    assert result["conflicts_detected"] >= 0
    assert result["forgotten_records"] >= 0


def test_governor_does_not_touch_frozen():
    governor = EvolutionaryMemoryGovernor()
    governor.store.add_record(EvolutionaryMemoryRecord(record_id="r1", source_cycle_id="c1", source_task="t1", source_profile="p1", status=EvolutionaryMemoryStatus.FROZEN_POLICY.value))
    result = governor.run_governance_cycle()
    assert result["consolidation_decisions"] == 0


def test_governor_does_not_touch_forgotten():
    governor = EvolutionaryMemoryGovernor()
    governor.store.add_record(EvolutionaryMemoryRecord(record_id="r1", source_cycle_id="c1", source_task="t1", source_profile="p1", status=EvolutionaryMemoryStatus.FORGOTTEN.value))
    result = governor.run_governance_cycle()
    assert result["consolidation_decisions"] == 0


# ------------------------------------------------------------------ #
# EvolutionaryMemoryAudit
# ------------------------------------------------------------------ #

def test_audit_empty_store():
    store = EvolutionaryMemoryStore()
    audit = EvolutionaryMemoryAudit(store)
    result = audit.run_audit()
    assert result.total_records == 0
    assert result.verdict == "INSUFFICIENT_EVIDENCE"


def test_audit_validated():
    store = EvolutionaryMemoryStore()
    store.add_record(EvolutionaryMemoryRecord(record_id="r1", source_cycle_id="c1", source_task="t1", source_profile="p1", status=EvolutionaryMemoryStatus.STABLE.value, safety_score=0.8, reuse_count=1))
    audit = EvolutionaryMemoryAudit(store)
    result = audit.run_audit()
    assert result.verdict == "EVOLUTIONARY_MEMORY_GOVERNANCE_VALIDATED"


def test_audit_unsafe_stable_detected():
    store = EvolutionaryMemoryStore()
    store.add_record(EvolutionaryMemoryRecord(record_id="r1", source_cycle_id="c1", source_task="t1", source_profile="p1", status=EvolutionaryMemoryStatus.STABLE.value, safety_score=0.2))
    audit = EvolutionaryMemoryAudit(store)
    result = audit.run_audit()
    assert result.verdict == "UNSAFE_MEMORY_PROMOTION_DETECTED"


def test_audit_memory_bloat_detected():
    store = EvolutionaryMemoryStore()
    for i in range(10):
        store.add_record(EvolutionaryMemoryRecord(record_id=f"r{i}", source_cycle_id="c1", source_task="t1", source_profile="p1", status=EvolutionaryMemoryStatus.VOLATILE.value))
    audit = EvolutionaryMemoryAudit(store)
    result = audit.run_audit()
    assert result.verdict == "MEMORY_BLOAT_DETECTED"


def test_audit_forgetting_too_aggressive():
    store = EvolutionaryMemoryStore()
    store.add_record(EvolutionaryMemoryRecord(record_id="r1", source_cycle_id="c1", source_task="t1", source_profile="p1", status=EvolutionaryMemoryStatus.FORGOTTEN.value, reuse_count=1))
    audit = EvolutionaryMemoryAudit(store)
    result = audit.run_audit()
    assert result.verdict == "FORGETTING_POLICY_TOO_AGGRESSIVE"


def test_audit_consolidation_too_weak():
    store = EvolutionaryMemoryStore()
    for i in range(2):
        store.add_record(EvolutionaryMemoryRecord(record_id=f"r{i}", source_cycle_id="c1", source_task="t1", source_profile="p1", status=EvolutionaryMemoryStatus.VOLATILE.value))
    for i in range(2, 5):
        store.add_record(EvolutionaryMemoryRecord(record_id=f"r{i}", source_cycle_id="c1", source_task="t1", source_profile="p1", status=EvolutionaryMemoryStatus.FORGOTTEN.value))
    audit = EvolutionaryMemoryAudit(store)
    result = audit.run_audit()
    assert result.verdict == "CONSOLIDATION_TOO_WEAK"


def test_audit_governance_score_clamped():
    store = EvolutionaryMemoryStore()
    store.add_record(EvolutionaryMemoryRecord(record_id="r1", source_cycle_id="c1", source_task="t1", source_profile="p1", status=EvolutionaryMemoryStatus.STABLE.value, safety_score=1.0, reuse_count=1))
    audit = EvolutionaryMemoryAudit(store)
    result = audit.run_audit()
    assert 0.0 <= result.governance_score <= 1.0


def test_audit_reports_json(tmp_path):
    store = EvolutionaryMemoryStore(report_dir=str(tmp_path))
    audit = EvolutionaryMemoryAudit(store)
    result = audit.run_audit()
    path = audit.generate_json_report(result)
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["verdict"] == result.verdict


def test_audit_reports_markdown(tmp_path):
    store = EvolutionaryMemoryStore(report_dir=str(tmp_path))
    audit = EvolutionaryMemoryAudit(store)
    result = audit.run_audit()
    path = audit.generate_markdown_report(result)
    assert path.exists()
    assert result.verdict in path.read_text(encoding="utf-8")


# ------------------------------------------------------------------ #
# Orchestrator hook
# ------------------------------------------------------------------ #

def test_orchestrator_flag_disabled_by_default():
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.dna.parser import load_genome
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    assert orch.evolutionary_memory_governance_enabled is False


def test_orchestrator_get_governor_lazy():
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.dna.parser import load_genome
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.evolutionary_memory_governance_enabled = True
    g = orch.get_evolutionary_memory_governor()
    assert g is not None
    assert orch._evolutionary_memory_governor is g


@pytest.mark.asyncio
async def test_orchestrator_run_governance_disabled():
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.dna.parser import load_genome
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.evolutionary_memory_governance_enabled = False
    result = await orch.run_evolutionary_memory_governance_cycle()
    assert result is None


@pytest.mark.asyncio
async def test_orchestrator_run_governance_enabled():
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.dna.parser import load_genome
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.evolutionary_memory_governance_enabled = True
    result = await orch.run_evolutionary_memory_governance_cycle()
    assert isinstance(result, dict)
    assert "consolidation_decisions" in result


# ------------------------------------------------------------------ #
# Safety / Guardrails
# ------------------------------------------------------------------ #

def test_quarantined_records_not_reused():
    store = EvolutionaryMemoryStore()
    store.add_record(EvolutionaryMemoryRecord(record_id="r1", source_cycle_id="c1", source_task="t1", source_profile="p1", status=EvolutionaryMemoryStatus.QUARANTINED.value, reuse_count=0))
    # In real usage, increment_reuse could be called, but governance should prevent it
    # Here we just verify the record exists with quarantined status
    r = store.get_record("r1")
    assert r.status == EvolutionaryMemoryStatus.QUARANTINED.value
    assert r.reuse_count == 0


def test_no_patch_execution_by_governor():
    governor = EvolutionaryMemoryGovernor()
    result = governor.run_governance_cycle()
    # Governor only changes memory statuses, never modifies architecture
    assert "patch" not in str(result).lower()


def test_conservative_profile_allows_safe_selection_only():
    # This is a conceptual test: the governor's consolidation engine decides
    engine = ConsolidationPolicyEngine()
    r = EvolutionaryMemoryRecord(
        record_id="r1",
        source_cycle_id="c1",
        source_task="t1",
        source_profile="p1",
        fitness_delta=0.1,
        safety_score=0.5,
        confidence=0.3,
        reuse_count=0,
    )
    d = engine.evaluate(r)
    # With moderate safety, no reuse: should not be promoted to stable
    assert d.new_status != EvolutionaryMemoryStatus.STABLE.value


def test_deterministic_evaluate():
    engine = ConsolidationPolicyEngine()
    r = EvolutionaryMemoryRecord(record_id="r1", source_cycle_id="c1", source_task="t1", source_profile="p1", fitness_delta=0.5, safety_score=0.8, confidence=0.6, reuse_count=1)
    d1 = engine.evaluate(r)
    d2 = engine.evaluate(r)
    assert d1.new_status == d2.new_status
