"""Tests for T134 — Cognitive Evolution Runtime Audit and T135 — Cognitive Skill Library."""

import time
from typing import Any, Dict

import pytest

from speace_core.cellular_brain.cognitive_evolution import (
    CognitiveEvolutionRuntimeAudit,
    CognitivePatchProposalBuilder,
    CognitiveSelfModificationProposal,
    CognitiveSkill,
    CognitiveSkillLibrary,
    CognitiveSkillRegistry,
    EvolutionarySkillOptimizer,
)


# --------------------------------------------------------------------------- #
# T134 — CognitiveEvolutionRuntimeAudit
# --------------------------------------------------------------------------- #

def test_t134_full_audit_all_scenarios_pass(tmp_path):
    reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
    builder = CognitivePatchProposalBuilder(data_root=str(tmp_path / "ce"))
    t133 = CognitiveSelfModificationProposal(registry=reg, proposal_builder=builder)
    audit = CognitiveEvolutionRuntimeAudit(
        registry=reg,
        proposal_builder=builder,
        t133=t133,
    )
    report = audit.run_full_audit()
    assert report["all_passed"] is True
    assert len(report["scenarios"]) == 10
    for i in range(1, 11):
        assert report["scenarios"][f"scenario_{i}"]["passed"] is True


def test_t134_scenario_1_generate_variant(tmp_path):
    reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
    audit = CognitiveEvolutionRuntimeAudit(registry=reg)
    sc1 = audit._audit_generate_variant()
    assert sc1["passed"] is True
    assert "evolve_result" in sc1
    assert "proposal_id" in sc1["evolve_result"]


def test_t134_scenario_5_no_auto_apply(tmp_path):
    reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
    builder = CognitivePatchProposalBuilder(data_root=str(tmp_path / "ce"))
    audit = CognitiveEvolutionRuntimeAudit(registry=reg, proposal_builder=builder)
    sc1 = audit._audit_generate_variant()
    sc2 = audit._audit_sandbox_trial(sc1)
    sc3 = audit._audit_fitness_evaluation(sc2)
    sc4 = audit._audit_create_proposal(sc3)
    sc5 = audit._audit_no_auto_apply(sc4)
    assert sc5["passed"] is True


def test_t134_scenario_6_7_manual_approve_and_snapshot(tmp_path):
    reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
    builder = CognitivePatchProposalBuilder(data_root=str(tmp_path / "ce"))
    t133 = CognitiveSelfModificationProposal(registry=reg, proposal_builder=builder)
    audit = CognitiveEvolutionRuntimeAudit(
        registry=reg, proposal_builder=builder, t133=t133
    )
    sc1 = audit._audit_generate_variant()
    sc2 = audit._audit_sandbox_trial(sc1)
    sc3 = audit._audit_fitness_evaluation(sc2)
    sc4 = audit._audit_create_proposal(sc3)
    sc6 = audit._audit_manual_approve(sc4)
    assert sc6["passed"] is True
    sc7 = audit._audit_snapshot_and_apply(sc6)
    assert sc7["passed"] is True


def test_t134_scenario_8_9_auto_rollback(tmp_path):
    reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
    builder = CognitivePatchProposalBuilder(data_root=str(tmp_path / "ce"))
    t133 = CognitiveSelfModificationProposal(registry=reg, proposal_builder=builder)
    audit = CognitiveEvolutionRuntimeAudit(
        registry=reg, proposal_builder=builder, t133=t133
    )
    sc1 = audit._audit_generate_variant()
    sc2 = audit._audit_sandbox_trial(sc1)
    sc3 = audit._audit_fitness_evaluation(sc2)
    sc4 = audit._audit_create_proposal(sc3)
    sc6 = audit._audit_manual_approve(sc4)
    sc8 = audit._audit_simulate_regression(sc6)
    if not sc8["passed"]:
        print(f"DEBUG sc8: {sc8}")
    assert sc8["passed"] is True
    sc9 = audit._audit_auto_rollback(sc8)
    assert sc9["passed"] is True


def test_t134_scenario_10_immutable_blocked(tmp_path):
    reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
    builder = CognitivePatchProposalBuilder(data_root=str(tmp_path / "ce"))
    t133 = CognitiveSelfModificationProposal(registry=reg, proposal_builder=builder)
    audit = CognitiveEvolutionRuntimeAudit(
        registry=reg, proposal_builder=builder, t133=t133
    )
    sc10 = audit._audit_immutable_blocked()
    assert sc10["passed"] is True


# --------------------------------------------------------------------------- #
# T135 — CognitiveSkillLibrary
# --------------------------------------------------------------------------- #

def test_t135_install_all_skills(tmp_path):
    reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
    lib = CognitiveSkillLibrary(registry=reg)
    installed = lib.install_all()
    assert len(installed) == 6
    # Verify all are in registry
    for skill_id in installed:
        assert reg.get(skill_id) is not None
        assert reg.get(skill_id).approved is True


def test_t135_skill_types_installed(tmp_path):
    reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
    lib = CognitiveSkillLibrary(registry=reg)
    lib.install_all()

    thought = lib.list_by_type("thought")
    meta = lib.list_by_type("metacognitive")
    lang = lib.list_by_type("language")

    assert len(thought) == 1
    assert len(meta) == 2  # meta + confidence
    assert len(lang) == 3  # italian + narrative + dialogue


def test_t135_summary(tmp_path):
    reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
    lib = CognitiveSkillLibrary(registry=reg)
    lib.install_all()
    summary = lib.summary()
    assert summary["total_skills"] == 6
    assert summary["by_type"]["thought"] == 1
    assert summary["by_type"]["metacognitive"] == 2
    assert summary["by_type"]["language"] == 3


def test_t135_reasoning_skill_params(tmp_path):
    reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
    lib = CognitiveSkillLibrary(registry=reg)
    lib.install_all()
    skill = lib.get_skill("SK-REASON-001")
    assert skill is not None
    assert skill.skill_type == "thought"
    assert skill.params["reasoning_depth"] == 3
    assert skill.params["reasoning_breadth"] == 3
    assert skill.approved is True


def test_t135_italian_language_skill(tmp_path):
    reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
    lib = CognitiveSkillLibrary(registry=reg)
    lib.install_all()
    skill = lib.get_skill("SK-LANG-IT-001")
    assert skill is not None
    assert skill.skill_type == "language"
    assert skill.params["language_fluency"] == 0.85
    assert "Italian" in skill.template


def test_t135_narrative_synthesis_skill(tmp_path):
    reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
    lib = CognitiveSkillLibrary(registry=reg)
    lib.install_all()
    skill = lib.get_skill("SK-NARR-001")
    assert skill is not None
    assert skill.skill_type == "language"
    assert skill.params["narrative_compression_ratio"] == 0.3
    assert skill.params["importance_threshold"] == 5


def test_t135_vocal_dialogue_skill(tmp_path):
    reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
    lib = CognitiveSkillLibrary(registry=reg)
    lib.install_all()
    skill = lib.get_skill("SK-DIALOGUE-001")
    assert skill is not None
    assert skill.skill_type == "language"
    assert skill.params["turn_memory"] == 10
    assert "prosody" in skill.template


def test_t135_confidence_scoring_skill(tmp_path):
    reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
    lib = CognitiveSkillLibrary(registry=reg)
    lib.install_all()
    skill = lib.get_skill("SK-CONF-001")
    assert skill is not None
    assert skill.skill_type == "metacognitive"
    assert skill.params["novelty_weight"] == 0.3
    assert "epistemic confidence" in skill.template


def test_t135_skills_are_evolvable(tmp_path):
    """Verify that baseline skills can be cloned for sandbox evolution."""
    reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
    lib = CognitiveSkillLibrary(registry=reg)
    lib.install_all()

    parent = reg.get("SK-REASON-001")
    assert parent is not None
    assert parent.approved is True

    clone = reg.clone_for_sandbox("SK-REASON-001", {"params": {"reasoning_depth": 5}})
    assert clone is not None
    assert clone.parent_id == "SK-REASON-001"
    assert clone.approved is False
    assert clone.params["reasoning_depth"] == 5
