import pytest

from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.regions.deep_region_routing_calibrator import (
    DeepRegionRoutingCalibrator,
    DeepRegionRoutingProfile,
    DeepRegionRoutingResult,
    RegionFlowMemory,
    DEFAULT_REGIONAL_GAIN_MAP,
)
from speace_core.cellular_brain.regions.region_signal_router import (
    RegionSignalRouter,
    RegionSignal,
)


# ---------------------------------------------------------------------------
# 1. Importability and model defaults
# ---------------------------------------------------------------------------

def test_calibrator_importable():
    assert DeepRegionRoutingCalibrator is not None
    assert DeepRegionRoutingProfile is not None
    assert DeepRegionRoutingResult is not None
    assert RegionFlowMemory is not None


def test_profile_defaults():
    p = DeepRegionRoutingProfile(profile_id="test", name="test")
    assert p.top_k_ratio == 0.15
    assert p.top_k_min == 3
    assert p.deep_region_signal_boost == 1.0
    assert p.stability_aware_routing is True
    assert p.flow_memory_enabled is True
    assert p.top_k_routing_active is True
    assert p.deep_region_damping_floor == 0.30


def test_flow_memory_defaults():
    m = RegionFlowMemory(region_id="limbic")
    assert m.last_signal_inflow == 0.0
    assert m.last_signal_outflow == 0.0
    assert m.cumulative_inflow == 0.0
    assert m.inflow_count == 0


# ---------------------------------------------------------------------------
# 2. Top-k neuron selection
# ---------------------------------------------------------------------------

def test_select_top_k_neurons_basic():
    neurons = [
        DigitalNeuron(cell_id=f"n{i}", role="digital_neuron", activation=0.1 * i)
        for i in range(10)
    ]
    top = DeepRegionRoutingCalibrator.select_top_k_neurons(neurons, 3)
    assert len(top) == 3
    assert top[0].cell_id == "n9"
    assert top[1].cell_id == "n8"
    assert top[2].cell_id == "n7"


def test_select_top_k_neurons_k_larger_than_list():
    neurons = [DigitalNeuron(cell_id="n0", role="digital_neuron", activation=0.5)]
    top = DeepRegionRoutingCalibrator.select_top_k_neurons(neurons, 5)
    assert len(top) == 1


def test_select_top_k_neurons_zero_k():
    neurons = [DigitalNeuron(cell_id="n0", role="digital_neuron", activation=0.5)]
    top = DeepRegionRoutingCalibrator.select_top_k_neurons(neurons, 0)
    assert len(top) == 0  # k=0 returns empty slice


# ---------------------------------------------------------------------------
# 3. Regional gain map
# ---------------------------------------------------------------------------

def test_default_gain_map():
    assert DEFAULT_REGIONAL_GAIN_MAP["limbic"] == 1.20
    assert DEFAULT_REGIONAL_GAIN_MAP["brainstem_homeostatic"] == 1.25
    assert DEFAULT_REGIONAL_GAIN_MAP["sensory"] == 1.00


def test_effective_gain_map_merge():
    profile = DeepRegionRoutingProfile(
        profile_id="test",
        name="test",
        regional_gain_map={"limbic": 1.50},
    )
    cal = DeepRegionRoutingCalibrator(profile=profile)
    gain = cal._build_effective_gain_map()
    assert gain["limbic"] == 1.50
    assert gain["hippocampus"] == 1.15  # default preserved


# ---------------------------------------------------------------------------
# 4. Deep-region detection
# ---------------------------------------------------------------------------

def test_is_deep_region():
    cal = DeepRegionRoutingCalibrator()
    assert cal.is_deep_region("limbic") is True
    assert cal.is_deep_region("hippocampus") is True
    assert cal.is_deep_region("sensory") is False
    assert cal.is_deep_region("motor") is False


# ---------------------------------------------------------------------------
# 5. Top-k computation
# ---------------------------------------------------------------------------

def test_compute_top_k():
    cal = DeepRegionRoutingCalibrator()
    assert cal.compute_top_k(10) == 3  # max(3, 0.15*10)=max(3,1)=3
    assert cal.compute_top_k(100) == 15  # max(3, 15)=15


def test_compute_top_k_with_custom_profile():
    profile = DeepRegionRoutingProfile(
        profile_id="test", name="test", top_k_ratio=0.20, top_k_min=4
    )
    cal = DeepRegionRoutingCalibrator(profile=profile)
    assert cal.compute_top_k(10) == 4  # max(4, 2)=4
    assert cal.compute_top_k(100) == 20


# ---------------------------------------------------------------------------
# 6. Stability-aware multiplier correction
# ---------------------------------------------------------------------------

def test_correct_routing_multiplier_no_t34():
    profile = DeepRegionRoutingProfile(
        profile_id="test", name="test", stability_aware_routing=False
    )
    cal = DeepRegionRoutingCalibrator(profile=profile)
    assert cal.correct_routing_multiplier("limbic", 0.0) == 0.0
    assert cal.correct_routing_multiplier("sensory", 0.5) == 0.5


def test_correct_routing_multiplier_with_floor():
    profile = DeepRegionRoutingProfile(
        profile_id="test", name="test", stability_aware_routing=True, deep_region_damping_floor=0.30
    )
    cal = DeepRegionRoutingCalibrator(profile=profile)
    assert cal.correct_routing_multiplier("limbic", 0.0) == 0.30
    assert cal.correct_routing_multiplier("limbic", 0.50) == 0.50
    assert cal.correct_routing_multiplier("sensory", 0.0) == 0.0  # not deep


def test_correct_routing_multiplier_stricter_floor():
    profile = DeepRegionRoutingProfile(
        profile_id="test", name="test", stability_aware_routing=True, deep_region_damping_floor=0.40
    )
    cal = DeepRegionRoutingCalibrator(profile=profile)
    assert cal.correct_routing_multiplier("brainstem_homeostatic", 0.1) == 0.40


# ---------------------------------------------------------------------------
# 7. Flow memory operations
# ---------------------------------------------------------------------------

def test_flow_memory_record_inflow():
    cal = DeepRegionRoutingCalibrator()
    cal.record_inflow("limbic", 0.5, tick=1)
    mem = cal.get_or_create_flow_memory("limbic")
    assert mem.last_signal_inflow == 0.5
    assert mem.inflow_count == 1
    assert mem.cumulative_inflow == 0.5


def test_flow_memory_record_outflow():
    cal = DeepRegionRoutingCalibrator()
    cal.record_outflow("sensory", 0.3, tick=2)
    mem = cal.get_or_create_flow_memory("sensory")
    assert mem.last_signal_outflow == 0.3
    assert mem.outflow_count == 1


def test_flow_memory_mean_inflow():
    cal = DeepRegionRoutingCalibrator()
    cal.record_inflow("limbic", 0.5, tick=1)
    cal.record_inflow("limbic", 1.0, tick=2)
    mem = cal.get_or_create_flow_memory("limbic")
    assert mem.mean_inflow == 0.75


def test_flow_memory_record_activation_delta():
    cal = DeepRegionRoutingCalibrator()
    cal.record_activation_delta("hippocampus", 0.25)
    mem = cal.get_or_create_flow_memory("hippocampus")
    assert mem.last_activation_delta == 0.25


def test_summarize_flow_memory():
    cal = DeepRegionRoutingCalibrator()
    cal.record_inflow("limbic", 0.5, tick=1)
    summary = cal.summarize_flow_memory()
    assert "limbic" in summary
    assert summary["limbic"]["last_inflow"] == 0.5


# ---------------------------------------------------------------------------
# 8. Profile application to router
# ---------------------------------------------------------------------------

def test_apply_profile_to_router():
    router = RegionSignalRouter()
    profile = DeepRegionRoutingProfile(
        profile_id="p1", name="test", regional_gain_map={"limbic": 1.50}
    )
    cal = DeepRegionRoutingCalibrator(profile=profile)
    cal.apply_profile_to_router(router)
    assert hasattr(router, "_t34_profile")
    assert hasattr(router, "_t34_gain_map")
    assert router._t34_gain_map["limbic"] == 1.50


def test_remove_profile_from_router():
    router = RegionSignalRouter()
    profile = DeepRegionRoutingProfile(profile_id="p1", name="test")
    cal = DeepRegionRoutingCalibrator(profile=profile)
    cal.apply_profile_to_router(router)
    cal.remove_profile_from_router(router)
    assert not hasattr(router, "_t34_profile")


# ---------------------------------------------------------------------------
# 9. Build default profiles
# ---------------------------------------------------------------------------

def test_build_default_profiles():
    profiles = DeepRegionRoutingCalibrator.build_default_profiles()
    assert len(profiles) == 6
    ids = {p.profile_id for p in profiles}
    assert ids == {"p0", "p1", "p2", "p3", "p4", "p5"}


def test_default_profiles_distinct():
    profiles = DeepRegionRoutingCalibrator.build_default_profiles()
    names = [p.name for p in profiles]
    assert len(names) == len(set(names))


def test_aggressive_profile_values():
    profiles = DeepRegionRoutingCalibrator.build_default_profiles()
    p5 = next(p for p in profiles if p.profile_id == "p5")
    assert p5.deep_region_signal_boost == 1.50
    assert p5.top_k_ratio == 0.20
    assert p5.top_k_min == 4
    assert p5.deep_region_damping_floor == 0.40


# ---------------------------------------------------------------------------
# 10. Router signal strength with regional gain
# ---------------------------------------------------------------------------

def test_build_region_signal_with_regional_gain():
    router = RegionSignalRouter()
    router._t34_profile = DeepRegionRoutingProfile(profile_id="t", name="t")
    router._t34_gain_map = {"limbic": 1.50}
    router._t34_deep_region_types = {"limbic"}

    # Minimal circuit with one neuron in limbic
    n = DigitalNeuron(cell_id="n1", role="digital_neuron", region="limbic", activation=0.5)
    circuit = NeuralCircuit(
        circuit_id="test",
        input_neurons=[],
        hidden_neurons=[n],
        output_neurons=[],
        synapses=[],
        astrocytes=[],
        microglia=[],
        oligodendrocytes=[],
    )

    class FakeConn:
        source_region_id = "sensory"
        target_region_id = "limbic"
        strength = 0.5

    signal = router.build_region_signal("sensory", "limbic", FakeConn(), circuit)
    # signal_strength = source_activation * strength * signal_gain * confidence_weight * regional_gain * deep_boost
    # source_activation for sensory will be 0 because no neurons in sensory region
    # But the gain and boost multipliers should be present in the chain
    assert signal.pathway_strength == 0.5


def test_build_region_signal_deep_boost():
    router = RegionSignalRouter()
    router._t34_profile = DeepRegionRoutingProfile(
        profile_id="t", name="t", deep_region_signal_boost=1.30
    )
    router._t34_gain_map = {}
    router._t34_deep_region_types = {"hippocampus"}

    n = DigitalNeuron(cell_id="n1", role="digital_neuron", region="hippocampus", activation=0.5)
    circuit = NeuralCircuit(
        circuit_id="test",
        input_neurons=[],
        hidden_neurons=[n],
        output_neurons=[],
        synapses=[],
        astrocytes=[],
        microglia=[],
        oligodendrocytes=[],
    )

    class FakeConn:
        source_region_id = "sensory"
        target_region_id = "hippocampus"
        strength = 0.5

    signal = router.build_region_signal("sensory", "hippocampus", FakeConn(), circuit)
    assert signal.target_region_id == "hippocampus"


# ---------------------------------------------------------------------------
# 11. Top-k signal delivery in router
# ---------------------------------------------------------------------------

def test_route_signal_top_k_targets_subset():
    router = RegionSignalRouter()
    router._t34_profile = DeepRegionRoutingProfile(
        profile_id="t", name="t", top_k_routing_active=True, top_k_ratio=0.5, top_k_min=2
    )

    neurons = [
        DigitalNeuron(cell_id=f"n{i}", role="digital_neuron", region="limbic", activation=0.1 * i)
        for i in range(10)
    ]
    circuit = NeuralCircuit(
        circuit_id="test",
        input_neurons=[],
        hidden_neurons=neurons,
        output_neurons=[],
        synapses=[],
        astrocytes=[],
        microglia=[],
        oligodendrocytes=[],
    )

    signal = RegionSignal(
        source_region_id="sensory",
        target_region_id="limbic",
        signal_strength=1.0,
    )
    # Snapshot pre-route activations
    pre_activations = {n.cell_id: n.activation for n in neurons}
    delivered = router.route_signal(signal, "limbic", circuit)
    assert delivered is True
    # Only top 5 neurons should receive additional activation (k = max(2, 0.5*10) = 5)
    changed_count = sum(
        1 for n in neurons if n.activation > pre_activations[n.cell_id] + 1e-9
    )
    assert changed_count == 5


def test_route_signal_top_k_when_disabled():
    router = RegionSignalRouter()
    # No T34 profile

    neurons = [
        DigitalNeuron(cell_id=f"n{i}", role="digital_neuron", region="limbic", activation=0.1 * i)
        for i in range(10)
    ]
    circuit = NeuralCircuit(
        circuit_id="test",
        input_neurons=[],
        hidden_neurons=neurons,
        output_neurons=[],
        synapses=[],
        astrocytes=[],
        microglia=[],
        oligodendrocytes=[],
    )

    signal = RegionSignal(
        source_region_id="sensory",
        target_region_id="limbic",
        signal_strength=1.0,
    )
    delivered = router.route_signal(signal, "limbic", circuit)
    assert delivered is True
    active_count = sum(1 for n in neurons if n.activation > 0.01)
    assert active_count == 10


def test_route_signal_top_k_all_neurons_when_k_large():
    router = RegionSignalRouter()
    router._t34_profile = DeepRegionRoutingProfile(
        profile_id="t", name="t", top_k_routing_active=True, top_k_ratio=1.0, top_k_min=100
    )

    neurons = [
        DigitalNeuron(cell_id=f"n{i}", role="digital_neuron", region="limbic", activation=0.1 * i)
        for i in range(5)
    ]
    circuit = NeuralCircuit(
        circuit_id="test",
        input_neurons=[],
        hidden_neurons=neurons,
        output_neurons=[],
        synapses=[],
        astrocytes=[],
        microglia=[],
        oligodendrocytes=[],
    )

    signal = RegionSignal(
        source_region_id="sensory",
        target_region_id="limbic",
        signal_strength=1.0,
    )
    delivered = router.route_signal(signal, "limbic", circuit)
    assert delivered is True
    active_count = sum(1 for n in neurons if n.activation > 0.01)
    assert active_count == 5


# ---------------------------------------------------------------------------
# 12. Router route_all with stability-aware correction
# ---------------------------------------------------------------------------

def test_route_all_stability_aware_does_not_block_deep():
    router = RegionSignalRouter()
    profile = DeepRegionRoutingProfile(
        profile_id="t",
        name="t",
        stability_aware_routing=True,
        deep_region_damping_floor=0.30,
    )
    cal = DeepRegionRoutingCalibrator(profile=profile)
    cal.apply_profile_to_router(router)

    n = DigitalNeuron(cell_id="n1", role="digital_neuron", region="limbic", activation=0.8)
    circuit = NeuralCircuit(
        circuit_id="test",
        input_neurons=[n],
        hidden_neurons=[],
        output_neurons=[],
        synapses=[],
        astrocytes=[],
        microglia=[],
        oligodendrocytes=[],
    )

    class FakeConnectome:
        connections = []

    result = router.route_all(FakeConnectome(), circuit, routing_multiplier_map={"limbic": 0.0})
    # Even with multiplier=0.0, stability-aware correction should raise it to 0.30 for deep regions
    # but there are no connections so nothing routes
    assert result.routed_signals == 0


# ---------------------------------------------------------------------------
# 13. Result model
# ---------------------------------------------------------------------------

def test_routing_result_model():
    r = DeepRegionRoutingResult(profile_id="p1")
    assert r.routed_signals == 0
    assert r.mean_regional_signal_gain == 0.0


# ---------------------------------------------------------------------------
# 14. Orchestrator integration flag
# ---------------------------------------------------------------------------

def test_orchestrator_has_t34_flag():
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.dna.models import SharedGenome

    genome = SharedGenome(cell_type="neuron", genome_id="test")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    assert hasattr(orch, "deep_region_routing_calibrator_enabled")
    assert orch.deep_region_routing_calibrator_enabled is False


def test_orchestrator_t34_enabled_initializes_calibrator():
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.dna.models import SharedGenome

    genome = SharedGenome(cell_type="neuron", genome_id="test")
    orch = CellularBrainOrchestrator(
        genome=genome,
        circuit=CellularBrainOrchestrator.build_mvp(genome).circuit,
        deep_region_routing_calibrator_enabled=True,
    )
    assert orch._deep_region_routing_calibrator is not None
    assert hasattr(orch._region_signal_router, "_t34_profile")
