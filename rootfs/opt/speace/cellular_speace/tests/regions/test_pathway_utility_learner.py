import pytest

from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.regions.pathway_utility_learner import (
    PathwayUtilityLearner,
    PathwayUtilityRecord,
    PathwayRewardSignal,
    PathwayUtilityLearningResult,
)


@pytest.fixture
def learner():
    return PathwayUtilityLearner(alpha=0.2, cost_penalty=0.5)


# ---------------------------------------------------------------------------
# 1. Importabilità
# ---------------------------------------------------------------------------

def test_learner_importable():
    assert PathwayUtilityLearner is not None
    assert PathwayUtilityRecord is not None
    assert PathwayRewardSignal is not None
    assert PathwayUtilityLearningResult is not None


# ---------------------------------------------------------------------------
# 2. compute_reward_signal formula
# ---------------------------------------------------------------------------

def test_compute_reward_signal_positive():
    before = {"speace_cognitive_score": 0.4, "coherence_phi": 0.2, "energy_efficiency": 0.5, "functional_improvement": 0.1}
    after = {"speace_cognitive_score": 0.5, "coherence_phi": 0.3, "energy_efficiency": 0.6, "functional_improvement": 0.2}
    signal = PathwayUtilityLearner.compute_reward_signal(before, after, routing_cost=0.0, plasticity_cost=0.0)
    assert signal.composite_reward > 0.0
    assert -1.0 <= signal.composite_reward <= 1.0


def test_compute_reward_signal_negative_costs():
    before = {"speace_cognitive_score": 0.4, "coherence_phi": 0.2, "energy_efficiency": 0.5, "functional_improvement": 0.1}
    after = {"speace_cognitive_score": 0.4, "coherence_phi": 0.2, "energy_efficiency": 0.5, "functional_improvement": 0.1}
    signal = PathwayUtilityLearner.compute_reward_signal(before, after, routing_cost=0.5, plasticity_cost=0.5)
    assert signal.composite_reward <= 0.0


def test_compute_reward_signal_clamped():
    before = {"speace_cognitive_score": 0.0, "coherence_phi": 0.0, "energy_efficiency": 0.0, "functional_improvement": 0.0}
    after = {"speace_cognitive_score": 10.0, "coherence_phi": 10.0, "energy_efficiency": 10.0, "functional_improvement": 10.0}
    signal = PathwayUtilityLearner.compute_reward_signal(before, after)
    assert signal.composite_reward == 1.0


def test_compute_reward_signal_clamped_negative():
    before = {"speace_cognitive_score": 10.0, "coherence_phi": 10.0, "energy_efficiency": 10.0, "functional_improvement": 10.0}
    after = {"speace_cognitive_score": 0.0, "coherence_phi": 0.0, "energy_efficiency": 0.0, "functional_improvement": 0.0}
    signal = PathwayUtilityLearner.compute_reward_signal(before, after, routing_cost=5.0, plasticity_cost=5.0)
    assert signal.composite_reward == -1.0


# ---------------------------------------------------------------------------
# 3. update_pathway_utility EMA
# ---------------------------------------------------------------------------

def test_update_pathway_utility_creates_record(learner):
    signal = PathwayRewardSignal(composite_reward=0.5)
    rec = learner.update_pathway_utility("s->h", "sensory", "hippocampus", signal)
    assert rec.pathway_id == "s->h"
    assert rec.reward_ema > 0.0
    assert rec.utility_score > 0.0
    assert rec.update_count == 1


def test_update_pathway_utility_negative_reward(learner):
    signal = PathwayRewardSignal(composite_reward=-0.5)
    rec = learner.update_pathway_utility("s->h", "sensory", "hippocampus", signal)
    assert rec.negative_updates == 1
    assert rec.positive_updates == 0
    assert rec.utility_score < 0.0


def test_update_pathway_utility_multiple_updates(learner):
    signal1 = PathwayRewardSignal(composite_reward=0.5)
    signal2 = PathwayRewardSignal(composite_reward=0.5)
    learner.update_pathway_utility("s->h", "sensory", "hippocampus", signal1)
    rec = learner.update_pathway_utility("s->h", "sensory", "hippocampus", signal2)
    assert rec.update_count == 2
    assert rec.positive_updates == 2


# ---------------------------------------------------------------------------
# 4. update_pathway_utility records memory events
# ---------------------------------------------------------------------------

def test_update_records_memory_events(learner):
    mem = MorphologicalMemory()
    signal = PathwayRewardSignal(composite_reward=0.5)
    learner.update_pathway_utility("s->h", "sensory", "hippocampus", signal, memory=mem)
    types = [e.event_type for e in mem.events]
    assert MorphologyEventType.PATHWAY_UTILITY_POSITIVE in types
    assert MorphologyEventType.PATHWAY_REWARD_COMPUTED in types


def test_update_records_negative_event(learner):
    mem = MorphologicalMemory()
    signal = PathwayRewardSignal(composite_reward=-0.5)
    learner.update_pathway_utility("s->h", "sensory", "hippocampus", signal, memory=mem)
    types = [e.event_type for e in mem.events]
    assert MorphologyEventType.PATHWAY_UTILITY_NEGATIVE in types


# ---------------------------------------------------------------------------
# 5. apply_utility_gate
# ---------------------------------------------------------------------------

def test_utility_gate_no_history(learner):
    proceed, reason = learner.apply_utility_gate("unknown", "ltp")
    assert proceed is True
    assert reason == "no_utility_history"


def test_utility_gate_negative_blocks_ltp(learner):
    signal = PathwayRewardSignal(composite_reward=-0.5)
    learner.update_pathway_utility("s->h", "sensory", "hippocampus", signal)
    proceed, reason = learner.apply_utility_gate("s->h", "ltp")
    assert proceed is False
    assert reason == "utility_negative_blocks_ltp"


def test_utility_gate_negative_allows_ltd(learner):
    signal = PathwayRewardSignal(composite_reward=-0.5)
    learner.update_pathway_utility("s->h", "sensory", "hippocampus", signal)
    proceed, reason = learner.apply_utility_gate("s->h", "ltd")
    assert proceed is True
    assert reason == "utility_negative_allows_ltd"


def test_utility_gate_positive_allows_ltp(learner):
    signal = PathwayRewardSignal(composite_reward=0.5)
    learner.update_pathway_utility("s->h", "sensory", "hippocampus", signal)
    proceed, reason = learner.apply_utility_gate("s->h", "ltp")
    assert proceed is True
    assert reason == "utility_positive_allows_ltp"


# ---------------------------------------------------------------------------
# 6. get_utility_score
# ---------------------------------------------------------------------------

def test_get_utility_score_unknown(learner):
    assert learner.get_utility_score("unknown") == 0.0


def test_get_utility_score_known(learner):
    signal = PathwayRewardSignal(composite_reward=0.5)
    learner.update_pathway_utility("s->h", "sensory", "hippocampus", signal)
    assert learner.get_utility_score("s->h") > 0.0


# ---------------------------------------------------------------------------
# 7. summarize_utilities
# ---------------------------------------------------------------------------

def test_summarize_utilities_empty(learner):
    summary = learner.summarize_utilities()
    assert summary["count"] == 0


def test_summarize_utilities_with_data(learner):
    learner.update_pathway_utility("s->h", "sensory", "hippocampus", PathwayRewardSignal(composite_reward=0.5))
    learner.update_pathway_utility("h->p", "hippocampus", "prefrontal", PathwayRewardSignal(composite_reward=-0.3))
    summary = learner.summarize_utilities()
    assert summary["count"] == 2
    assert summary["positive_count"] == 1
    assert summary["negative_count"] == 1


# ---------------------------------------------------------------------------
# 8. reset_utilities
# ---------------------------------------------------------------------------

def test_reset_utilities(learner):
    learner.update_pathway_utility("s->h", "sensory", "hippocampus", PathwayRewardSignal(composite_reward=0.5))
    learner.reset_utilities()
    assert learner.get_utility_score("s->h") == 0.0
    assert len(learner._utilities) == 0


# ---------------------------------------------------------------------------
# 9. reward_all_pathways con registry vuoto
# ---------------------------------------------------------------------------

def test_reward_all_pathways_empty_registry(learner):
    from speace_core.cellular_brain.regions.region_registry import RegionRegistry
    registry = RegionRegistry()
    before = {"speace_cognitive_score": 0.4}
    after = {"speace_cognitive_score": 0.5}
    result = learner.reward_all_pathways(registry, before, after)
    assert result.updated_pathways == 0
