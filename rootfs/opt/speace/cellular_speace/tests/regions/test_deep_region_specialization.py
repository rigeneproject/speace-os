import pytest

from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.regions.brain_region import BrainRegion
from speace_core.cellular_brain.regions.region_connectome import InterRegionConnection
from speace_core.cellular_brain.regions.region_registry import RegionRegistry
from speace_core.cellular_brain.regions.deep_region_specialization import DeepRegionSpecialization


@pytest.fixture
def registry():
    reg = RegionRegistry()
    for rid in ["sensory", "limbic", "hippocampus", "default_mode", "prefrontal", "cerebellar", "motor", "brainstem_homeostatic"]:
        reg.register(BrainRegion(
            region_id=rid,
            region_type=rid,
            neuron_ids=[f"n_{rid}_1", f"n_{rid}_2"],
            dominant_cell_types=[f"{rid}_neuron"],
            role_description=f"Role of {rid}",
        ))
    return reg


# ---------------------------------------------------------------------------
# 1. Importabilità
# ---------------------------------------------------------------------------

def test_deep_region_specialization_importable():
    assert DeepRegionSpecialization is not None


# ---------------------------------------------------------------------------
# 2. extend_region_connectome aggiunge pathway deep
# ---------------------------------------------------------------------------

def test_extend_region_connectome(registry):
    added = DeepRegionSpecialization.extend_region_connectome(registry)
    assert added > 0
    # Verify some expected pathways exist
    pairs = {(c.source_region_id, c.target_region_id) for c in registry.connectome.connections}
    assert ("sensory", "limbic") in pairs
    assert ("limbic", "prefrontal") in pairs
    assert ("prefrontal", "cerebellar") in pairs
    assert ("cerebellar", "motor") in pairs
    assert ("brainstem_homeostatic", "sensory") in pairs


# ---------------------------------------------------------------------------
# 3. apply_deep_region_specialization
# ---------------------------------------------------------------------------

def test_apply_deep_region_specialization(registry):
    mem = MorphologicalMemory()
    result = DeepRegionSpecialization.apply_deep_region_specialization(registry, memory=mem)
    assert result["region_count"] == 8
    assert result["added_pathways"] > 0
    types = [e.event_type for e in mem.events]
    assert MorphologyEventType.DEEP_REGION_SPECIALIZATION_APPLIED in types


# ---------------------------------------------------------------------------
# 4. validate_deep_region_architecture
# ---------------------------------------------------------------------------

def test_validate_deep_region_architecture(registry):
    DeepRegionSpecialization.extend_region_connectome(registry)
    valid, missing = DeepRegionSpecialization.validate_deep_region_architecture(registry)
    assert valid is True
    assert missing == []


def test_validate_missing_region(registry):
    registry.remove_region("limbic")
    valid, missing = DeepRegionSpecialization.validate_deep_region_architecture(registry)
    assert valid is False
    assert any("missing_region:limbic" in m for m in missing)


# ---------------------------------------------------------------------------
# 5. compute_region_role_alignment
# ---------------------------------------------------------------------------

def test_compute_region_role_alignment(registry):
    score = DeepRegionSpecialization.compute_region_role_alignment(registry)
    assert 0.0 <= score <= 1.0
    assert score == 1.0  # All regions have description and neurons


def test_compute_region_role_alignment_missing_region(registry):
    registry.remove_region("limbic")
    score = DeepRegionSpecialization.compute_region_role_alignment(registry)
    assert score < 1.0


# ---------------------------------------------------------------------------
# 6. compute_region_specialization_diversity
# ---------------------------------------------------------------------------

def test_compute_region_specialization_diversity(registry):
    score = DeepRegionSpecialization.compute_region_specialization_diversity(registry)
    assert 0.0 <= score <= 1.0
    assert score > 0.0  # All regions have distinct dominant types


# ---------------------------------------------------------------------------
# 7. compute_deep_region_signal_flow
# ---------------------------------------------------------------------------

def test_compute_deep_region_signal_flow(registry):
    registry.connectome.add_connection("sensory", "limbic", strength=0.6, plasticity_enabled=True)
    registry.connectome.add_connection("limbic", "prefrontal", strength=0.4, plasticity_enabled=True)
    flow = DeepRegionSpecialization.compute_deep_region_signal_flow(registry)
    assert flow >= 0.0


def test_compute_deep_region_signal_flow_empty(registry):
    flow = DeepRegionSpecialization.compute_deep_region_signal_flow(registry)
    assert flow == 0.0


# ---------------------------------------------------------------------------
# 8. compute_deep_region_metrics
# ---------------------------------------------------------------------------

def test_compute_deep_region_metrics(registry):
    registry.connectome.add_connection("sensory", "limbic", strength=0.6, plasticity_enabled=True)
    metrics = DeepRegionSpecialization.compute_deep_region_metrics(registry)
    assert metrics["deep_region_count"] == 8
    assert metrics["limbic_salience_score"] >= 0.0
    assert metrics["cerebellar_error_correction_score"] >= 0.0
    assert metrics["default_mode_consolidation_score"] >= 0.0
    assert metrics["brainstem_homeostatic_stability_score"] >= 0.0
    assert metrics["deep_region_signal_flow"] >= 0.0
    assert metrics["region_specialization_diversity"] >= 0.0
    assert metrics["region_role_alignment_score"] >= 0.0


# ---------------------------------------------------------------------------
# 9. compute_deep_region_metrics con registry vuoto
# ---------------------------------------------------------------------------

def test_compute_deep_region_metrics_empty():
    metrics = DeepRegionSpecialization.compute_deep_region_metrics(RegionRegistry())
    assert metrics["deep_region_count"] == 0


# ---------------------------------------------------------------------------
# 10. DEEP_REGION_ROLES contiene tutte le regioni attese
# ---------------------------------------------------------------------------

def test_deep_region_roles_complete():
    expected = {"sensory", "limbic", "hippocampus", "default_mode", "prefrontal", "cerebellar", "motor", "brainstem_homeostatic"}
    assert set(DeepRegionSpecialization.DEEP_REGION_ROLES.keys()) == expected
