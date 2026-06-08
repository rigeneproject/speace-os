"""Tests for T136 — Longitudinal Cognitive Evolution Study,
T137 — Cognitive Homeostasis Layer,
T138 — Skill Consolidation & Pruning.
"""

import time

import pytest

from speace_core.cellular_brain.cognitive_evolution import (
    CognitiveHomeostasis,
    CognitivePatchProposalBuilder,
    CognitiveSelfModificationProposal,
    CognitiveSkill,
    CognitiveSkillRegistry,
    EvolutionarySkillOptimizer,
    LongitudinalEvolutionTracker,
    SkillConsolidationPruner,
)


# --------------------------------------------------------------------------- #
# T136 — LongitudinalEvolutionTracker
# --------------------------------------------------------------------------- #

class TestLongitudinalEvolutionTracker:
    def test_records_event(self, tmp_path):
        tracker = LongitudinalEvolutionTracker(
            history_path=str(tmp_path / "evo_history.jsonl")
        )
        tracker.record_event("SK-001", "proposal_applied", {"fitness": 0.8})
        events = tracker._load_all()
        assert len(events) == 1
        assert events[0]["skill_id"] == "SK-001"
        assert events[0]["event_type"] == "proposal_applied"
        assert events[0]["payload"]["fitness"] == 0.8

    def test_skill_timeline_filtering(self, tmp_path):
        tracker = LongitudinalEvolutionTracker(
            history_path=str(tmp_path / "evo_history.jsonl")
        )
        tracker.record_event("SK-001", "fitness_evaluated", {"fitness": 0.5})
        tracker.record_event("SK-002", "fitness_evaluated", {"fitness": 0.6})
        timeline = tracker.get_skill_timeline("SK-001", hours=1)
        assert len(timeline) == 1
        assert timeline[0]["skill_id"] == "SK-001"

    def test_fitness_trend_improving(self, tmp_path):
        tracker = LongitudinalEvolutionTracker(
            history_path=str(tmp_path / "evo_history.jsonl")
        )
        for i in range(5):
            tracker.record_event("SK-001", "fitness_evaluated", {"fitness": 0.4 + i * 0.1})
            time.sleep(0.01)
        trend = tracker.get_fitness_trend("SK-001", hours=1)
        assert trend["direction"] == "improving"
        assert trend["samples"] == 5

    def test_fitness_trend_decaying(self, tmp_path):
        tracker = LongitudinalEvolutionTracker(
            history_path=str(tmp_path / "evo_history.jsonl")
        )
        for i in range(5):
            tracker.record_event("SK-001", "fitness_evaluated", {"fitness": 0.8 - i * 0.1})
            time.sleep(0.01)
        trend = tracker.get_fitness_trend("SK-001", hours=1)
        assert trend["direction"] == "decaying"

    def test_rollback_prone_detection(self, tmp_path):
        tracker = LongitudinalEvolutionTracker(
            history_path=str(tmp_path / "evo_history.jsonl")
        )
        for _ in range(3):
            tracker.record_event("SK-001", "proposal_rolled_back", {})
        prone = tracker.get_rollback_prone_skills(min_rollbacks=2)
        assert "SK-001" in prone

    def test_decaying_skills(self, tmp_path):
        tracker = LongitudinalEvolutionTracker(
            history_path=str(tmp_path / "evo_history.jsonl")
        )
        tracker.record_event("SK-001", "fitness_evaluated", {"fitness": 0.2})
        tracker.record_event("SK-002", "fitness_evaluated", {"fitness": 0.5})
        decaying = tracker.get_decaying_skills(fitness_threshold=0.3)
        assert "SK-001" in decaying
        assert "SK-002" not in decaying

    def test_converging_skills(self, tmp_path):
        tracker = LongitudinalEvolutionTracker(
            history_path=str(tmp_path / "evo_history.jsonl")
        )
        tracker.record_event("SK-001", "fitness_evaluated", {"fitness": 0.5})
        tracker.record_event("SK-001", "fitness_evaluated", {"fitness": 0.8})
        converging = tracker.get_converging_skills(min_fitness=0.7)
        assert "SK-001" in converging

    def test_longitudinal_report(self, tmp_path):
        tracker = LongitudinalEvolutionTracker(
            history_path=str(tmp_path / "evo_history.jsonl")
        )
        tracker.record_event("SK-001", "fitness_evaluated", {"fitness": 0.8})
        report = tracker.generate_longitudinal_report()
        assert report["total_events"] == 1
        assert "SK-001" in report["skills_tracked"]

    def test_integration_with_t133(self, tmp_path):
        reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
        builder = CognitivePatchProposalBuilder(data_root=str(tmp_path / "ce"))
        tracker = LongitudinalEvolutionTracker(
            history_path=str(tmp_path / "evo_history.jsonl")
        )
        t133 = CognitiveSelfModificationProposal(
            registry=reg, proposal_builder=builder, tracker=tracker
        )

        skill = CognitiveSkill(
            skill_id="SK-T136-001",
            skill_type="thought",
            name="test",
            params={"depth": 3},
            template="test",
            approved=True,
            fitness_score=0.5,
            created_at=time.time(),
        )
        reg.register(skill)

        # Create and apply proposal
        proposal = builder.create(
            skill_id="SK-T136-001",
            skill_type="thought",
            fitness={"fitness": 0.8, "passed": True},
            pre_snapshot={"alert_engine": {"health_score": 0.8}},
            variant_params={"depth": 4},
            variant_template="test variant",
        )
        t133.approve_and_apply(proposal.proposal_id, "test_reviewer", current_health=0.8)

        # Rollback
        t133.rollback(proposal.proposal_id, "test_reviewer")

        events = tracker._load_all()
        assert len(events) == 2
        assert events[0]["event_type"] == "proposal_applied"
        assert events[1]["event_type"] == "proposal_rolled_back"


# --------------------------------------------------------------------------- #
# T137 — CognitiveHomeostasis
# --------------------------------------------------------------------------- #

class TestCognitiveHomeostasis:
    def test_pressure_low_when_few_skills(self, tmp_path):
        reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
        builder = CognitivePatchProposalBuilder(data_root=str(tmp_path / "ce"))
        homeo = CognitiveHomeostasis(max_active_skills=10)
        report = homeo.check(reg, builder, current_tick=0)
        assert report.overall_pressure == 0.0
        assert report.can_mutate is True
        assert report.can_create_proposal is True
        assert report.recommended_action == "maintain"

    def test_pressure_high_when_many_skills(self, tmp_path):
        reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
        builder = CognitivePatchProposalBuilder(data_root=str(tmp_path / "ce"))
        # Register 8 skills (threshold 10)
        for i in range(8):
            skill = CognitiveSkill(
                skill_id=f"SK-{i}",
                skill_type="thought",
                name="test",
                params={},
                template="t",
                approved=True,
                created_at=time.time(),
            )
            reg.register(skill)
        homeo = CognitiveHomeostasis(max_active_skills=10)
        report = homeo.check(reg, builder, current_tick=0)
        assert report.pressure_by_limit["active_skills"] == 0.8
        assert report.should_consolidate is True
        assert report.should_prune is True  # overall_pressure=0.8 >= 0.8

    def test_blocks_mutation_when_over_limit(self, tmp_path):
        reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
        builder = CognitivePatchProposalBuilder(data_root=str(tmp_path / "ce"))
        for i in range(11):
            skill = CognitiveSkill(
                skill_id=f"SK-{i}",
                skill_type="thought",
                name="test",
                params={},
                template="t",
                approved=True,
                created_at=time.time(),
            )
            reg.register(skill)
        homeo = CognitiveHomeostasis(max_active_skills=10)
        report = homeo.check(reg, builder, current_tick=0)
        assert report.can_mutate is False
        assert report.recommended_action == "halt_mutations"

    def test_blocks_mutation_when_too_many_pending(self, tmp_path):
        reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
        builder = CognitivePatchProposalBuilder(data_root=str(tmp_path / "ce"))
        for i in range(6):
            builder.create(
                skill_id="SK-X",
                skill_type="thought",
                fitness={"fitness": 0.5, "passed": True},
                pre_snapshot={},
                variant_params={},
                variant_template="",
            )
        homeo = CognitiveHomeostasis(max_pending_proposals=5)
        report = homeo.check(reg, builder, current_tick=0)
        assert report.can_mutate is False
        assert report.pressure_by_limit["pending_proposals"] == 1.0

    def test_respects_cooldown(self, tmp_path):
        reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
        builder = CognitivePatchProposalBuilder(data_root=str(tmp_path / "ce"))
        homeo = CognitiveHomeostasis(min_cycles_between_mutations=5)
        homeo.register_mutation(tick=0)
        report = homeo.check(reg, builder, current_tick=2)
        assert report.can_mutate is False
        assert report.pressure_by_limit["cooldown"] == 1.0

        report = homeo.check(reg, builder, current_tick=10)
        assert report.can_mutate is True
        assert report.pressure_by_limit["cooldown"] == 0.0

    def test_pressure_report(self, tmp_path):
        homeo = CognitiveHomeostasis(max_active_skills=20)
        report = homeo.get_pressure_report()
        assert report["limits"]["max_active_skills"] == 20

    def test_pressure_relief_actions(self, tmp_path):
        reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
        builder = CognitivePatchProposalBuilder(data_root=str(tmp_path / "ce"))
        for i in range(10):
            skill = CognitiveSkill(
                skill_id=f"SK-{i}",
                skill_type="thought",
                name="test",
                params={},
                template="t",
                approved=True,
                created_at=time.time(),
            )
            reg.register(skill)
        homeo = CognitiveHomeostasis(max_active_skills=10)
        relief = homeo.apply_pressure_relief(reg, builder)
        assert "consider_pruning_low_fitness_skills" in relief["actions"]

    def test_integration_with_optimizer(self, tmp_path):
        reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
        builder = CognitivePatchProposalBuilder(data_root=str(tmp_path / "ce"))
        # Fill registry to limit
        for i in range(11):
            skill = CognitiveSkill(
                skill_id=f"SK-{i}",
                skill_type="thought",
                name="test",
                params={},
                template="t",
                approved=True,
                fitness_score=0.5,
                created_at=time.time(),
            )
            reg.register(skill)
        homeo = CognitiveHomeostasis(max_active_skills=10)
        opt = EvolutionarySkillOptimizer(
            registry=reg,
            proposal_builder=builder,
            homeostasis=homeo,
        )
        result = opt.evolve_skill("SK-0", {}, mutation_rate=0.1, current_tick=0)
        assert result is None


# --------------------------------------------------------------------------- #
# T138 — SkillConsolidationPruner
# --------------------------------------------------------------------------- #

class TestSkillConsolidationPruner:
    def test_find_redundant_skills(self, tmp_path):
        reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
        s1 = CognitiveSkill(
            skill_id="SK-A",
            skill_type="thought",
            name="a",
            params={"depth": 3.0, "breadth": 3.0},
            template="Analyze {depth}",
            approved=True,
            fitness_score=0.8,
            created_at=time.time(),
        )
        s2 = CognitiveSkill(
            skill_id="SK-B",
            skill_type="thought",
            name="b",
            params={"depth": 3.02, "breadth": 3.01},
            template="Analyze {depth}",
            approved=True,
            fitness_score=0.81,
            created_at=time.time(),
        )
        reg.register(s1)
        reg.register(s2)
        pruner = SkillConsolidationPruner(similarity_threshold=0.05)
        redundant = pruner.find_redundant_skills(reg)
        assert len(redundant) == 1
        assert set(redundant[0][:2]) == {"SK-A", "SK-B"}

    def test_no_redundant_for_different_types(self, tmp_path):
        reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
        s1 = CognitiveSkill(
            skill_id="SK-A",
            skill_type="thought",
            name="a",
            params={"depth": 3.0},
            template="t",
            approved=True,
            fitness_score=0.8,
            created_at=time.time(),
        )
        s2 = CognitiveSkill(
            skill_id="SK-B",
            skill_type="language",
            name="b",
            params={"depth": 3.0},
            template="t",
            approved=True,
            fitness_score=0.8,
            created_at=time.time(),
        )
        reg.register(s1)
        reg.register(s2)
        pruner = SkillConsolidationPruner()
        redundant = pruner.find_redundant_skills(reg)
        assert len(redundant) == 0

    def test_propose_merge(self, tmp_path):
        reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
        builder = CognitivePatchProposalBuilder(data_root=str(tmp_path / "ce"))
        s1 = CognitiveSkill(
            skill_id="SK-A",
            skill_type="thought",
            name="a",
            params={"depth": 3.0},
            template="Analyze {depth}",
            approved=True,
            fitness_score=0.8,
            created_at=time.time(),
        )
        s2 = CognitiveSkill(
            skill_id="SK-B",
            skill_type="thought",
            name="b",
            params={"depth": 4.0},
            template="Analyze {depth}",
            approved=True,
            fitness_score=0.6,
            created_at=time.time(),
        )
        reg.register(s1)
        reg.register(s2)
        pruner = SkillConsolidationPruner()
        proposal = pruner.propose_merge("SK-A", "SK-B", reg, builder)
        assert proposal is not None
        assert "SK-A" in proposal.description

    def test_consolidate_core_skills(self, tmp_path):
        reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
        s1 = CognitiveSkill(
            skill_id="SK-A",
            skill_type="thought",
            name="a",
            params={},
            template="t",
            approved=True,
            fitness_score=0.8,
            created_at=time.time() - 3600,  # old enough
        )
        reg.register(s1)
        pruner = SkillConsolidationPruner()
        consolidated = pruner.consolidate_core_skills(reg, min_cycles=0, min_fitness=0.7)
        assert "SK-A" in consolidated
        assert reg.get("SK-A").origin == "consolidated"

    def test_prune_obsolete_skills(self, tmp_path):
        reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
        s1 = CognitiveSkill(
            skill_id="SK-A",
            skill_type="thought",
            name="a",
            params={},
            template="t",
            approved=False,
            fitness_score=0.2,
            created_at=time.time() - 3600,
        )
        reg.register(s1)
        pruner = SkillConsolidationPruner()
        pruned = pruner.prune_obsolete_skills(reg, fitness_threshold=0.3, min_age_cycles=0)
        assert "SK-A" in pruned
        assert reg.get("SK-A").origin == "pruned"

    def test_core_skills_protected_from_pruning(self, tmp_path):
        reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
        s1 = CognitiveSkill(
            skill_id="SK-A",
            skill_type="thought",
            name="a",
            params={},
            template="t",
            approved=True,
            fitness_score=0.2,
            origin="consolidated",
            created_at=time.time() - 3600,
        )
        reg.register(s1)
        pruner = SkillConsolidationPruner()
        pruned = pruner.prune_obsolete_skills(reg, fitness_threshold=0.3, min_age_cycles=0)
        assert "SK-A" not in pruned

    def test_run_maintenance(self, tmp_path):
        reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
        builder = CognitivePatchProposalBuilder(data_root=str(tmp_path / "ce"))
        # One stable skill (should consolidate)
        s1 = CognitiveSkill(
            skill_id="SK-A",
            skill_type="thought",
            name="a",
            params={},
            template="t",
            approved=True,
            fitness_score=0.8,
            created_at=time.time() - 3600,
        )
        # One obsolete skill (should prune)
        s2 = CognitiveSkill(
            skill_id="SK-B",
            skill_type="thought",
            name="b",
            params={},
            template="t",
            approved=False,
            fitness_score=0.2,
            created_at=time.time() - 3600,
        )
        reg.register(s1)
        reg.register(s2)
        pruner = SkillConsolidationPruner()
        report = pruner.run_maintenance(reg, builder)
        assert report.action_taken is True
        assert "SK-A" in report.consolidated
        assert "SK-B" in report.pruned

    def test_similarity_clusters(self, tmp_path):
        reg = CognitiveSkillRegistry(data_root=str(tmp_path / "ce"))
        s1 = CognitiveSkill(
            skill_id="SK-A",
            skill_type="thought",
            name="a",
            params={"depth": 3.0},
            template="t",
            approved=True,
            fitness_score=0.8,
            created_at=time.time(),
        )
        s2 = CognitiveSkill(
            skill_id="SK-B",
            skill_type="thought",
            name="b",
            params={"depth": 3.01},
            template="t",
            approved=True,
            fitness_score=0.81,
            created_at=time.time(),
        )
        reg.register(s1)
        reg.register(s2)
        pruner = SkillConsolidationPruner()
        redundant = pruner.find_redundant_skills(reg)
        clusters = pruner._build_clusters(redundant)
        assert len(clusters) == 1
        assert set(clusters[0]) == {"SK-A", "SK-B"}
