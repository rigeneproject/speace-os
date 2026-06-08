import pytest

from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.regions.pathway_plasticity_tuner import (
    PathwayPlasticityTuner,
    PathwayTuningProfile,
    PathwayTuningResult,
)
from speace_core.cellular_brain.regions.region_plasticity_trigger import (
    RegionPlasticityTriggerResult,
)
from speace_core.cellular_brain.regulation.homeostasis_engine import SystemMetrics


@pytest.fixture
def tuner():
    return PathwayPlasticityTuner()


@pytest.fixture
def profile():
    return PathwayTuningProfile(
        profile_id="test",
        name="test_profile",
        min_causal_score=0.05,
        ltp_scale=1.0,
        ltd_scale=1.0,
        phi_guard_enabled=False,
        energy_guard_enabled=False,
        confidence_guard_enabled=False,
    )


@pytest.fixture
def trigger_result():
    return RegionPlasticityTriggerResult(
        source_region_id="sensory",
        target_region_id="hippocampus",
        triggered=True,
        trigger_type="routing_aware",
        causal_score=0.2,
        recommended_update="ltp",
        confidence=0.5,
    )


# ---------------------------------------------------------------------------
# 1. Importabilità
# ---------------------------------------------------------------------------

def test_tuner_importable():
    assert PathwayPlasticityTuner is not None
    assert PathwayTuningProfile is not None
    assert PathwayTuningResult is not None


# ---------------------------------------------------------------------------
# 2. Almeno 10 profili di default
# ---------------------------------------------------------------------------

def test_default_profiles_count(tuner):
    profiles = tuner.default_profiles()
    assert len(profiles) >= 10


def test_default_profiles_unique_ids(tuner):
    profiles = tuner.default_profiles()
    ids = [p.profile_id for p in profiles]
    assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# 3. Gate: passa con causal_score sufficiente
# ---------------------------------------------------------------------------

def test_gate_passes_with_good_causal(tuner, trigger_result, profile):
    proceed, reason = tuner.gate_update(trigger_result, profile)
    assert proceed is True
    assert reason == "passed"


# ---------------------------------------------------------------------------
# 4. Gate: blocca con causal_score troppo basso
# ---------------------------------------------------------------------------

def test_gate_blocks_low_causal(tuner, trigger_result, profile):
    trigger_result.causal_score = 0.01
    proceed, reason = tuner.gate_update(trigger_result, profile)
    assert proceed is False
    assert reason == "causal_score_too_low"


# ---------------------------------------------------------------------------
# 5. Gate: blocca con energy depletata
# ---------------------------------------------------------------------------

def test_gate_blocks_low_energy(tuner, trigger_result, profile):
    profile.energy_guard_enabled = True
    metrics = SystemMetrics(tick=1, mean_energy=0.1, coherence_phi=0.2)
    proceed, reason = tuner.gate_update(trigger_result, profile, metrics=metrics)
    assert proceed is False
    assert reason == "energy_depleted"


# ---------------------------------------------------------------------------
# 6. Gate: blocca con confidence guard attivo e confidence bassa
# ---------------------------------------------------------------------------

def test_gate_blocks_low_confidence(tuner, trigger_result, profile):
    profile.confidence_guard_enabled = True
    profile.min_confidence = 0.5
    confidence_state = type("CS", (), {"confidence_score": 0.2, "uncertainty_score": 0.5})()
    proceed, reason = tuner.gate_update(trigger_result, profile, confidence_state=confidence_state)
    assert proceed is False
    assert reason == "confidence_guarded"


# ---------------------------------------------------------------------------
# 7. Apply scaled update: LTP aumenta strength
# ---------------------------------------------------------------------------

class FakePathway:
    def __init__(self):
        self.pathway_strength = 0.5
        self.plasticity_rate = 1.0
        self.min_strength = 0.0
        self.max_strength = 1.0


def test_apply_scaled_ltp(tuner, profile):
    pw = FakePathway()
    old = pw.pathway_strength
    tuner.apply_scaled_update(pw, "ltp", profile)
    assert pw.pathway_strength > old


# ---------------------------------------------------------------------------
# 8. Apply scaled update: LTD diminuisce strength
# ---------------------------------------------------------------------------

def test_apply_scaled_ltd(tuner, profile):
    pw = FakePathway()
    old = pw.pathway_strength
    tuner.apply_scaled_update(pw, "ltd", profile)
    assert pw.pathway_strength < old


# ---------------------------------------------------------------------------
# 9. Rollback ripristina strength precedente
# ---------------------------------------------------------------------------

def test_rollback_restores_strength(tuner):
    pw = FakePathway()
    old = pw.pathway_strength
    pw.pathway_strength = 0.9
    tuner.rollback_update(pw, old)
    assert pw.pathway_strength == old


# ---------------------------------------------------------------------------
# 10. Utility score in [0, 1]
# ---------------------------------------------------------------------------

def test_utility_score_bounded(tuner, trigger_result):
    pw = FakePathway()
    score = tuner.compute_pathway_utility_score(pw, trigger_result)
    assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# 11. tune_pathway_update accetta quando gate passa
# ---------------------------------------------------------------------------

def test_tune_pathway_update_accepted(tuner, profile, trigger_result):
    pw = FakePathway()
    accepted, rolled_back, reason = tuner.tune_pathway_update(pw, trigger_result, profile)
    assert accepted is True
    assert rolled_back is False
    assert reason == "accepted"


# ---------------------------------------------------------------------------
# 12. tune_pathway_update salta quando gate fallisce
# ---------------------------------------------------------------------------

def test_tune_pathway_update_skipped(tuner, profile, trigger_result):
    pw = FakePathway()
    trigger_result.causal_score = 0.01
    accepted, rolled_back, reason = tuner.tune_pathway_update(pw, trigger_result, profile)
    assert accepted is False
    assert rolled_back is False
    assert reason == "causal_score_too_low"


# ---------------------------------------------------------------------------
# 13. tune_pathway_update registra eventi su memory
# ---------------------------------------------------------------------------

def test_tune_pathway_update_records_events(tuner, profile, trigger_result):
    mem = MorphologicalMemory()
    pw = FakePathway()
    tuner.tune_pathway_update(pw, trigger_result, profile, memory=mem)
    types = [e.event_type for e in mem.events]
    assert MorphologyEventType.REGION_PLASTICITY_UPDATE_ACCEPTED in types


# ---------------------------------------------------------------------------
# 14. tune_all_pathways senza errori
# ---------------------------------------------------------------------------

def test_tune_all_pathways_empty_registry(tuner, profile):
    from speace_core.cellular_brain.regions.inter_region_plasticity import InterRegionPlasticityEngine
    from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
    from speace_core.cellular_brain.regions.region_registry import RegionRegistry

    engine = InterRegionPlasticityEngine(trigger_mode="hybrid")
    circuit = NeuralCircuit(circuit_id="test")
    registry = RegionRegistry()
    result = tuner.tune_all_pathways(engine, registry, circuit, profile, tick=1)
    assert isinstance(result, PathwayTuningResult)
    assert result.attempted_updates == 0
