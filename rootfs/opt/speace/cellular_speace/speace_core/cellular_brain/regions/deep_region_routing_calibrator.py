from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.regions.region_registry import RegionRegistry
from speace_core.cellular_brain.regions.region_signal_router import (
    RegionSignalRouter,
    RegionRoutingResult,
)
from speace_core.cellular_brain.regions.region_stability_controller import (
    RegionLevelStabilityController,
)


# --------------------------------------------------------------------------- #
# Default regional gain map — empirically tuned for deep-region activation
# --------------------------------------------------------------------------- #

DEFAULT_REGIONAL_GAIN_MAP: Dict[str, float] = {
    "sensory": 1.00,
    "limbic": 1.20,
    "hippocampus": 1.15,
    "default_mode": 1.10,
    "prefrontal": 1.05,
    "cerebellar": 1.10,
    "motor": 1.00,
    "brainstem_homeostatic": 1.25,
}


# --------------------------------------------------------------------------- #
# Flow memory per region
# --------------------------------------------------------------------------- #

class RegionFlowMemory(BaseModel):
    """Tracks signal flow history for a single region."""

    region_id: str
    last_signal_inflow: float = 0.0
    last_signal_outflow: float = 0.0
    last_activation_delta: float = 0.0
    last_routed_tick: int = 0
    cumulative_inflow: float = 0.0
    cumulative_outflow: float = 0.0
    inflow_count: int = 0
    outflow_count: int = 0

    def record_inflow(self, strength: float, tick: int) -> None:
        self.last_signal_inflow = strength
        self.cumulative_inflow += strength
        self.inflow_count += 1
        self.last_routed_tick = tick

    def record_outflow(self, strength: float, tick: int) -> None:
        self.last_signal_outflow = strength
        self.cumulative_outflow += strength
        self.outflow_count += 1
        self.last_routed_tick = tick

    def record_activation_delta(self, delta: float) -> None:
        self.last_activation_delta = delta

    @property
    def mean_inflow(self) -> float:
        return self.cumulative_inflow / max(1, self.inflow_count)

    @property
    def mean_outflow(self) -> float:
        return self.cumulative_outflow / max(1, self.outflow_count)


# --------------------------------------------------------------------------- #
# Calibration profile
# --------------------------------------------------------------------------- #

class DeepRegionRoutingProfile(BaseModel):
    """Parameter set for deep-region routing calibration."""

    profile_id: str
    name: str
    # Top-k routing: fraction of region neurons to target
    top_k_ratio: float = 0.15
    top_k_min: int = 3
    # Regional gain multipliers (overrides defaults partially)
    regional_gain_map: Dict[str, float] = Field(default_factory=dict)
    # Deep-region signal boost (multiplier applied to signal_strength for deep targets)
    deep_region_signal_boost: float = 1.0
    # Whether to enable stability-aware routing (don't zero out deep regions)
    stability_aware_routing: bool = True
    # Minimum activation threshold for deep regions to receive routing
    min_deep_region_activation: float = 0.02
    # Whether to record flow memory
    flow_memory_enabled: bool = True
    # Whether top-k routing is active
    top_k_routing_active: bool = True
    # Damping resistance: don't let stability controller fully suppress deep regions
    deep_region_damping_floor: float = 0.30


class DeepRegionRoutingResult(BaseModel):
    """Outcome of applying a deep-region routing profile."""

    profile_id: str
    routed_signals: int = 0
    delivered_signals: int = 0
    blocked_signals: int = 0
    deep_region_targeted_signals: int = 0
    mean_deep_region_activation: float = 0.0
    mean_regional_signal_gain: float = 0.0
    routing_efficiency: float = 0.0
    flow_memory_entries: int = 0
    stability_damping_resisted: int = 0


# --------------------------------------------------------------------------- #
# Calibrator engine
# --------------------------------------------------------------------------- #

class DeepRegionRoutingCalibrator:
    """Calibrate deep-region routing to overcome dormancy and trigger T33 stability.

    T34 addresses the STABILITY_NO_EFFECT finding from T33B by:
    1. Top-k target routing — concentrate signal on most-active neurons
    2. Regional gain multipliers — boost signal for deep regions
    3. Deep-region stimulation profile — temporary signal boost
    4. Flow memory — per-region inflow/outflow tracking
    5. Stability-aware routing — prevent stability controller from zeroing deep regions
    """

    def __init__(
        self,
        profile: Optional[DeepRegionRoutingProfile] = None,
        phi_baseline: float = 0.25,
    ):
        self.profile = profile or DeepRegionRoutingProfile(
            profile_id="default",
            name="default_deep_region_routing",
        )
        self.phi_baseline = phi_baseline
        self._flow_memory: Dict[str, RegionFlowMemory] = {}
        self._deep_region_types = {
            "limbic",
            "hippocampus",
            "default_mode",
            "prefrontal",
            "cerebellar",
            "brainstem_homeostatic",
        }

    # ------------------------------------------------------------------ #
    # Profile application
    # ------------------------------------------------------------------ #

    def apply_profile_to_router(self, router: RegionSignalRouter) -> None:
        """Mutate a RegionSignalRouter to use T34 settings."""
        # Store T34 settings on the router for use during route_all
        router._t34_profile = self.profile  # type: ignore[attr-defined]
        router._t34_gain_map = self._build_effective_gain_map()  # type: ignore[attr-defined]
        router._t34_flow_memory = self._flow_memory  # type: ignore[attr-defined]
        router._t34_deep_region_types = self._deep_region_types  # type: ignore[attr-defined]

    def remove_profile_from_router(self, router: RegionSignalRouter) -> None:
        """Restore router to pre-T34 state."""
        for attr in ("_t34_profile", "_t34_gain_map", "_t34_flow_memory", "_t34_deep_region_types"):
            if hasattr(router, attr):
                delattr(router, attr)

    def _build_effective_gain_map(self) -> Dict[str, float]:
        """Merge default gains with profile overrides."""
        gain_map = dict(DEFAULT_REGIONAL_GAIN_MAP)
        gain_map.update(self.profile.regional_gain_map)
        return gain_map

    # ------------------------------------------------------------------ #
    # Flow memory
    # ------------------------------------------------------------------ #

    def get_or_create_flow_memory(self, region_id: str) -> RegionFlowMemory:
        if region_id not in self._flow_memory:
            self._flow_memory[region_id] = RegionFlowMemory(region_id=region_id)
        return self._flow_memory[region_id]

    def record_inflow(self, region_id: str, strength: float, tick: int) -> None:
        mem = self.get_or_create_flow_memory(region_id)
        mem.record_inflow(strength, tick)

    def record_outflow(self, region_id: str, strength: float, tick: int) -> None:
        mem = self.get_or_create_flow_memory(region_id)
        mem.record_outflow(strength, tick)

    def record_activation_delta(self, region_id: str, delta: float) -> None:
        mem = self.get_or_create_flow_memory(region_id)
        mem.record_activation_delta(delta)

    def summarize_flow_memory(self) -> Dict[str, Any]:
        return {
            rid: {
                "last_inflow": m.last_signal_inflow,
                "last_outflow": m.last_signal_outflow,
                "last_activation_delta": m.last_activation_delta,
                "mean_inflow": m.mean_inflow,
                "mean_outflow": m.mean_outflow,
                "inflow_count": m.inflow_count,
                "outflow_count": m.outflow_count,
            }
            for rid, m in self._flow_memory.items()
        }

    # ------------------------------------------------------------------ #
    # Deep-region helpers
    # ------------------------------------------------------------------ #

    def is_deep_region(self, region_id: str) -> bool:
        return region_id in self._deep_region_types

    def compute_top_k(self, region_neuron_count: int) -> int:
        k = max(self.profile.top_k_min, int(self.profile.top_k_ratio * region_neuron_count))
        return max(1, min(k, region_neuron_count))

    # ------------------------------------------------------------------ #
    # Stability-aware multiplier correction
    # ------------------------------------------------------------------ #

    def correct_routing_multiplier(
        self,
        region_id: str,
        raw_multiplier: float,
    ) -> float:
        """Prevent stability controller from fully suppressing deep regions.

        If stability_aware_routing is enabled and the region is a deep region,
        apply a floor so that deep regions still receive some signal.
        """
        if not self.profile.stability_aware_routing:
            return raw_multiplier
        if not self.is_deep_region(region_id):
            return raw_multiplier
        floor = self.profile.deep_region_damping_floor
        return max(floor, raw_multiplier)

    # ------------------------------------------------------------------ #
    # Calibration suite
    # ------------------------------------------------------------------ #

    @classmethod
    def build_default_profiles(cls) -> List[DeepRegionRoutingProfile]:
        """Return the 6 standard T34 calibration profiles."""
        return [
            DeepRegionRoutingProfile(
                profile_id="p0",
                name="baseline_no_top_k",
                top_k_routing_active=False,
                top_k_ratio=0.0,
                deep_region_signal_boost=1.0,
                stability_aware_routing=False,
                flow_memory_enabled=False,
            ),
            DeepRegionRoutingProfile(
                profile_id="p1",
                name="top_k_only",
                top_k_routing_active=True,
                top_k_ratio=0.15,
                deep_region_signal_boost=1.0,
                stability_aware_routing=False,
                flow_memory_enabled=False,
            ),
            DeepRegionRoutingProfile(
                profile_id="p2",
                name="top_k_with_regional_gain",
                top_k_routing_active=True,
                top_k_ratio=0.15,
                deep_region_signal_boost=1.0,
                stability_aware_routing=False,
                flow_memory_enabled=False,
                regional_gain_map=DEFAULT_REGIONAL_GAIN_MAP,
            ),
            DeepRegionRoutingProfile(
                profile_id="p3",
                name="top_k_gain_and_boost",
                top_k_routing_active=True,
                top_k_ratio=0.15,
                deep_region_signal_boost=1.30,
                stability_aware_routing=False,
                flow_memory_enabled=False,
                regional_gain_map=DEFAULT_REGIONAL_GAIN_MAP,
            ),
            DeepRegionRoutingProfile(
                profile_id="p4",
                name="full_stability_aware",
                top_k_routing_active=True,
                top_k_ratio=0.15,
                deep_region_signal_boost=1.30,
                stability_aware_routing=True,
                deep_region_damping_floor=0.30,
                flow_memory_enabled=True,
                regional_gain_map=DEFAULT_REGIONAL_GAIN_MAP,
            ),
            DeepRegionRoutingProfile(
                profile_id="p5",
                name="aggressive_deep_stimulation",
                top_k_routing_active=True,
                top_k_ratio=0.20,
                top_k_min=4,
                deep_region_signal_boost=1.50,
                stability_aware_routing=True,
                deep_region_damping_floor=0.40,
                flow_memory_enabled=True,
                regional_gain_map={k: v * 1.1 for k, v in DEFAULT_REGIONAL_GAIN_MAP.items()},
            ),
        ]

    # ------------------------------------------------------------------ #
    # Static helpers for router integration
    # ------------------------------------------------------------------ #

    @staticmethod
    def select_top_k_neurons(
        neurons: List[Any],
        k: int,
    ) -> List[Any]:
        """Return the k neurons with highest current activation."""
        if len(neurons) <= k:
            return neurons
        scored = [(n, abs(getattr(n, "activation", 0.0))) for n in neurons]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [n for n, _ in scored[:k]]
