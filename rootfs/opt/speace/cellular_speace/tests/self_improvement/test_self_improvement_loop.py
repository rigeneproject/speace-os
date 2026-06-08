import json
import tempfile
from datetime import datetime, timezone

import pytest

from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.self_improvement.architecture_rewriter import (
    ArchitectureRewriteProposal,
    RewriteSimulationResult,
    SelfImprovementCycleResult,
)
from speace_core.cellular_brain.self_improvement.limitation_detector import (
    LimitationDetector,
)
from speace_core.cellular_brain.self_improvement.proposal_store import ProposalStore
from speace_core.cellular_brain.self_improvement.self_improvement_loop import (
    SelfImprovementLoop,
)


class FakeMorphologicalMemory:
    def __init__(self):
        self.events = []

    def log_event(self, event):
        self.events.append(event)

    def load(self):
        pass


class TestSelfImprovementLoop:
    def test_run_detection_cycle_creates_result(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProposalStore(base_path=tmpdir)
            loop = SelfImprovementLoop(proposal_store=store)
            metrics = {
                "cognitive_delta": -0.05,
                "phi_delta": -0.04,
            }
            result = loop.run_detection_cycle(metrics)
            assert isinstance(result, SelfImprovementCycleResult)
            assert result.cycle_id.startswith("cycle-")
            assert len(result.detected_limitations) == 2
            assert len(result.diagnoses) == 2

    def test_cycle_detects_semantic_association_missing_after_t43c_metrics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProposalStore(base_path=tmpdir)
            loop = SelfImprovementLoop(proposal_store=store)
            metrics = {
                "semantic_assembly_count": 5,
                "semantic_association_count": 0,
                "semantic_recall_success_rate": 0.5,
                "semantic_memory_enabled": True,
            }
            result = loop.run_detection_cycle(metrics)
            categories = [s.category for s in result.detected_limitations]
            assert "semantic_association_missing" in categories

    def test_cycle_generates_safe_t44_proposal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProposalStore(base_path=tmpdir)
            loop = SelfImprovementLoop(proposal_store=store)
            metrics = {
                "semantic_assembly_count": 5,
                "semantic_association_count": 0,
                "semantic_recall_success_rate": 0.5,
                "semantic_memory_enabled": True,
            }
            result = loop.run_detection_cycle(metrics)
            titles = [p.title for p in result.proposals]
            assert any("T44" in t for t in titles)

    def test_simulate_proposal_accepts_safe_low_risk_patch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProposalStore(base_path=tmpdir)
            loop = SelfImprovementLoop(proposal_store=store)
            proposal = ArchitectureRewriteProposal(
                id="prop-safe",
                diagnosis_id="diag-001",
                title="Safe Parameter Tuning",
                proposal_type="parameter_tuning",
                rationale="Test rationale",
                expected_benefits={"recall_rate": 0.6},
                expected_risks={"safety": 0.05, "regression": 0.05},
                implementation_plan=["Tune threshold"],
                rollback_plan=["Restore threshold"],
                safety_constraints=["No core mutation", "Run tests first"],
                created_at="2024-01-01T00:00:00Z",
            )
            sim = loop.simulate_proposal(proposal)
            assert sim.safety_passed is True
            assert sim.acceptance_score >= 0.55
            assert sim.recommendation == "accept"

    def test_simulate_proposal_rejects_unsafe_patch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProposalStore(base_path=tmpdir)
            loop = SelfImprovementLoop(proposal_store=store)
            proposal = ArchitectureRewriteProposal(
                id="prop-unsafe",
                diagnosis_id="diag-001",
                title="Unsafe Genome Mutation",
                proposal_type="genome_mutation",
                rationale="Test rationale",
                expected_benefits={"fitness": 0.3},
                expected_risks={"safety": 0.30, "regression": 0.40},
                implementation_plan=["Mutate genome"],
                rollback_plan=["Revert genome"],
                safety_constraints=[],
                created_at="2024-01-01T00:00:00Z",
            )
            sim = loop.simulate_proposal(proposal)
            assert sim.safety_passed is False
            assert sim.recommendation == "reject"

    def test_cycle_logs_morphological_events(self):
        fake_memory = FakeMorphologicalMemory()
        loop = SelfImprovementLoop(memory=fake_memory)
        metrics = {
            "semantic_assembly_count": 3,
            "semantic_association_count": 0,
        }
        result = loop.run_detection_cycle(metrics)
        event_types = [e.event_type for e in fake_memory.events]
        assert any("LIMITATION_DETECTED" in str(et) for et in event_types)
        assert any("LIMITATION_DIAGNOSED" in str(et) for et in event_types)
        assert any("ARCHITECTURE_PROPOSAL_CREATED" in str(et) for et in event_types)
        assert any("SELF_IMPROVEMENT_CYCLE_COMPLETED" in str(et) for et in event_types)

    def test_generate_markdown_report_contains_diagnoses_and_proposals(self):
        loop = SelfImprovementLoop()
        result = SelfImprovementCycleResult(
            cycle_id="cycle-report",
            detected_limitations=[],
            diagnoses=[],
            proposals=[],
            simulations=[],
            accepted_proposals=[],
            rejected_proposals=[],
            final_verdict="NO_LIMITATION_DETECTED",
        )
        md = loop.generate_markdown_report(result)
        assert "T45" in md
        assert "NO_LIMITATION_DETECTED" in md
        assert "## Detected Limitations" in md
        assert "## Final Verdict" in md

    def test_generate_json_report_is_valid_json(self):
        loop = SelfImprovementLoop()
        result = SelfImprovementCycleResult(
            cycle_id="cycle-json",
            final_verdict="SAFE_PROPOSAL_GENERATED",
        )
        json_str = loop.generate_json_report(result)
        parsed = json.loads(json_str)
        assert parsed["cycle_id"] == "cycle-json"
        assert parsed["final_verdict"] == "SAFE_PROPOSAL_GENERATED"

    def test_run_from_audit_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProposalStore(base_path=tmpdir)
            loop = SelfImprovementLoop(proposal_store=store)
            report = {
                "verdict": "POLICY_MAJOR_REGRESSION",
                "semantic_recall_success_rate": 0.1,
            }
            result = loop.run_from_audit_report(report)
            assert len(result.detected_limitations) >= 1
            assert result.final_verdict in (
                "SAFE_PROPOSAL_GENERATED",
                "PROPOSAL_ACCEPTED_FOR_NEXT_TASK",
                "REGRESSION_BLOCKED",
            )

    def test_accept_or_reject_boundary(self):
        loop = SelfImprovementLoop()
        sim = RewriteSimulationResult(
            proposal_id="p1",
            safety_passed=True,
            acceptance_score=0.55,
            regression_guard_verdict="POLICY_SAFE",
        )
        assert loop.accept_or_reject(sim) == "accept"

        sim2 = RewriteSimulationResult(
            proposal_id="p2",
            safety_passed=True,
            acceptance_score=0.34,
            regression_guard_verdict="POLICY_SAFE",
        )
        assert loop.accept_or_reject(sim2) == "reject"

        sim3 = RewriteSimulationResult(
            proposal_id="p3",
            safety_passed=False,
            acceptance_score=0.8,
            regression_guard_verdict="POLICY_SAFE",
        )
        assert loop.accept_or_reject(sim3) == "reject"

    def test_no_limitation_detected_when_healthy(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProposalStore(base_path=tmpdir)
            loop = SelfImprovementLoop(proposal_store=store)
            metrics = {
                "cognitive_delta": 0.01,
                "phi_delta": 0.01,
                "energy_delta": 0.01,
                "semantic_recall_success_rate": 0.5,
                "semantic_memory_enabled": True,
                "semantic_assembly_count": 0,
            }
            result = loop.run_detection_cycle(metrics)
            assert result.final_verdict == "NO_LIMITATION_DETECTED"
            assert len(result.detected_limitations) == 0

    def test_proposal_status_updated_after_simulation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProposalStore(base_path=tmpdir)
            loop = SelfImprovementLoop(proposal_store=store)
            metrics = {
                "cognitive_delta": -0.05,
            }
            result = loop.run_detection_cycle(metrics)
            for proposal in result.proposals:
                assert proposal.status in ("accepted", "rejected", "simulated")

    def test_orchestrator_manual_self_improvement_cycle(self):
        from speace_core.dna.models import SharedGenome
        from speace_core.orchestrator import CellularBrainOrchestrator

        genome = SharedGenome()
        orch = CellularBrainOrchestrator.build_mvp(genome)
        orch.self_improvement_enabled = True
        loop = orch.get_self_improvement_loop()
        assert loop is not None
        assert loop.orchestrator is orch
        metrics = {
            "semantic_assembly_count": 3,
            "semantic_association_count": 0,
            "semantic_recall_success_rate": 0.5,
            "semantic_memory_enabled": True,
        }
        result = orch.run_self_improvement_cycle(metrics)
        assert result.cycle_id.startswith("cycle-")
        assert len(result.detected_limitations) >= 1
        assert "semantic_association_missing" in [s.category for s in result.detected_limitations]
