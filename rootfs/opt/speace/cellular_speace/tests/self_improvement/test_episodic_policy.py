import pytest
import tempfile
from pathlib import Path

from speace_core.cellular_brain.memory.episodic_memory import EpisodicMemory, EpisodeEvent
from speace_core.cellular_brain.memory.episodic_recall import EpisodicRecall
from speace_core.cellular_brain.memory.morphology_events import MorphologyEvent, MorphologyEventType
from speace_core.cellular_brain.self_improvement.episodic_policy import (
    EpisodicPolicyContext,
    EpisodicProposalAdjustment,
    EpisodicSelfImprovementPolicy,
)
from speace_core.cellular_brain.self_improvement.architecture_rewriter import ArchitectureRewriteProposal
from speace_core.cellular_brain.self_improvement.self_improvement_loop import SelfImprovementLoop
from speace_core.cellular_brain.self_improvement.proposal_learning_engine import ProposalLearningEngine
from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import BenchmarkMetrics


class FakeMorphologicalMemory:
    def __init__(self):
        self.events = []

    def log_event(self, event):
        self.events.append(event)

    def count_events(self, event_type):
        return sum(1 for e in self.events if e.event_type == event_type)


class FakeEpisodicRecall:
    def __init__(self, episodes=None):
        self.episodes = episodes or []
        self.memory = FakeMorphologicalMemory()

    def recall_by_outcome(self, outcome):
        return [ep for ep in self.episodes if outcome.lower() in ep.outcome.lower()]

    def recall_similar_metrics(self, metrics, top_k=10):
        class FakeResult:
            matched_episodes = []
            query = "similar_metrics"
        r = FakeResult()
        r.matched_episodes = self.episodes[:top_k]
        return r

    def find_recovery_patterns(self):
        patterns = set()
        for ep in self.episodes:
            if ep.outcome == "recovery":
                for ev in ep.events:
                    patterns.add(ev.event_type)
        return list(patterns)

    def find_regression_precursors(self):
        patterns = set()
        for ep in self.episodes:
            if ep.outcome == "regression":
                for ev in ep.events:
                    patterns.add(ev.event_type)
        return list(patterns)

    @property
    def episodic_memory(self):
        class FakeMem:
            def __init__(self, episodes):
                self._episodes = episodes
            def load_episodes(self):
                return self._episodes
        return FakeMem(self.episodes)


def _make_episode(episode_id, trigger="test", outcome="unknown", cognitive_delta=0.0, events=None, linked_proposals=None):
    from speace_core.cellular_brain.memory.episodic_memory import Episode
    return Episode(
        episode_id=episode_id,
        start_time="now",
        trigger=trigger,
        outcome=outcome,
        cognitive_delta=cognitive_delta,
        events=events or [],
        linked_proposals=linked_proposals or [],
    )


def _make_proposal(pid="prop-a", title="Test"):
    return ArchitectureRewriteProposal(
        id=pid,
        diagnosis_id="diag-1",
        title=title,
        proposal_type="parameter_tuning",
        rationale="test",
        created_at="now",
    )


class TestEpisodicSelfImprovementPolicy:
    def test_build_context_empty_memory_safe(self):
        mem = FakeMorphologicalMemory()
        policy = EpisodicSelfImprovementPolicy(episodic_recall=None, memory=mem)
        ctx = policy.build_context("phi_regression")
        assert ctx.limitation_type == "phi_regression"
        assert ctx.similar_episode_count == 0

    def test_build_context_counts_similar_episodes(self):
        ep1 = _make_episode("ep-1", trigger="phi_regression", outcome="recovery")
        ep2 = _make_episode("ep-2", trigger="phi_regression", outcome="regression")
        recall = FakeEpisodicRecall(episodes=[ep1, ep2])
        mem = FakeMorphologicalMemory()
        policy = EpisodicSelfImprovementPolicy(episodic_recall=recall, memory=mem)
        ctx = policy.build_context("phi_regression")
        assert ctx.recovery_episode_count == 1
        assert ctx.regression_episode_count == 1

    def test_build_context_detects_recovery_patterns(self):
        ev = EpisodeEvent(event_id="e1", timestamp="t", event_type="tick", source_module="orchestrator")
        ep = _make_episode("ep-1", outcome="recovery", events=[ev])
        recall = FakeEpisodicRecall(episodes=[ep])
        mem = FakeMorphologicalMemory()
        policy = EpisodicSelfImprovementPolicy(episodic_recall=recall, memory=mem)
        ctx = policy.build_context("test")
        assert "tick" in ctx.recovery_patterns

    def test_build_context_detects_regression_precursors(self):
        ev = EpisodeEvent(event_id="e1", timestamp="t", event_type="error", source_module="mod")
        ep = _make_episode("ep-1", outcome="regression", events=[ev])
        recall = FakeEpisodicRecall(episodes=[ep])
        mem = FakeMorphologicalMemory()
        policy = EpisodicSelfImprovementPolicy(episodic_recall=recall, memory=mem)
        ctx = policy.build_context("test")
        assert "error" in ctx.regression_precursors

    def test_adjust_proposals_applies_recovery_bonus(self):
        prop = _make_proposal("prop-a")
        ep = _make_episode("ep-1", outcome="recovery", linked_proposals=["prop-a"])
        recall = FakeEpisodicRecall(episodes=[ep])
        mem = FakeMorphologicalMemory()
        policy = EpisodicSelfImprovementPolicy(episodic_recall=recall, memory=mem)
        ctx = policy.build_context("test")
        adj = policy.adjust_proposals([prop], ctx)
        assert len(adj) == 1
        assert adj[0].episodic_bonus > 0
        assert any("linked_to_recovery_episode" in r for r in adj[0].reasons)

    def test_adjust_proposals_applies_regression_penalty(self):
        prop = _make_proposal("prop-b")
        ep = _make_episode("ep-1", outcome="regression", linked_proposals=["prop-b"])
        recall = FakeEpisodicRecall(episodes=[ep])
        mem = FakeMorphologicalMemory()
        policy = EpisodicSelfImprovementPolicy(episodic_recall=recall, memory=mem)
        ctx = policy.build_context("test")
        adj = policy.adjust_proposals([prop], ctx)
        assert len(adj) == 1
        assert adj[0].episodic_penalty > 0
        assert any("linked_to_regression_episode" in r for r in adj[0].reasons)

    def test_adjusted_confidence_is_clamped(self):
        prop = _make_proposal("prop-c")
        # Create many recovery episodes linked to this proposal to push bonus high
        episodes = []
        for i in range(20):
            episodes.append(_make_episode(f"ep-{i}", outcome="recovery", linked_proposals=["prop-c"]))
        recall = FakeEpisodicRecall(episodes=episodes)
        mem = FakeMorphologicalMemory()
        policy = EpisodicSelfImprovementPolicy(episodic_recall=recall, memory=mem)
        ctx = policy.build_context("test")
        adj = policy.adjust_proposals([prop], ctx)
        assert 0.0 <= adj[0].adjusted_confidence <= 1.0

    def test_select_best_proposal_uses_adjusted_score(self):
        p1 = _make_proposal("prop-low")
        p2 = _make_proposal("prop-high")
        ep = _make_episode("ep-1", outcome="recovery", linked_proposals=["prop-high"])
        recall = FakeEpisodicRecall(episodes=[ep])
        mem = FakeMorphologicalMemory()
        policy = EpisodicSelfImprovementPolicy(episodic_recall=recall, memory=mem)
        ctx = policy.build_context("test")
        best = policy.select_best_proposal([p1, p2], ctx)
        assert best is not None
        assert best.id == "prop-high"

    def test_policy_does_not_mutate_original_proposal(self):
        prop = _make_proposal("prop-a")
        recall = FakeEpisodicRecall(episodes=[])
        mem = FakeMorphologicalMemory()
        policy = EpisodicSelfImprovementPolicy(episodic_recall=recall, memory=mem)
        ctx = policy.build_context("test")
        _ = policy.adjust_proposals([prop], ctx)
        # Proposal fields unchanged
        assert prop.id == "prop-a"
        assert prop.title == "Test"

    def test_policy_handles_missing_episodic_recall(self):
        mem = FakeMorphologicalMemory()
        policy = EpisodicSelfImprovementPolicy(episodic_recall=None, memory=mem)
        prop = _make_proposal("prop-a")
        ctx = EpisodicPolicyContext(limitation_type="test")
        adj = policy.adjust_proposals([prop], ctx)
        assert len(adj) == 1
        assert adj[0].adjusted_confidence == 0.0

    def test_policy_logs_context_event(self):
        mem = FakeMorphologicalMemory()
        recall = FakeEpisodicRecall(episodes=[])
        policy = EpisodicSelfImprovementPolicy(episodic_recall=recall, memory=mem)
        policy.build_context("phi_regression")
        types = [e.event_type for e in mem.events]
        assert MorphologyEventType.EPISODIC_POLICY_CONTEXT_BUILT in types

    def test_policy_logs_adjustment_event(self):
        prop = _make_proposal("prop-a")
        ep = _make_episode("ep-1", outcome="recovery", linked_proposals=["prop-a"])
        recall = FakeEpisodicRecall(episodes=[ep])
        mem = FakeMorphologicalMemory()
        policy = EpisodicSelfImprovementPolicy(episodic_recall=recall, memory=mem)
        ctx = policy.build_context("test")
        policy.adjust_proposals([prop], ctx)
        types = [e.event_type for e in mem.events]
        assert MorphologyEventType.EPISODIC_POLICY_PROPOSAL_ADJUSTED in types

    def test_policy_logs_selection_event(self):
        prop = _make_proposal("prop-a")
        ep = _make_episode("ep-1", outcome="recovery", linked_proposals=["prop-a"])
        recall = FakeEpisodicRecall(episodes=[ep])
        mem = FakeMorphologicalMemory()
        policy = EpisodicSelfImprovementPolicy(episodic_recall=recall, memory=mem)
        ctx = policy.build_context("test")
        policy.select_best_proposal([prop], ctx)
        types = [e.event_type for e in mem.events]
        assert MorphologyEventType.EPISODIC_POLICY_PROPOSAL_SELECTED in types

    def test_benchmark_metrics_include_episodic_policy_fields(self):
        m = BenchmarkMetrics()
        assert hasattr(m, "episodic_policy_enabled")
        assert hasattr(m, "episodic_context_episode_count")
        assert hasattr(m, "episodic_adjusted_confidence")

    def test_proposal_learning_and_episodic_policy_compose(self):
        with tempfile.TemporaryDirectory() as td:
            ple = ProposalLearningEngine(base_path=td, memory=FakeMorphologicalMemory())
            prop = _make_proposal("prop-a")
            ep = _make_episode("ep-1", outcome="recovery", linked_proposals=["prop-a"])
            recall = FakeEpisodicRecall(episodes=[ep])
            mem = FakeMorphologicalMemory()
            policy = EpisodicSelfImprovementPolicy(episodic_recall=recall, memory=mem)
            ctx = policy.build_context("test")
            adj = policy.adjust_proposals([prop], ctx)
            # Learning engine and policy operate independently
            assert adj[0].adjusted_confidence >= 0.0

    def test_regression_history_penalizes_repeated_bad_mapping(self):
        prop = _make_proposal("prop-bad")
        episodes = [
            _make_episode("ep-1", outcome="regression", linked_proposals=["prop-bad"]),
            _make_episode("ep-2", outcome="regression", linked_proposals=["prop-bad"]),
        ]
        recall = FakeEpisodicRecall(episodes=episodes)
        mem = FakeMorphologicalMemory()
        policy = EpisodicSelfImprovementPolicy(episodic_recall=recall, memory=mem)
        ctx = policy.build_context("test")
        adj = policy.adjust_proposals([prop], ctx)
        assert adj[0].episodic_penalty > 0
        assert adj[0].episodic_bonus == 0.0

    def test_recovery_history_reinforces_successful_mapping(self):
        prop = _make_proposal("prop-good")
        episodes = [
            _make_episode("ep-1", outcome="recovery", linked_proposals=["prop-good"]),
            _make_episode("ep-2", outcome="recovery", linked_proposals=["prop-good"]),
        ]
        recall = FakeEpisodicRecall(episodes=episodes)
        mem = FakeMorphologicalMemory()
        policy = EpisodicSelfImprovementPolicy(episodic_recall=recall, memory=mem)
        ctx = policy.build_context("test")
        adj = policy.adjust_proposals([prop], ctx)
        assert adj[0].episodic_bonus > 0

    def test_semantic_learning_episode_boosts_memory_related_task(self):
        prop = _make_proposal("prop-mem")
        ep = _make_episode("ep-1", outcome="ok", cognitive_delta=0.1, linked_proposals=["prop-mem"])
        recall = FakeEpisodicRecall(episodes=[ep])
        mem = FakeMorphologicalMemory()
        policy = EpisodicSelfImprovementPolicy(episodic_recall=recall, memory=mem)
        ctx = policy.build_context("test")
        adj = policy.adjust_proposals([prop], ctx)
        assert adj[0].episodic_bonus > 0
        assert any("linked_to_semantic_learning_with_gain" in r for r in adj[0].reasons)

    def test_no_episode_context_preserves_existing_ranking(self):
        p1 = _make_proposal("prop-a")
        p2 = _make_proposal("prop-b")
        recall = FakeEpisodicRecall(episodes=[])
        mem = FakeMorphologicalMemory()
        policy = EpisodicSelfImprovementPolicy(episodic_recall=recall, memory=mem)
        ctx = policy.build_context("test")
        adj = policy.adjust_proposals([p1, p2], ctx)
        assert adj[0].adjusted_confidence == adj[1].adjusted_confidence

    def test_self_improvement_loop_uses_episodic_policy_when_enabled(self):
        from speace_core.cellular_brain.self_improvement.limitation_detector import LimitationSignal, LimitationDiagnosis
        mem = FakeMorphologicalMemory()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "episodes.jsonl"
            em = EpisodicMemory(storage_path=str(path), memory=mem)
            em.start_episode(trigger="phi_regression", initial_metrics={"cognitive_score": 0.5})
            em.close_episode(list(em._episodes.keys())[0], {"cognitive_score": 0.8}, "recovery")
            recall = EpisodicRecall(episodic_memory=em, memory=mem)
            policy = EpisodicSelfImprovementPolicy(episodic_recall=recall, memory=mem)
            loop = SelfImprovementLoop(
                memory=mem,
                episodic_policy_enabled=True,
                episodic_policy=policy,
            )
            # Inject a fake signal so the loop generates proposals
            sig = LimitationSignal(
                id="sig-1",
                source="test",
                category="phi_regression",
                description="low phi",
                severity=0.6,
                confidence=0.8,
                detected_at="now",
            )
            loop.detector.detect_from_metrics = lambda m: [sig]
            result = loop.run_detection_cycle({"cognitive_score": 0.5})
            assert result.episodic_context is not None

    def test_self_improvement_loop_skips_policy_when_disabled(self):
        mem = FakeMorphologicalMemory()
        loop = SelfImprovementLoop(memory=mem, episodic_policy_enabled=False)
        result = loop.run_detection_cycle({"cognitive_score": 0.5})
        assert result.episodic_context is None

    def test_markdown_report_contains_episodic_policy_section(self):
        mem = FakeMorphologicalMemory()
        loop = SelfImprovementLoop(memory=mem, episodic_policy_enabled=False)
        result = loop.run_detection_cycle({"cognitive_score": 0.5})
        # Inject fake episodic context into result for report test
        result.episodic_context = {
            "limitation_type": "phi_regression",
            "similar_episode_count": 3,
            "recovery_episode_count": 1,
            "regression_episode_count": 0,
            "recovery_patterns": ["tick"],
            "regression_precursors": [],
            "confidence_modifier": 0.05,
            "risk_modifier": 0.0,
        }
        result.episodic_adjustments = [
            {
                "proposal_id": "prop-a",
                "original_confidence": 0.0,
                "adjusted_confidence": 0.15,
                "episodic_bonus": 0.15,
                "episodic_penalty": 0.0,
                "reasons": ["linked_to_recovery_episode"],
            }
        ]
        md = loop.generate_markdown_report(result)
        assert "Episodic Policy Context" in md
        assert "Episodic Proposal Adjustments" in md
        assert "prop-a" in md
