from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.execution.burst_engine import EventDrivenBurstEngine
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.regulation.homeostasis_engine import SystemMetrics


class EnergyControlDecision(BaseModel):
    """Decision snapshot produced by EnergyControlAgent each tick."""

    metabolic_state: str = "optimal"
    mean_energy: float = 0.0
    coherence_phi: float = 0.0
    burst_size_multiplier: float = 1.0
    stdp_rate_multiplier: float = 1.0
    plasticity_rate_multiplier: float = 1.0
    neurogenesis_allowance_multiplier: float = 1.0
    inhibition_decay_multiplier: float = 1.0
    apoptosis_pressure_multiplier: float = 1.0
    energy_replenish_rate: float = 0.0
    reason: str = ""
    metadata: Dict[str, object] = Field(default_factory=dict)


class EnergyControlAgent:
    """Metabolic regulator: adapts engine parameters based on circuit energy state.

    Implements a 5-state metabolic machine:
    - critical_low  : emergency conservation
    - low           : cautious operation
    - optimal       : full performance
    - high          : accelerated learning
    - critical_high : overflow prevention
    """

    # Energy thresholds for state transitions
    CRITICAL_LOW_THRESHOLD: float = 0.20
    LOW_THRESHOLD: float = 0.40
    HIGH_THRESHOLD: float = 0.70
    CRITICAL_HIGH_THRESHOLD: float = 0.85

    # Default multipliers per metabolic state (overridable for calibration)
    DEFAULT_STATE_PROFILES: Dict[str, Dict[str, float]] = {
        "critical_low": {
            "burst_size_multiplier": 0.25,
            "stdp_rate_multiplier": 0.0,
            "plasticity_rate_multiplier": 0.0,
            "neurogenesis_allowance_multiplier": 0.0,
            "inhibition_decay_multiplier": 2.0,
            "apoptosis_pressure_multiplier": 0.0,
        },
        "low": {
            "burst_size_multiplier": 0.50,
            "stdp_rate_multiplier": 0.50,
            "plasticity_rate_multiplier": 0.50,
            "neurogenesis_allowance_multiplier": 0.0,
            "inhibition_decay_multiplier": 1.5,
            "apoptosis_pressure_multiplier": 0.5,
        },
        "optimal": {
            "burst_size_multiplier": 1.0,
            "stdp_rate_multiplier": 1.0,
            "plasticity_rate_multiplier": 1.0,
            "neurogenesis_allowance_multiplier": 1.0,
            "inhibition_decay_multiplier": 1.0,
            "apoptosis_pressure_multiplier": 1.0,
        },
        "high": {
            "burst_size_multiplier": 1.50,
            "stdp_rate_multiplier": 1.25,
            "plasticity_rate_multiplier": 1.25,
            "neurogenesis_allowance_multiplier": 1.50,
            "inhibition_decay_multiplier": 0.5,
            "apoptosis_pressure_multiplier": 1.0,
        },
        "critical_high": {
            "burst_size_multiplier": 2.0,
            "stdp_rate_multiplier": 1.50,
            "plasticity_rate_multiplier": 1.50,
            "neurogenesis_allowance_multiplier": 2.0,
            "inhibition_decay_multiplier": 0.25,
            "apoptosis_pressure_multiplier": 2.0,
        },
    }

    def __init__(
        self,
        critical_low_replenish: float = 0.05,
        normal_replenish: float = 0.01,
        overflow_drain: float = 0.03,
        state_profiles: Optional[Dict[str, Dict[str, float]]] = None,
    ):
        self.critical_low_replenish = critical_low_replenish
        self.normal_replenish = normal_replenish
        self.overflow_drain = overflow_drain
        self._last_decision: EnergyControlDecision | None = None
        self.state_profiles = state_profiles or {
            k: dict(v) for k, v in self.DEFAULT_STATE_PROFILES.items()
        }

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def regulate(
        self,
        circuit: NeuralCircuit,
        metrics: SystemMetrics | None = None,
        burst_engine: EventDrivenBurstEngine | None = None,
        memory: MorphologicalMemory | None = None,
    ) -> EnergyControlDecision:
        """Classify metabolic state, apply multipliers, replenish/drain energy."""
        mean_energy = metrics.mean_energy if metrics else 0.0
        phi = metrics.coherence_phi if metrics else 0.0

        state = self._classify_state(mean_energy)
        decision = self._build_decision(state, mean_energy, phi)

        self._apply_multipliers(decision, burst_engine)
        self._replenish_or_drain(circuit, decision)

        self._last_decision = decision

        if memory is not None:
            memory.create_event(
                event_type=MorphologyEventType.ENERGY_CHANGED,
                source_id="energy_control_agent",
                metadata={
                    "metabolic_state": state,
                    "mean_energy": mean_energy,
                    "coherence_phi": phi,
                    "burst_size_multiplier": decision.burst_size_multiplier,
                    "stdp_rate_multiplier": decision.stdp_rate_multiplier,
                    "plasticity_rate_multiplier": decision.plasticity_rate_multiplier,
                    "neurogenesis_allowance_multiplier": decision.neurogenesis_allowance_multiplier,
                    "inhibition_decay_multiplier": decision.inhibition_decay_multiplier,
                    "apoptosis_pressure_multiplier": decision.apoptosis_pressure_multiplier,
                    "energy_replenish_rate": decision.energy_replenish_rate,
                },
            )

        return decision

    def get_last_decision(self) -> EnergyControlDecision | None:
        return self._last_decision

    # ------------------------------------------------------------------ #
    # State classification
    # ------------------------------------------------------------------ #

    def _classify_state(self, mean_energy: float) -> str:
        if mean_energy <= self.CRITICAL_LOW_THRESHOLD:
            return "critical_low"
        if mean_energy <= self.LOW_THRESHOLD:
            return "low"
        if mean_energy >= self.CRITICAL_HIGH_THRESHOLD:
            return "critical_high"
        if mean_energy >= self.HIGH_THRESHOLD:
            return "high"
        return "optimal"

    # ------------------------------------------------------------------ #
    # Decision builder
    # ------------------------------------------------------------------ #

    def _build_decision(
        self, state: str, mean_energy: float, phi: float
    ) -> EnergyControlDecision:
        profile = self.state_profiles.get(state, self.state_profiles["optimal"])
        reasons = {
            "critical_low": "emergency conservation: suppress firing and plasticity",
            "low": "cautious operation: reduce burst and plasticity",
            "optimal": "normal operation: no restrictions",
            "high": "accelerated learning: expand burst and plasticity",
            "critical_high": "overflow prevention: drain excess, increase apoptosis",
        }
        if state == "critical_low":
            replenish = self.critical_low_replenish
        elif state == "critical_high":
            replenish = -self.overflow_drain
        else:
            replenish = self.normal_replenish
        return EnergyControlDecision(
            metabolic_state=state,
            mean_energy=mean_energy,
            coherence_phi=phi,
            burst_size_multiplier=profile.get("burst_size_multiplier", 1.0),
            stdp_rate_multiplier=profile.get("stdp_rate_multiplier", 1.0),
            plasticity_rate_multiplier=profile.get("plasticity_rate_multiplier", 1.0),
            neurogenesis_allowance_multiplier=profile.get(
                "neurogenesis_allowance_multiplier", 1.0
            ),
            inhibition_decay_multiplier=profile.get("inhibition_decay_multiplier", 1.0),
            apoptosis_pressure_multiplier=profile.get("apoptosis_pressure_multiplier", 1.0),
            energy_replenish_rate=replenish,
            reason=reasons.get(state, "normal operation: no restrictions"),
        )

    # ------------------------------------------------------------------ #
    # Multiplier application
    # ------------------------------------------------------------------ #

    def _apply_multipliers(
        self,
        decision: EnergyControlDecision,
        burst_engine: EventDrivenBurstEngine | None,
    ) -> None:
        if burst_engine is not None:
            base_max = getattr(burst_engine, "_original_max_burst_size", None)
            if base_max is None:
                burst_engine._original_max_burst_size = burst_engine.max_burst_size
                base_max = burst_engine.max_burst_size
            burst_engine.max_burst_size = max(1, int(base_max * decision.burst_size_multiplier))

    # ------------------------------------------------------------------ #
    # Energy replenishment / drainage
    # ------------------------------------------------------------------ #

    def _replenish_or_drain(
        self, circuit: NeuralCircuit, decision: EnergyControlDecision
    ) -> None:
        rate = decision.energy_replenish_rate
        all_neurons = (
            circuit.input_neurons
            + circuit.hidden_neurons
            + circuit.output_neurons
        )
        for neuron in all_neurons:
            if rate > 0:
                neuron.energy = min(1.0, neuron.energy + rate)
            elif rate < 0:
                neuron.energy = max(0.0, neuron.energy + rate)
