"""Tests for T132 — Cognitive Skill Evolution Layer and T133 — Cognitive Self-Modification Proposal Layer."""

import time
from typing import Any, Dict

import pytest

from speace_core.cellular_brain.cognitive_evolution import (
    CognitiveMutationSandbox,
    CognitivePatchProposalBuilder,
    CognitiveSelfModificationProposal,
    CognitiveSkill,
    CognitiveSkillRegistry,
    EvolutionarySkillOptimizer,
    LanguageSkillRunner,
    MetacognitiveSkillRunner,
    SkillFitnessEvaluator,
    ThoughtSkillRunner,
)


# --------------------------------------------------------------------------- #
# T132 — CognitiveSkillRegistry
# --------------------------------------------------------------------------- #

def test_registry_register_and_get(tmp_path):
    reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
    skill = CognitiveSkill(
        skill_id="SK-001",
        skill_type="thought",
        name="reasoning_v1",
        params={"depth": 3, "breadth": 3},
        template="Analyze {depth} branches",
        approved=True,
        created_at=time.time(),
    )
    reg.register(skill)
    retrieved = reg.get("SK-001")
    assert retrieved is not None
    assert retrieved.name == "reasoning_v1"
    assert retrieved.approved is True


def test_registry_clone_for_sandbox(tmp_path):
    reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
    parent = CognitiveSkill(
        skill_id="SK-002",
        skill_type="metacognitive",
        name="meta_v1",
        params={"effectiveness": 0.7},
        template="Reflect on {effectiveness}",
        approved=True,
        created_at=time.time(),
    )
    reg.register(parent)
    clone = reg.clone_for_sandbox("SK-002", {"params": {"effectiveness": 0.8}})
    assert clone is not None
    assert clone.parent_id == "SK-002"
    assert clone.approved is False
    assert clone.params["effectiveness"] == 0.8


def test_registry_rejects_unapproved_parent(tmp_path):
    reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
    parent = CognitiveSkill(
        skill_id="SK-003",
        skill_type="language",
        name="lang_v1",
        params={"fluency": 0.5},
        approved=False,
        created_at=time.time(),
    )
    reg.register(parent)
    clone = reg.clone_for_sandbox("SK-003", {"params": {"fluency": 0.6}})
    assert clone is None


# --------------------------------------------------------------------------- #
# T132 — SkillFitnessEvaluator
# --------------------------------------------------------------------------- #

def test_fitness_passes_with_good_trials():
    evaluator = SkillFitnessEvaluator(trials_per_variant=3)
    trials = [
        {"success": True, "latency_ms": 100.0, "stability_delta": 0.1, "coherence_delta": 0.1, "confidence_delta": 0.1},
        {"success": True, "latency_ms": 110.0, "stability_delta": 0.12, "coherence_delta": 0.08, "confidence_delta": 0.1},
        {"success": True, "latency_ms": 90.0, "stability_delta": 0.11, "coherence_delta": 0.09, "confidence_delta": 0.1},
    ]
    result = evaluator.evaluate({}, trials)
    assert result["passed"] is True
    assert result["fitness"] > 0.5


def test_fitness_fails_with_low_success():
    evaluator = SkillFitnessEvaluator(trials_per_variant=3)
    trials = [
        {"success": False, "latency_ms": 100.0, "stability_delta": -0.1, "coherence_delta": -0.1, "confidence_delta": -0.1},
        {"success": False, "latency_ms": 110.0, "stability_delta": -0.1, "coherence_delta": -0.1, "confidence_delta": -0.1},
        {"success": False, "latency_ms": 90.0, "stability_delta": -0.1, "coherence_delta": -0.1, "confidence_delta": -0.1},
    ]
    result = evaluator.evaluate({}, trials)
    assert result["passed"] is False


# --------------------------------------------------------------------------- #
# T132 — CognitiveMutationSandbox
# --------------------------------------------------------------------------- #

def test_sandbox_validates_dangerous_patterns():
    sandbox = CognitiveMutationSandbox(seed=42)
    bad_variant = {
        "params": {"x": 1},
        "template": "eval(malicious_code)",
    }
    assert sandbox.validate_mutation(bad_variant) is False


def test_sandbox_accepts_safe_variant():
    sandbox = CognitiveMutationSandbox(seed=42)
    good_variant = {
        "params": {"depth": 3, "breadth": 3},
        "template": "Analyze {depth} branches carefully",
    }
    assert sandbox.validate_mutation(good_variant) is True


def test_sandbox_run_returns_metrics():
    sandbox = CognitiveMutationSandbox(seed=42)
    variant = {
        "params": {"success_bias": 0.9, "stability_boost": 0.2},
        "template": "safe template",
    }
    result = sandbox.run_sandbox(variant, {})
    assert "latency_ms" in result
    assert "stability_delta" in result


# --------------------------------------------------------------------------- #
# T132 — Skill Runners
# --------------------------------------------------------------------------- #

def test_thought_skill_runner():
    runner = ThoughtSkillRunner()
    result = runner.run(
        skill_params={"reasoning_depth": 3, "reasoning_breadth": 2},
        template="Think about {reasoning_depth} levels",
        input_state={},
    )
    assert result["skill_type"] == "thought"
    assert len(result["trace"]) == 3
    assert result["latency_ms"] > 0


def test_metacognitive_skill_runner():
    runner = MetacognitiveSkillRunner()
    meta_state = {
        "cognitive_observation": {"workspace_stability": 0.8},
        "error_detection": {"repetitive_loop": False, "contradiction": False, "overfocus": False, "similarity_collapse": False, "memory_saturation": False, "regulation_oscillation": False},
        "epistemic_confidence": {"confidence_score": 0.7},
    }
    result = runner.run(
        skill_params={"meta_effectiveness": 0.8},
        template="Reflect with {meta_effectiveness}",
        meta_state=meta_state,
    )
    assert result["skill_type"] == "metacognitive"
    assert result["stability_delta"] > 0


def test_language_skill_runner():
    runner = LanguageSkillRunner()
    result = runner.run(
        skill_params={"language_fluency": 0.9, "context_depth": 2},
        template="Respond with {language_fluency}",
        dialogue_state={"turn_count": 5},
    )
    assert result["skill_type"] == "language"
    assert result["coherence_delta"] > 0


# --------------------------------------------------------------------------- #
# T132 — EvolutionarySkillOptimizer
# --------------------------------------------------------------------------- #

def test_optimizer_skips_unapproved_parent(tmp_path):
    reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
    parent = CognitiveSkill(
        skill_id="SK-UNAPPROVED",
        skill_type="thought",
        name="unapproved",
        params={"depth": 3},
        approved=False,
        created_at=time.time(),
    )
    reg.register(parent)
    optimizer = EvolutionarySkillOptimizer(registry=reg)
    result = optimizer.evolve_skill("SK-UNAPPROVED", {})
    assert result is None


def test_optimizer_evolve_and_create_proposal(tmp_path):
    reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
    parent = CognitiveSkill(
        skill_id="SK-GOOD",
        skill_type="thought",
        name="good_parent",
        params={"success_bias": 0.95, "stability_boost": 0.3, "coherence_boost": 0.3, "confidence_boost": 0.3},
        template="Think deeply",
        approved=True,
        fitness_score=0.5,
        created_at=time.time(),
    )
    reg.register(parent)
    optimizer = EvolutionarySkillOptimizer(registry=reg)
    result = optimizer.evolve_skill("SK-GOOD", {}, mutation_rate=0.1, requested_by="test")
    # With high success_bias, sandbox trials should pass and create a proposal
    assert result is not None
    assert result["status"] == "pending_approval"
    assert "proposal_id" in result


# --------------------------------------------------------------------------- #
# T133 — CognitivePatchProposalBuilder
# --------------------------------------------------------------------------- #

def test_proposal_builder_lifecycle(tmp_path):
    builder = CognitivePatchProposalBuilder(data_root=str(tmp_path / "ce"))
    proposal = builder.create(
        skill_id="SK-001",
        skill_type="thought",
        fitness={"fitness": 0.85, "passed": True},
        pre_snapshot={"health": 0.9},
        variant_params={"depth": 5},
        variant_template="Think deeper",
        requested_by="test",
    )
    assert proposal.status == "pending"

    ok = builder.approve(proposal.proposal_id, "reviewer_a")
    assert ok is True
    updated = builder.get(proposal.proposal_id)
    assert updated is not None
    assert updated.status == "approved"
    assert updated.reviewer == "reviewer_a"

    ok = builder.mark_applied(proposal.proposal_id, {"old_params": {}})
    assert ok is True
    applied = builder.get(proposal.proposal_id)
    assert applied is not None
    assert applied.status == "applied"

    ok = builder.mark_rolled_back(proposal.proposal_id)
    assert ok is True
    rolled = builder.get(proposal.proposal_id)
    assert rolled is not None
    assert rolled.status == "rolled_back"


# --------------------------------------------------------------------------- #
# T133 — CognitiveSelfModificationProposal
# --------------------------------------------------------------------------- #

def test_t133_approve_and_apply(tmp_path):
    reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
    skill = CognitiveSkill(
        skill_id="SK-MOD",
        skill_type="thought",
        name="modifiable",
        params={"depth": 3},
        template="Think",
        approved=True,
        created_at=time.time(),
    )
    reg.register(skill)

    builder = CognitivePatchProposalBuilder(data_root=str(tmp_path / "ce"))
    proposal = builder.create(
        skill_id="SK-MOD",
        skill_type="thought",
        fitness={"fitness": 0.9, "passed": True},
        pre_snapshot={},
        variant_params={"depth": 5},
        variant_template="Think deeper",
    )

    t133 = CognitiveSelfModificationProposal(registry=reg, proposal_builder=builder)
    result = t133.approve_and_apply(proposal.proposal_id, "human_reviewer")
    assert result["status"] == "applied"
    assert result["rollback_available"] is True

    updated_skill = reg.get("SK-MOD")
    assert updated_skill is not None
    assert updated_skill.params["depth"] == 5
    assert updated_skill.template == "Think deeper"


def test_t133_rollback_restores_state(tmp_path):
    reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
    skill = CognitiveSkill(
        skill_id="SK-ROLL",
        skill_type="metacognitive",
        name="rollbackable",
        params={"effectiveness": 0.5},
        template="Reflect",
        approved=True,
        created_at=time.time(),
    )
    reg.register(skill)

    builder = CognitivePatchProposalBuilder(data_root=str(tmp_path / "ce"))
    proposal = builder.create(
        skill_id="SK-ROLL",
        skill_type="metacognitive",
        fitness={"fitness": 0.9, "passed": True},
        pre_snapshot={},
        variant_params={"effectiveness": 0.9},
        variant_template="Reflect deeply",
    )

    t133 = CognitiveSelfModificationProposal(registry=reg, proposal_builder=builder)
    t133.approve_and_apply(proposal.proposal_id, "human_reviewer")

    # Verify applied
    assert reg.get("SK-ROLL").params["effectiveness"] == 0.9

    # Rollback
    rb = t133.rollback(proposal.proposal_id, "human_reviewer")
    assert rb["status"] == "rolled_back"
    assert reg.get("SK-ROLL").params["effectiveness"] == 0.5
    assert reg.get("SK-ROLL").template == "Reflect"


def test_t133_auto_rollback_on_regression(tmp_path):
    reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
    skill = CognitiveSkill(
        skill_id="SK-AUTO",
        skill_type="language",
        name="auto_rollback",
        params={"fluency": 0.5},
        template="Speak",
        approved=True,
        created_at=time.time(),
    )
    reg.register(skill)

    builder = CognitivePatchProposalBuilder(data_root=str(tmp_path / "ce"))
    proposal = builder.create(
        skill_id="SK-AUTO",
        skill_type="language",
        fitness={"fitness": 0.9, "passed": True},
        pre_snapshot={"alert_engine": {"health_score": 0.8}},
        variant_params={"fluency": 0.99},
        variant_template="Speak fluently",
    )

    t133 = CognitiveSelfModificationProposal(registry=reg, proposal_builder=builder)
    t133.approve_and_apply(proposal.proposal_id, "human_reviewer")

    # Post-apply health regressed > 10%
    eval_result = t133.evaluate_post_apply(proposal.proposal_id, post_health=0.6)
    assert eval_result["action"] == "auto_rollback"
    assert reg.get("SK-AUTO").params["fluency"] == 0.5


def test_t133_rejects_immutable_domain(tmp_path):
    builder = CognitivePatchProposalBuilder(data_root=str(tmp_path / "ce"))
    proposal = builder.create(
        skill_id="SK-GOV",
        skill_type="governance",  # immutable domain
        fitness={"fitness": 0.9, "passed": True},
        pre_snapshot={},
        variant_params={},
        variant_template="",
    )

    t133 = CognitiveSelfModificationProposal(proposal_builder=builder)
    result = t133.submit_proposal(proposal.proposal_id)
    assert result["error"] == "immutable_domain_touched"
