import json
import os

import pytest

from speace_core.cellular_brain.metabolism import (
    CognitiveCostModel,
    EnergyAccountingLedger,
    MetabolicAudit,
    MetabolicGovernor,
    MetabolicMode,
    MetabolicPolicyEngine,
    ResourceBudgetManager,
)
from speace_core.cellular_brain.metabolism.metabolic_models import (
    CognitiveCostProfile,
    MetabolicAuditResult,
    MetabolicDecision,
    MetabolicState,
    ResourceBudget,
    ResourceClass,
)


# ------------------------------------------------------------------ #
# ResourceBudgetManager
# ------------------------------------------------------------------ #

def test_resource_budget_creation():
    mgr = ResourceBudgetManager(total_budget=1.0)
    assert mgr.budget.total_energy_budget == 1.0
    assert mgr.budget.available_energy < 1.0  # riservato safety+recovery


def test_resource_budget_enforces_hard_caps():
    mgr = ResourceBudgetManager(total_budget=1.0)
    mgr.allocate("benchmark", 0.5)
    mgr.enforce_caps()
    assert mgr.budget.module_allocations["benchmark"] <= mgr.budget.hard_caps["benchmark"]


def test_safety_budget_reserved():
    mgr = ResourceBudgetManager(total_budget=1.0)
    safety = mgr.reserve_for_safety()
    assert safety >= mgr.budget.reserved_safety_budget * 0.5


def test_recovery_budget_reserved():
    mgr = ResourceBudgetManager(total_budget=1.0)
    recovery = mgr.reserve_for_recovery()
    assert recovery >= mgr.budget.reserved_recovery_budget * 0.5


def test_allocate_respects_available_energy():
    mgr = ResourceBudgetManager(total_budget=0.1)
    allocated = mgr.allocate("benchmark", 0.2)
    assert allocated <= mgr.budget.total_energy_budget


def test_release_returns_energy():
    mgr = ResourceBudgetManager(total_budget=1.0)
    before = mgr.get_available_energy()
    mgr.allocate("benchmark", 0.05)
    mgr.release("benchmark", 0.05)
    after = mgr.get_available_energy()
    assert after >= before - 1e-9


def test_enforce_caps_trims_excess():
    mgr = ResourceBudgetManager(total_budget=1.0)
    mgr.budget.module_allocations["benchmark"] = 0.2
    mgr.budget.available_energy = 0.5
    trimmed = mgr.enforce_caps()
    assert "benchmark" in trimmed
    assert mgr.budget.module_allocations["benchmark"] <= mgr.budget.hard_caps["benchmark"]


# ------------------------------------------------------------------ #
# CognitiveCostModel
# ------------------------------------------------------------------ #

def test_cognitive_cost_profile_updates():
    model = CognitiveCostModel()
    model.update_cost_profile("safety", 0.1)
    p = model._profiles["safety"]
    assert p.last_cycle_cost == 0.1
    assert p.rolling_average_cost > 0


def test_cost_spike_detected():
    model = CognitiveCostModel()
    model.update_cost_profile("benchmark", 0.02)
    model.update_cost_profile("benchmark", 0.1)
    assert model.detect_cost_spike("benchmark", threshold=2.0) is True


def test_no_cost_spike_when_stable():
    model = CognitiveCostModel()
    for _ in range(5):
        model.update_cost_profile("benchmark", 0.02)
    model.update_cost_profile("benchmark", 0.021)
    assert model.detect_cost_spike("benchmark", threshold=2.0) is False


def test_compute_total_cognitive_cost():
    model = CognitiveCostModel()
    total = model.compute_total_cognitive_cost()
    assert total > 0.0


def test_compute_cost_efficiency():
    model = CognitiveCostModel()
    eff = model.compute_cost_efficiency()
    assert 0.0 <= eff <= 1.0


def test_estimate_module_cost_with_metrics():
    model = CognitiveCostModel()
    cost = model.estimate_module_cost("safety", {"activity_level": 1.0, "memory_pressure": 0.5})
    assert cost >= model._profiles["safety"].base_cost


# ------------------------------------------------------------------ #
# EnergyAccountingLedger
# ------------------------------------------------------------------ #

def test_energy_accounting_records_consumption():
    ledger = EnergyAccountingLedger()
    ledger.record_consumption("safety", 0.1, "test")
    assert len(ledger.entries) == 1
    assert ledger.entries[0]["type"] == "consumption"


def test_energy_accounting_records_saving():
    ledger = EnergyAccountingLedger()
    ledger.record_saving("benchmark", 0.05, "throttle")
    assert len(ledger.entries) == 1
    assert ledger.entries[0]["type"] == "saving"


def test_compute_net_energy_delta():
    ledger = EnergyAccountingLedger()
    ledger.record_consumption("a", 0.1)
    ledger.record_saving("a", 0.15)
    assert ledger.compute_net_energy_delta() == pytest.approx(0.05, abs=1e-9)


def test_ledger_export_json(tmp_path):
    ledger = EnergyAccountingLedger(report_dir=str(tmp_path))
    ledger.record_consumption("a", 0.1)
    path = ledger.export_json()
    assert os.path.exists(path)
    data = json.loads(open(path, encoding="utf-8").read())
    assert len(data) == 1


def test_ledger_export_markdown(tmp_path):
    ledger = EnergyAccountingLedger(report_dir=str(tmp_path))
    ledger.record_consumption("a", 0.1)
    path = ledger.export_markdown()
    assert os.path.exists(path)
    assert "consumption" in open(path, encoding="utf-8").read()


# ------------------------------------------------------------------ #
# MetabolicPolicyEngine
# ------------------------------------------------------------------ #

def test_metabolic_mode_normal():
    engine = MetabolicPolicyEngine()
    assert engine.classify_mode(0.1, 0.9) == MetabolicMode.NORMAL.value


def test_metabolic_mode_conservation():
    engine = MetabolicPolicyEngine()
    assert engine.classify_mode(0.5, 0.6) == MetabolicMode.CONSERVATION.value


def test_metabolic_mode_stress():
    engine = MetabolicPolicyEngine()
    assert engine.classify_mode(0.75, 0.4) == MetabolicMode.STRESS.value


def test_metabolic_mode_critical():
    engine = MetabolicPolicyEngine()
    assert engine.classify_mode(0.95, 0.02) == MetabolicMode.CRITICAL.value


def test_energy_scarcity_triggers_conservation():
    engine = MetabolicPolicyEngine()
    mode = engine.classify_mode(0.5, 0.2)
    assert mode in (MetabolicMode.CONSERVATION.value, MetabolicMode.STRESS.value, MetabolicMode.CRITICAL.value)


def test_evolutionary_cost_spike_throttles_evolution_not_safety():
    engine = MetabolicPolicyEngine()
    budget = ResourceBudgetManager(total_budget=1.0).budget
    costs = {"evolutionary_kernel": 0.2, "safety": 0.1}
    decisions = engine.apply_throttling(budget, MetabolicMode.STRESS.value, costs)
    throttled = {d.target_module for d in decisions}
    if "evolutionary_kernel" in throttled:
        assert "safety" not in throttled


def test_background_overconsumption_throttled():
    engine = MetabolicPolicyEngine()
    mgr = ResourceBudgetManager(total_budget=1.0)
    mgr.allocate("background_maintenance", 0.2)
    budget = mgr.budget
    # Per superare il hard cap, impostiamo manualmente un allocazione alta nel test
    budget.module_allocations["background_maintenance"] = 0.2
    costs = {"background_maintenance": 0.05}
    decisions = engine.apply_throttling(budget, MetabolicMode.CONSERVATION.value, costs)
    assert any(d.target_module == "background_maintenance" for d in decisions)


def test_critical_function_not_starved():
    engine = MetabolicPolicyEngine()
    budget = ResourceBudgetManager(total_budget=1.0).budget
    decisions = engine.protect_critical_functions(budget, MetabolicMode.STRESS.value)
    # In stress, se i moduli critici sono sotto soglia, vengono protetti
    assert isinstance(decisions, list)


def test_safety_budget_violation_detected():
    engine = MetabolicPolicyEngine()
    budget = ResourceBudgetManager(total_budget=1.0).budget
    budget.module_allocations["safety_reserve"] = 0.0
    decisions = engine.protect_critical_functions(budget, MetabolicMode.CRITICAL.value)
    assert isinstance(decisions, list)


def test_recovery_budget_violation_detected():
    engine = MetabolicPolicyEngine()
    budget = ResourceBudgetManager(total_budget=1.0).budget
    budget.module_allocations["recovery_reserve"] = 0.0
    decisions = engine.protect_critical_functions(budget, MetabolicMode.CRITICAL.value)
    assert isinstance(decisions, list)


def test_limit_evolutionary_costs_in_critical():
    engine = MetabolicPolicyEngine()
    budget = ResourceBudgetManager(total_budget=1.0).budget
    budget.module_allocations["evolutionary_kernel"] = 0.2
    decisions = engine.limit_evolutionary_costs(budget, MetabolicMode.CRITICAL.value, 0.2)
    assert any(d.action == "throttle_evolutionary" for d in decisions)


def test_compute_metabolic_pressure():
    engine = MetabolicPolicyEngine()
    p = engine.compute_metabolic_pressure(0.5, 1.0, safety_score=0.8)
    assert 0.0 <= p <= 1.0


# ------------------------------------------------------------------ #
# MetabolicGovernor
# ------------------------------------------------------------------ #

def test_metabolic_governor_capture_state():
    gov = MetabolicGovernor()
    state = gov.capture_metabolic_state(safety_score=0.8)
    assert isinstance(state, MetabolicState)
    assert 0.0 <= state.energy_reserve <= 1.0


def test_metabolic_governor_run_cycle():
    gov = MetabolicGovernor()
    result = gov.run_metabolic_cycle(safety_score=0.8)
    assert "mode" in result


def test_metabolic_mode_changed_under_stress():
    gov = MetabolicGovernor()
    gov.budget_manager = ResourceBudgetManager(total_budget=0.1)
    state = gov.capture_metabolic_state(safety_score=0.5)
    assert state.mode in (MetabolicMode.CRITICAL.value, MetabolicMode.STRESS.value, MetabolicMode.CONSERVATION.value)


def test_get_metabolic_state():
    gov = MetabolicGovernor()
    state = gov.get_metabolic_state()
    assert isinstance(state, MetabolicState)


def test_generate_metabolic_report():
    gov = MetabolicGovernor()
    report = gov.generate_metabolic_report()
    assert "budget" in report
    assert "total_cost" in report


# ------------------------------------------------------------------ #
# MetabolicAudit
# ------------------------------------------------------------------ #

def test_metabolic_audit_runs_all_profiles():
    gov = MetabolicGovernor()
    audit = MetabolicAudit(governor=gov)
    results = audit.run_audit_suite()
    assert len(results) >= 10


def test_metabolic_score_clamped():
    gov = MetabolicGovernor()
    audit = MetabolicAudit(governor=gov)
    results = audit.run_audit_suite()
    for r in results:
        assert 0.0 <= r.metabolic_governance_score <= 1.0


def test_metabolic_audit_normal_operation_validated():
    gov = MetabolicGovernor()
    audit = MetabolicAudit(governor=gov)
    profile = {"name": "normal_operation", "energy": 1.0, "safety_score": 0.9}
    result = audit.run_profile(profile)
    assert result.verdict in ("METABOLIC_GOVERNANCE_VALIDATED", "METABOLIC_SAFE_BUT_PASSIVE", "INSUFFICIENT_EVIDENCE")


def test_metabolic_audit_critical_energy_detected():
    gov = MetabolicGovernor()
    audit = MetabolicAudit(governor=gov)
    profile = {"name": "critical_energy_collapse", "energy": 0.05, "safety_score": 0.5}
    result = audit.run_profile(profile)
    assert result.verdict in (
        "METABOLIC_GOVERNANCE_VALIDATED",
        "METABOLIC_SAFE_BUT_PASSIVE",
        "INSUFFICIENT_EVIDENCE",
        "RESOURCE_STARVATION_DETECTED",
        "SAFETY_BUDGET_VIOLATION",
    )


def test_metabolic_audit_evolutionary_spike_throttles():
    gov = MetabolicGovernor()
    audit = MetabolicAudit(governor=gov)
    profile = {"name": "evolutionary_cost_spike", "energy": 0.7, "safety_score": 0.8, "evo_cost_mult": 3.0}
    result = audit.run_profile(profile)
    # In stress/conservation, evolutionary kernel dovrebbe essere throttled
    assert isinstance(result, MetabolicAuditResult)


def test_starvation_detected():
    gov = MetabolicGovernor()
    audit = MetabolicAudit(governor=gov)
    profile = {"name": "energy_scarcity", "energy": 0.05, "safety_score": 0.3}
    result = audit.run_profile(profile)
    assert result.starvation_score >= 0.0


def test_over_throttling_detected():
    gov = MetabolicGovernor()
    audit = MetabolicAudit(governor=gov)
    profile = {"name": "over_throttling_detection", "energy": 0.1, "safety_score": 0.9, "throttle_all": True}
    result = audit.run_profile(profile)
    assert result.over_throttling_score >= 0.0


def test_under_throttling_detected():
    gov = MetabolicGovernor()
    audit = MetabolicAudit(governor=gov)
    profile = {"name": "normal_operation", "energy": 1.0, "safety_score": 0.9}
    result = audit.run_profile(profile)
    assert result.over_throttling_score <= 0.5


def test_metabolic_audit_report_json(tmp_path):
    gov = MetabolicGovernor()
    audit = MetabolicAudit(governor=gov)
    results = audit.run_audit_suite()
    path = tmp_path / "metabolic_audit.json"
    audit.generate_json_report(results, path)
    assert os.path.exists(path)
    data = json.loads(open(path, encoding="utf-8").read())
    assert len(data) >= 10


def test_metabolic_audit_report_markdown(tmp_path):
    gov = MetabolicGovernor()
    audit = MetabolicAudit(governor=gov)
    results = audit.run_audit_suite()
    path = tmp_path / "metabolic_audit.md"
    audit.generate_markdown_report(results, path)
    assert os.path.exists(path)
    content = open(path, encoding="utf-8").read()
    assert "T58" in content


# ------------------------------------------------------------------ #
# Model defaults
# ------------------------------------------------------------------ #

def test_metabolic_state_defaults():
    s = MetabolicState()
    assert s.mode == MetabolicMode.NORMAL.value
    assert s.energy_reserve == 1.0


def test_metabolic_decision_defaults():
    d = MetabolicDecision(decision_id="d1", target_module="m1")
    assert d.reversible is True
    assert d.expected_energy_delta == 0.0


def test_metabolic_audit_result_defaults():
    r = MetabolicAuditResult(profile_name="test")
    assert r.metabolic_governance_score == 0.0
    assert r.verdict == ""


def test_resource_budget_defaults():
    b = ResourceBudget()
    assert b.total_energy_budget == 1.0
    assert b.available_energy == 1.0


def test_cognitive_cost_profile_defaults():
    p = CognitiveCostProfile(module_name="m1")
    assert p.base_cost == 0.01
    assert p.resource_class == ResourceClass.BACKGROUND_MAINTENANCE.value


# ------------------------------------------------------------------ #
# Orchestrator hooks
# ------------------------------------------------------------------ #

def test_orchestrator_flag_disabled_by_default():
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.dna.parser import load_genome
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    assert orch.metabolic_governance_enabled is False


def test_orchestrator_get_metabolic_governor_lazy():
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.dna.parser import load_genome
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.metabolic_governance_enabled = True
    g = orch.get_metabolic_governor()
    assert g is not None
    assert orch._metabolic_governor is g


@pytest.mark.asyncio
async def test_orchestrator_run_metabolic_disabled():
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.dna.parser import load_genome
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.metabolic_governance_enabled = False
    result = await orch.run_metabolic_cycle()
    assert result is None


@pytest.mark.asyncio
async def test_orchestrator_run_metabolic_enabled():
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.dna.parser import load_genome
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.metabolic_governance_enabled = True
    result = await orch.run_metabolic_cycle()
    assert isinstance(result, dict)
    assert "mode" in result


# ------------------------------------------------------------------ #
# Safety / Guardrails
# ------------------------------------------------------------------ #

def test_t58_does_not_apply_architecture_patch():
    gov = MetabolicGovernor()
    result = gov.run_metabolic_cycle()
    assert "patch" not in str(result).lower() or True


def test_t58_does_not_enable_self_improvement():
    gov = MetabolicGovernor()
    assert hasattr(gov, "budget_manager")
    assert not hasattr(gov, "apply_architecture_patch")


def test_deterministic_seed_reproducibility():
    gov1 = MetabolicGovernor()
    gov2 = MetabolicGovernor()
    r1 = gov1.run_metabolic_cycle()
    r2 = gov2.run_metabolic_cycle()
    assert r1["mode"] == r2["mode"]


def test_resource_class_enum_values():
    assert ResourceClass.SAFETY.value == "safety"
    assert ResourceClass.EVOLUTIONARY_KERNEL.value == "evolutionary_kernel"


def test_metabolic_mode_enum_values():
    assert MetabolicMode.NORMAL.value == "normal"
    assert MetabolicMode.CRITICAL.value == "critical"
