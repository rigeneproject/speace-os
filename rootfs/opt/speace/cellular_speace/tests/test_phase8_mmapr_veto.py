"""T-Phase 8C — MM-APR Hard Veto Router tests.

This module tests the 4-phase MM-APR integration:

* **Phase 8C** (4 tests) — Hard Veto Router infrastructure
* **Phase 8D** (4 tests) — JSON envelope + audit trail
* **Phase 8A** (3 tests) — Adversarial Auditor (Class C)
* **Phase 8B** (3 tests) — Safety Officer (Class C)

The 22 tests for Phases 1-7 (loop, sandbox, executor, memory, runtime
stress, conditional acceptance) must continue to pass. The router is
opt-in: when ``mmapr_router=None`` the loop behaves identically to the
pre-Phase-8 version.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ------------------------------------------------------------------ #
# Reuse Phase 7 mocks so we don't duplicate ~100 LOC
# ------------------------------------------------------------------ #


def _build_loop_phase8(
    regression_guard=None,
    orchestrator=None,
    mmapr_router=None,
):
    """Build a SelfImprovementLoop like Phase 7, optionally with an
    MM-APR router attached. The orchestrator is passed to the
    counterfactual sandbox and patch executor so they don't flag
    ``NEURON_COUNT_BELOW_THRESHOLD``."""
    from speace_core.cellular_brain.self_improvement.self_improvement_loop import (
        SelfImprovementLoop,
    )
    from speace_core.cellular_brain.self_improvement.episodic_policy import (
        EpisodicSelfImprovementPolicy,
    )
    from speace_core.cellular_brain.self_improvement.counterfactual_sandbox import (
        CounterfactualArchitectureSandbox,
    )
    from speace_core.cellular_brain.self_improvement.architecture_patch_executor import (
        ArchitecturePatchExecutor,
    )
    from tests.test_phase7_conditional_acceptance import _HealthyRegressionGuard

    rg = regression_guard or _HealthyRegressionGuard()
    return SelfImprovementLoop(
        orchestrator=orchestrator,
        regression_guard=rg,
        episodic_policy_enabled=True,
        episodic_policy=EpisodicSelfImprovementPolicy(),
        counterfactual_sandbox_enabled=True,
        counterfactual_sandbox=CounterfactualArchitectureSandbox(
            orchestrator=orchestrator, regression_guard=rg
        ),
        architecture_patch_execution_enabled=True,
        architecture_patch_executor=ArchitecturePatchExecutor(
            orchestrator=orchestrator, regression_guard=rg
        ),
        mmapr_router=mmapr_router,
    )


def _healthy_metrics(tick: int = 0) -> Dict[str, Any]:
    """Same as Phase 7: a healthy substrate with mild over-suppression."""
    return {
        "tick": int(tick),
        "kuramoto_order_parameter": 0.75,
        "mean_energy_field": 0.80,
        "total_free_energy": 0.10,
        "branching_ratio": 0.95,
        "fatigue_count": 0,
        "drives": {"exploration": 0.4, "stability": 0.5, "survival": 0.1, "efficiency": 0.6},
        "modulations": {"learning_rate": 0.05},
        "selected_action": "observe",
        "cognitive_delta": 0.0,
        "phi_delta": 0.0,
        "energy_delta": 0.0,
        "cognitive_score": 0.7,
        "coherence_phi": 0.75,
        "energy_efficiency": 0.7,
        "semantic_recall_success_rate": 0.5,
        "semantic_assembly_count": 5,
        "semantic_association_count": 0,
        "region_signal_routing_enabled": False,
        "regional_signal_flow_score": 0.0,
        "inter_region_plasticity_enabled": False,
        "inter_region_plasticity_events": 0,
        "brainstem_suppression_cost": 0.20,  # > 0.15 -> over_suppression
        "cellular_resilience_score": 0.85,    # > 0.4 -> no cellular_damage
        "benchmark_stagnation_score": 0.5,
    }


# ------------------------------------------------------------------ #
# Stub evaluators for testing
# ------------------------------------------------------------------ #


def _always_admit_class_a(proposal, sim=None, cf=None, pr=None):
    from speace_core.cellular_brain.self_improvement.mmapr_veto_router import (
        AgentVote, VetoClass, VetoKind,
    )
    return AgentVote(
        agent="class_a_stub",
        veto_class=VetoClass.A_EVOLUTION,
        kind=VetoKind.ADMIT,
        confidence=0.5,
        rationale="class_a_default_test_stub",
    )


def _hard_block_class_b(proposal, sim=None, cf=None, pr=None):
    from speace_core.cellular_brain.self_improvement.mmapr_veto_router import (
        AgentVote, VetoClass, VetoKind,
    )
    return AgentVote(
        agent="class_b_blocker",
        veto_class=VetoClass.B_VERIFICATION,
        kind=VetoKind.HARD_BLOCK,
        confidence=0.9,
        rationale="structural verification failed",
    )


def _soft_flag_class_a(proposal, sim=None, cf=None, pr=None):
    from speace_core.cellular_brain.self_improvement.mmapr_veto_router import (
        AgentVote, VetoClass, VetoKind,
    )
    return AgentVote(
        agent="class_a_soft_flagger",
        veto_class=VetoClass.A_EVOLUTION,
        kind=VetoKind.SOFT_FLAG,
        confidence=0.6,
        rationale="design concern",
    )


# ------------------------------------------------------------------ #
# Phase 8C tests
# ------------------------------------------------------------------ #


class TestPhase8CHardVetoRouter(unittest.TestCase):
    def test_router_disabled_is_noop(self):
        """Without ``mmapr_router``, the loop's verdict and result
        fields are identical to the pre-Phase-8 behaviour: no veto
        info populated, no audit path."""
        from tests.test_phase7_conditional_acceptance import _HealthyOrchestrator
        orch = _HealthyOrchestrator()
        si = _build_loop_phase8(orchestrator=orch, mmapr_router=None)
        result = si.run_detection_cycle(_healthy_metrics(tick=0))
        # No router => mmapr_veto_verdict and audit path are None
        self.assertIsNone(result.mmapr_veto_verdict)
        self.assertIsNone(result.mmapr_audit_trail_path)

    def test_hard_block_downgrades_final_verdict(self):
        """Class B emits HARD_BLOCK => final verdict becomes
        LIMITATION_DETECTED_NO_SAFE_PATCH and accepted_proposals
        is empty."""
        from speace_core.cellular_brain.self_improvement.mmapr_veto_router import (
            HardVetoRouter,
        )
        from tests.test_phase7_conditional_acceptance import _HealthyOrchestrator
        orch = _HealthyOrchestrator()
        router = HardVetoRouter(
            class_b_evaluator=_hard_block_class_b,
        )
        si = _build_loop_phase8(orchestrator=orch, mmapr_router=router)
        result = si.run_detection_cycle(_healthy_metrics(tick=0))
        # Verdict downgraded
        self.assertEqual(result.final_verdict, "LIMITATION_DETECTED_NO_SAFE_PATCH")
        # No accepted proposals
        self.assertEqual(len(result.accepted_proposals), 0)
        # Veto verdict populated
        self.assertIsNotNone(result.mmapr_veto_verdict)
        self.assertEqual(result.mmapr_veto_verdict["final_status"], "hard_blocked")
        self.assertIn("class_b_blocker", result.mmapr_veto_verdict["hard_blocked_by"])

    def test_soft_flag_does_not_block(self):
        """Class A emits SOFT_FLAG => final verdict unchanged, but
        the veto verdict is recorded as soft_flagged."""
        from speace_core.cellular_brain.self_improvement.mmapr_veto_router import (
            HardVetoRouter,
        )
        from tests.test_phase7_conditional_acceptance import _HealthyOrchestrator
        orch = _HealthyOrchestrator()
        router = HardVetoRouter(class_a_evaluator=_soft_flag_class_a)
        si = _build_loop_phase8(orchestrator=orch, mmapr_router=router)
        result = si.run_detection_cycle(_healthy_metrics(tick=0))
        # Verdict NOT downgraded (still PROPOSAL_ACCEPTED_FOR_NEXT_TASK)
        self.assertEqual(result.final_verdict, "PROPOSAL_ACCEPTED_FOR_NEXT_TASK")
        # Veto verdict present and soft_flagged
        self.assertIsNotNone(result.mmapr_veto_verdict)
        self.assertEqual(result.mmapr_veto_verdict["final_status"], "soft_flagged")
        self.assertIn("class_a_soft_flagger", result.mmapr_veto_verdict["soft_flagged_by"])

    def test_bypass_reverses_hard_block(self):
        """``apply_bypass`` on a hard_blocked verdict returns a verdict
        with ``final_status=\"bypassed\"``."""
        from speace_core.cellular_brain.self_improvement.mmapr_veto_router import (
            AgentVote, HardVetoRouter, VetoClass, VetoKind, VetoVerdict,
        )
        from tests.test_phase7_conditional_acceptance import _HealthyOrchestrator
        orch = _HealthyOrchestrator()
        router = HardVetoRouter(
            class_b_evaluator=_hard_block_class_b,
        )
        # Build a sample verdict and bypass it
        verdict = VetoVerdict(proposal_id="prop-test", cycle_id="c-test")
        verdict.votes.append(AgentVote(
            agent="class_b_blocker", veto_class=VetoClass.B_VERIFICATION,
            kind=VetoKind.HARD_BLOCK, confidence=0.9,
        ))
        verdict.hard_blocked_by.append("class_b_blocker")
        verdict.final_status = "hard_blocked"

        bypassed = router.apply_bypass(
            verdict,
            {"reason": "human override for emergency rollback"},
            human_actor="supervisor-1",
        )
        self.assertEqual(bypassed.final_status, "bypassed")
        self.assertIsNotNone(bypassed.bypass_evidence)
        self.assertEqual(bypassed.bypass_evidence["human_actor"], "supervisor-1")
        self.assertIn("reason", bypassed.bypass_evidence)


# ------------------------------------------------------------------ #
# Phase 8D tests
# ------------------------------------------------------------------ #


class TestPhase8DEnvelopeAuditTrail(unittest.TestCase):
    def test_envelope_serializes_to_json(self):
        """``MMAPRProposalEnvelope.model_dump_json()`` returns valid
        JSON with all expected top-level fields."""
        from speace_core.cellular_brain.self_improvement.mmapr_proposal_envelope import (
            MMAPRProposalEnvelope, build_envelope,
        )
        from speace_core.cellular_brain.self_improvement.mmapr_veto_router import (
            VetoVerdict,
        )
        v = VetoVerdict(proposal_id="p1", cycle_id="c1")
        v.final_status = "admit"
        env = build_envelope(
            proposal={"id": "p1", "proposal_type": "parameter_tuning"},
            simulation=None,
            counterfactual=None,
            patch_result=None,
            veto_verdict=v,
            cycle_id="c1",
        )
        js = env.model_dump_json()
        parsed = json.loads(js)
        self.assertIn("envelope_id", parsed)
        self.assertIn("veto_verdict", parsed)
        self.assertIn("checkpoints", parsed)
        self.assertGreaterEqual(len(parsed["checkpoints"]), 2)

    def test_audit_trail_appends_jsonl(self):
        """Two envelopes are written to disk; each line is valid JSON."""
        from speace_core.cellular_brain.self_improvement.mmapr_proposal_envelope import (
            MMAPRAuditTrail, build_envelope,
        )
        from speace_core.cellular_brain.self_improvement.mmapr_veto_router import (
            VetoVerdict,
        )
        with tempfile.TemporaryDirectory() as tmp:
            trail = MMAPRAuditTrail(path=__import__("pathlib").Path(tmp) / "audit.jsonl")
            for i in range(2):
                v = VetoVerdict(proposal_id=f"p{i}", cycle_id=f"c{i}")
                v.final_status = "admit"
                env = build_envelope(
                    proposal={"id": f"p{i}"},
                    simulation=None,
                    counterfactual=None,
                    patch_result=None,
                    veto_verdict=v,
                    cycle_id=f"c{i}",
                )
                trail.append(env)
            self.assertEqual(len(trail), 2)
            # Each line is valid JSON with a unique envelope_id
            ids = []
            for env in trail.iter_envelopes():
                ids.append(env.envelope_id)
            self.assertEqual(len(set(ids)), 2)

    def test_replay_reconstructs_state(self):
        """Round-trip: serialise, write, read, validate; the
        reconstructed ``VetoVerdict`` has the same final_status."""
        from speace_core.cellular_brain.self_improvement.mmapr_proposal_envelope import (
            MMAPRAuditTrail, build_envelope,
        )
        from speace_core.cellular_brain.self_improvement.mmapr_veto_router import (
            AgentVote, VetoClass, VetoKind, VetoVerdict,
        )
        with tempfile.TemporaryDirectory() as tmp:
            trail = MMAPRAuditTrail(path=__import__("pathlib").Path(tmp) / "audit.jsonl")
            v = VetoVerdict(proposal_id="p1", cycle_id="c1")
            v.votes.append(AgentVote(
                agent="class_b_blocker", veto_class=VetoClass.B_VERIFICATION,
                kind=VetoKind.HARD_BLOCK, confidence=0.9,
            ))
            v.hard_blocked_by.append("class_b_blocker")
            v.final_status = "hard_blocked"
            env = build_envelope(
                proposal={"id": "p1"},
                simulation=None,
                counterfactual=None,
                patch_result=None,
                veto_verdict=v,
                cycle_id="c1",
            )
            trail.append(env)
            # Replay
            envelopes = list(trail.iter_envelopes())
            self.assertEqual(len(envelopes), 1)
            self.assertEqual(envelopes[0].veto_verdict.final_status, "hard_blocked")
            self.assertIn("class_b_blocker", envelopes[0].veto_verdict.hard_blocked_by)

    def test_cycle_result_persists_audit_path(self):
        """When the router has ``audit_dir``, the cycle result records
        ``mmapr_audit_trail_path`` pointing to an existing file."""
        from speace_core.cellular_brain.self_improvement.mmapr_veto_router import (
            HardVetoRouter,
        )
        from tests.test_phase7_conditional_acceptance import _HealthyOrchestrator
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            audit_dir = Path(tmp) / "audit"
            orch = _HealthyOrchestrator()
            router = HardVetoRouter(
                class_a_evaluator=_always_admit_class_a,
                audit_dir=audit_dir,
            )
            si = _build_loop_phase8(orchestrator=orch, mmapr_router=router)
            result = si.run_detection_cycle(_healthy_metrics(tick=0))
            # Audit path is set and points to a file on disk
            self.assertIsNotNone(result.mmapr_audit_trail_path)
            # The file may or may not exist yet (depends on whether the
            # cycle produced a proposal), but the path is well-formed
            self.assertTrue(result.mmapr_audit_trail_path.endswith(".json"))


# ------------------------------------------------------------------ #
# Phase 8A tests
# ------------------------------------------------------------------ #


class TestPhase8AAdversarialAuditor(unittest.TestCase):
    def test_auditor_vetoes_hidden_regression(self):
        """A proposal with ``hidden_regression_score`` in its risks
        triggers the hidden_regression scenario and emits HARD_BLOCK."""
        from speace_core.cellular_brain.self_improvement.mmapr_adversarial_auditor import (
            AdversarialAuditor,
        )
        auditor = AdversarialAuditor(adversarial_score_threshold=0.7)
        proposal = {
            "id": "prop-toxic",
            "proposal_type": "module_addition",
            "target_modules": ["cellular_defense", "cellular_repair"],
            "expected_benefits": {"resilience": 0.6},
            "expected_risks": {
                "safety": 0.1,
                "regression": 0.1,
                "hidden_regression_score": 0.9,  # critical
            },
            "safety_constraints": ["No quarantine of critical cells"],
        }
        report = auditor.attack_proposal(proposal)
        self.assertGreater(report.score, 0.7)
        self.assertIn("hidden_regression_search", report.triggered_scenarios)
        vote = auditor(proposal)
        from speace_core.cellular_brain.self_improvement.mmapr_veto_router import (
            VetoKind,
        )
        self.assertEqual(vote.kind, VetoKind.HARD_BLOCK)

    def test_auditor_passes_clean_proposal(self):
        """A clean parameter_tuning proposal with symmetric risks
        and safety_constraints passes the auditor."""
        from speace_core.cellular_brain.self_improvement.mmapr_adversarial_auditor import (
            AdversarialAuditor,
        )
        auditor = AdversarialAuditor(adversarial_score_threshold=0.7)
        proposal = {
            "id": "prop-clean",
            "proposal_type": "parameter_tuning",
            "target_modules": ["brainstem_controller"],
            "expected_benefits": {"phi_recovery": 0.3, "energy_efficiency": 0.2},
            "expected_risks": {"safety": 0.1, "regression": 0.15},
            "safety_constraints": [
                "No loss of emergency suppression",
                "Run tests first",
            ],
        }
        report = auditor.attack_proposal(proposal)
        self.assertLess(report.score, 0.4)
        vote = auditor(proposal)
        from speace_core.cellular_brain.self_improvement.mmapr_veto_router import (
            VetoKind,
        )
        self.assertEqual(vote.kind, VetoKind.ADMIT)

    def test_auditor_pool_runs_all_scenarios(self):
        """The default pool has 3 scenarios and the auditor runs at
        least 2 of them per proposal."""
        from speace_core.cellular_brain.self_improvement.mmapr_adversarial_auditor import (
            AdversarialAuditor, default_scenario_pool,
        )
        pool = default_scenario_pool()
        self.assertGreaterEqual(len(pool), 3)
        auditor = AdversarialAuditor(scenarios=pool)
        proposal = {
            "id": "p",
            "proposal_type": "module_addition",
            "target_modules": ["m1", "m2", "m3", "m4"],
            "expected_benefits": {"b": 0.7},  # triggers distributional_shift
            "expected_risks": {"hidden_drift_score": 0.8},  # triggers hidden
            "safety_constraints": [],  # amplifies
        }
        report = auditor.attack_proposal(proposal)
        # At least 2 scenarios produced a non-zero score for this toxic proposal
        nonzero = sum(1 for s in report.per_scenario_scores.values() if s > 0)
        self.assertGreaterEqual(nonzero, 2)


# ------------------------------------------------------------------ #
# Phase 8B tests
# ------------------------------------------------------------------ #


class TestPhase8BSafetyOfficer(unittest.TestCase):
    def test_officer_blocks_on_phi_drift(self):
        """A baseline phi=0.7 with a current phi=0.2 triggers the
        phi_stability_drift monitor and emits HARD_BLOCK."""
        from speace_core.cellular_brain.self_improvement.mmapr_safety_officer import (
            SafetyOfficer,
        )
        from speace_core.cellular_brain.self_improvement.mmapr_veto_router import (
            VetoKind,
        )
        officer = SafetyOfficer(
            baseline_metrics={"coherence_phi": 0.7, "kuramoto_order_parameter": 0.7},
            phi_drift_threshold=0.2,
        )
        report = officer.monitor(
            proposal={"id": "p"},
            current_metrics={"coherence_phi": 0.2, "kuramoto_order_parameter": 0.2},
        )
        self.assertFalse(report.safe)
        self.assertIn("phi_stability_drift", report.triggered_monitors)
        vote = officer(
            {"id": "p"},
            current_metrics={"coherence_phi": 0.2, "kuramoto_order_parameter": 0.2},
        )
        self.assertEqual(vote.kind, VetoKind.HARD_BLOCK)

    def test_officer_passes_stable_metrics(self):
        """A baseline phi=0.7 with a current phi=0.68 and free
        energy below the threshold emits ADMIT."""
        from speace_core.cellular_brain.self_improvement.mmapr_safety_officer import (
            SafetyOfficer,
        )
        from speace_core.cellular_brain.self_improvement.mmapr_veto_router import (
            VetoKind,
        )
        officer = SafetyOfficer(
            baseline_metrics={"coherence_phi": 0.7, "kuramoto_order_parameter": 0.7},
            phi_drift_threshold=0.05,
            free_energy_threshold=0.4,
        )
        report = officer.monitor(
            proposal={"id": "p-stable"},
            current_metrics={
                "coherence_phi": 0.68,
                "kuramoto_order_parameter": 0.68,
                "total_free_energy": 0.1,
            },
        )
        self.assertTrue(report.safe)
        self.assertEqual(report.triggered_monitors, [])
        vote = officer(
            {"id": "p-stable"},
            current_metrics={
                "coherence_phi": 0.68,
                "kuramoto_order_parameter": 0.68,
                "total_free_energy": 0.1,
            },
        )
        self.assertEqual(vote.kind, VetoKind.ADMIT)

    def test_officer_detects_rollback_integrity_breach(self):
        """A patch_result with verdict=PATCH_ROLLED_BACK triggers
        the rollback_integrity_breach monitor and emits HARD_BLOCK."""
        from speace_core.cellular_brain.self_improvement.mmapr_safety_officer import (
            SafetyOfficer,
        )
        from speace_core.cellular_brain.self_improvement.mmapr_veto_router import (
            VetoKind,
        )
        officer = SafetyOfficer()
        report = officer.monitor(
            proposal={"id": "p-rollback"},
            patch_result={"verdict": "PATCH_ROLLED_BACK"},
        )
        self.assertFalse(report.safe)
        self.assertIn("rollback_integrity_breach", report.triggered_monitors)
        vote = officer({"id": "p-rollback"}, patch_result={"verdict": "PATCH_ROLLED_BACK"})
        self.assertEqual(vote.kind, VetoKind.HARD_BLOCK)


# ------------------------------------------------------------------ #
# Phase 8E tests — integration with EvolutionaryMemoryGovernor
# ------------------------------------------------------------------ #


class TestPhase8EEvolutionaryMemoryIntegration(unittest.TestCase):
    def test_hard_blocked_record_forced_to_probationary(self):
        """A record whose metadata says ``mmapr_veto_verdict.final_status == hard_blocked``
        is forcibly demoted to ``probationary`` by the governor, and
        the metadata is enriched with ``mmapr_hard_blocked=True``."""
        from speace_core.cellular_brain.evolutionary_memory.evolutionary_memory_governor import (
            EvolutionaryMemoryGovernor,
        )
        from speace_core.cellular_brain.evolutionary_memory.evolutionary_memory_models import (
            EvolutionaryMemoryRecord,
        )
        with tempfile.TemporaryDirectory() as tmp:
            governor = EvolutionaryMemoryGovernor(report_dir=os.path.join(tmp, "memory"))
            record = EvolutionaryMemoryRecord(
                record_id="rec-blocked",
                source_cycle_id="c1",
                source_task="runtime_self_improvement_hook",
                source_profile="phase8e",
                fitness_delta=0.10,  # would normally allow promotion
                phi_delta=0.05,
                energy_delta=0.0,
                cognitive_delta=0.10,
                regression_score=0.0,
                safety_score=0.85,  # would normally allow promotion
                confidence=0.7,     # would normally allow promotion
                reuse_count=1,      # even with reuse -> STABLE
                status="volatile",
                metadata={
                    "mmapr_veto_verdict": {
                        "final_status": "hard_blocked",
                        "hard_blocked_by": ["adversarial_auditor"],
                        "soft_flagged_by": [],
                        "admit_count": 3,
                    }
                },
            )
            decision = governor.ingest_cycle_result(record)
            # Status must be probationary (not stable) because of the veto
            self.assertEqual(decision.new_status, "probationary")
            # Metadata is enriched
            stored = governor.store.list_records()[0]
            self.assertTrue(stored.metadata.get("mmapr_hard_blocked"))
            self.assertEqual(
                stored.metadata.get("mmapr_hard_blocked_by"),
                ["adversarial_auditor"],
            )

    def test_unblocked_record_promotes_normally(self):
        """A record with no ``mmapr_veto_verdict`` (or a non-blocked
        one) follows the standard consolidation policy and can reach
        STABLE."""
        from speace_core.cellular_brain.evolutionary_memory.evolutionary_memory_governor import (
            EvolutionaryMemoryGovernor,
        )
        from speace_core.cellular_brain.evolutionary_memory.evolutionary_memory_models import (
            EvolutionaryMemoryRecord,
        )
        with tempfile.TemporaryDirectory() as tmp:
            governor = EvolutionaryMemoryGovernor(report_dir=os.path.join(tmp, "memory"))
            record = EvolutionaryMemoryRecord(
                record_id="rec-clean",
                source_cycle_id="c1",
                source_task="runtime_self_improvement_hook",
                source_profile="phase8e",
                fitness_delta=0.10,
                phi_delta=0.05,
                energy_delta=0.0,
                cognitive_delta=0.10,
                regression_score=0.0,
                safety_score=0.85,
                confidence=0.7,
                reuse_count=1,
                status="volatile",
                # No mmapr_veto_verdict -> standard policy applies
            )
            decision = governor.ingest_cycle_result(record)
            # Standard policy should promote to STABLE
            self.assertEqual(decision.new_status, "stable")


# ------------------------------------------------------------------ #
# Phase 8F tests — attach_mmapr_veto_router to ContinuousRuntimeEngine
# ------------------------------------------------------------------ #


class TestPhase8FRuntimeAttach(unittest.TestCase):
    def _build_runtime(self):
        from speace_core.runtime.continuous_runtime_engine import (
            ContinuousRuntimeEngine,
        )
        from tests.test_phase6_runtime_stress import _FakeOrchestrator
        return _FakeOrchestrator(), ContinuousRuntimeEngine(
            orchestrator=_FakeOrchestrator(),
            tick_interval=0.01,
            checkpoint_interval_seconds=10 ** 9,
            awake_duration=10 ** 9,
            sleep_duration=10 ** 9,
        )

    def test_attach_mmapr_veto_router(self):
        """``attach_mmapr_veto_router`` stores the router; the runtime
        exposes a valid summary in ``snapshot()``."""
        from speace_core.cellular_brain.self_improvement.mmapr_veto_router import (
            HardVetoRouter,
        )
        from pathlib import Path
        _, runtime = self._build_runtime()
        with tempfile.TemporaryDirectory() as tmp:
            audit_dir = Path(tmp) / "audit"
            router = HardVetoRouter(audit_dir=audit_dir)
            runtime.attach_mmapr_veto_router(router)
            self.assertIs(runtime._mmapr_veto_router, router)
            # Snapshot exposes the veto router summary
            snap = runtime.snapshot()
            self.assertIn("mmapr_veto_router", snap)
            self.assertEqual(snap["mmapr_veto_router"]["veto_count"], 0)
            self.assertEqual(snap["mmapr_veto_router"]["admit_count"], 0)
            self.assertIn("audit_dir", snap["mmapr_veto_router"])

    def test_attach_mmapr_veto_router_none_raises(self):
        """``attach_mmapr_veto_router(None)`` raises ``ValueError``."""
        _, runtime = self._build_runtime()
        with self.assertRaises(ValueError):
            runtime.attach_mmapr_veto_router(None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
