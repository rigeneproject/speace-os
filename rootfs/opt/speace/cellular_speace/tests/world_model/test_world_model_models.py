import pytest
from speace_core.cellular_brain.world_model.world_model_models import (
    CausalLink,
    CausalSimulationResult,
    ImpactAssessment,
    WorldConstraint,
    WorldEntity,
    WorldEntityType,
    WorldModelAuditProfile,
    WorldModelAuditResult,
    WorldModelAuditSuiteResult,
    WorldModelSnapshot,
    WorldScenario,
    WorldZone,
)


def test_world_entity_creation():
    e = WorldEntity(entity_id="e1", entity_type=WorldEntityType.ENVIRONMENT, name="test")
    assert e.entity_id == "e1"
    assert e.confidence == 1.0
    assert e.uncertainty == 0.0


def test_world_zone_creation():
    z = WorldZone(zone_id="z1", name="zone1", entities=["e1", "e2"])
    assert z.zone_id == "z1"
    assert len(z.entities) == 2


def test_world_constraint_creation():
    c = WorldConstraint(constraint_id="c1", name="limit", severity=0.8, hard_constraint=True)
    assert c.hard_constraint is True
    assert c.severity == 0.8


def test_causal_link_creation():
    l = CausalLink(link_id="l1", source_entity_id="a", target_entity_id="b")
    assert l.relation_type == "influences"
    assert l.strength == 0.5


def test_world_model_snapshot_creation():
    s = WorldModelSnapshot(snapshot_id="s1", timestamp="2024-01-01T00:00:00")
    assert s.global_coherence_score == 1.0
    assert s.global_risk_score == 0.0


def test_world_scenario_creation():
    sc = WorldScenario(scenario_id="sc1", initial_state_id="s1", horizon_ticks=3)
    assert sc.horizon_ticks == 3


def test_causal_simulation_result_defaults():
    r = CausalSimulationResult(scenario_id="sc1")
    assert r.safe_to_publish_read_only is True
    assert r.predicted_coherence_score == 1.0


def test_impact_assessment_defaults():
    ia = ImpactAssessment(assessment_id="ia1", scenario_id="sc1")
    assert ia.reversible is True
    assert ia.requires_human_review is False
    assert ia.allowed_as_simulation_only is True


def test_world_model_audit_result_defaults():
    ar = WorldModelAuditResult(profile_name="p1")
    assert ar.verdict == "EXTERNAL_WORLD_MODEL_INSUFFICIENT_EVIDENCE"


def test_world_model_audit_suite_defaults():
    su = WorldModelAuditSuiteResult()
    assert su.aggregate_verdict == "EXTERNAL_WORLD_MODEL_INSUFFICIENT_EVIDENCE"
    assert su.proceed_to_t61b is False


def test_world_model_audit_profile_defaults():
    p = WorldModelAuditProfile(name="p1")
    assert p.scenario_type == "baseline"
    assert p.duration_ticks == 5


def test_world_entity_type_enum():
    assert WorldEntityType.ENVIRONMENT == "environment"
    assert WorldEntityType.UNKNOWN == "unknown"
