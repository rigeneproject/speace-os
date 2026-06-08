import math
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.regions.region_connectome import RegionConnectome
from speace_core.cellular_brain.regulation.homeostasis_engine import SystemMetrics


class RegionSignal(BaseModel):
    source_region_id: str
    target_region_id: str
    signal_strength: float = 0.0
    pathway_strength: float = 0.0
    energy_cost: float = 0.0
    confidence_weight: float = 1.0
    delivered: bool = False
    reason: Optional[str] = None


class RegionRoutingResult(BaseModel):
    routed_signals: int = 0
    delivered_signals: int = 0
    blocked_signals: int = 0
    total_signal_strength: float = 0.0
    mean_signal_strength: float = 0.0
    total_energy_cost: float = 0.0
    active_pathways: int = 0
    regional_signal_flow_score: float = 0.0
    signals: List[RegionSignal] = Field(default_factory=list)


class RegionSignalRouter:
    """Routes signals between brain regions using soft activation and energy-aware gating.

    T25 makes inter-region pathways causally active so that T23 plasticity has
    meaningful activation pairs to observe (LTP/LTD).
    """

    def __init__(
        self,
        min_source_activation: float = 0.05,
        min_pathway_strength: float = 0.01,
        signal_gain: float = 1.0,
        energy_cost_per_signal: float = 0.001,
        max_signals_per_tick: int = 16,
    ):
        self.min_source_activation = min_source_activation
        self.min_pathway_strength = min_pathway_strength
        self.signal_gain = signal_gain
        self.energy_cost_per_signal = energy_cost_per_signal
        self.max_signals_per_tick = max_signals_per_tick

    # ------------------------------------------------------------------ #
    # Soft activation
    # ------------------------------------------------------------------ #

    def compute_soft_region_activation(
        self, region_id: str, circuit: NeuralCircuit
    ) -> float:
        """Return a sensitive activation score for a region.

        Formula:
            mean(|activation|)
            + 0.5 * max(|activation|)
            + 0.25 * active_fraction
        where active_fraction = neurons with |activation| > 0.05 / total.
        """
        all_neurons = circuit.input_neurons + circuit.hidden_neurons + circuit.output_neurons
        region_neurons = [
            n for n in all_neurons if getattr(n, "region", None) == region_id
        ]
        if not region_neurons:
            return 0.0

        activations = [abs(getattr(n, "activation", 0.0)) for n in region_neurons]
        mean_act = sum(activations) / len(activations)
        max_act = max(activations) if activations else 0.0
        active_frac = sum(1 for a in activations if a > 0.05) / len(activations)

        return mean_act + 0.5 * max_act + 0.25 * active_frac

    # ------------------------------------------------------------------ #
    # Signal construction
    # ------------------------------------------------------------------ #

    def build_region_signal(
        self,
        source_region_id: str,
        target_region_id: str,
        connection,
        circuit: NeuralCircuit,
        confidence_weight: float = 1.0,
    ) -> RegionSignal:
        source_activation = self.compute_soft_region_activation(source_region_id, circuit)
        signal_strength = (
            source_activation
            * connection.strength
            * self.signal_gain
            * confidence_weight
        )

        # T34 — regional gain multipliers
        gain_map = getattr(self, "_t34_gain_map", None)
        if gain_map is not None:
            regional_gain = gain_map.get(target_region_id, 1.0)
            signal_strength *= regional_gain

        # T34 — deep-region signal boost
        t34_profile = getattr(self, "_t34_profile", None)
        if t34_profile is not None:
            deep_types = getattr(self, "_t34_deep_region_types", set())
            if target_region_id in deep_types:
                signal_strength *= t34_profile.deep_region_signal_boost

        energy_cost = self.energy_cost_per_signal

        return RegionSignal(
            source_region_id=source_region_id,
            target_region_id=target_region_id,
            signal_strength=signal_strength,
            pathway_strength=connection.strength,
            energy_cost=energy_cost,
            confidence_weight=confidence_weight,
        )

    # ------------------------------------------------------------------ #
    # Signal delivery
    # ------------------------------------------------------------------ #

    def route_signal(
        self, signal: RegionSignal, target_region_id: str, circuit: NeuralCircuit
    ) -> bool:
        """Deliver signal to target region neurons. Returns True if delivered."""
        all_neurons = circuit.input_neurons + circuit.hidden_neurons + circuit.output_neurons
        target_neurons = [
            n for n in all_neurons if getattr(n, "region", None) == target_region_id
        ]
        if not target_neurons:
            signal.delivered = False
            signal.reason = "no_target_neurons"
            return False

        # T34 — top-k targeting if profile is active
        t34_profile = getattr(self, "_t34_profile", None)
        if t34_profile is not None and t34_profile.top_k_routing_active:
            from speace_core.cellular_brain.regions.deep_region_routing_calibrator import (
                DeepRegionRoutingCalibrator,
            )
            k = max(t34_profile.top_k_min, int(t34_profile.top_k_ratio * len(target_neurons)))
            k = min(k, len(target_neurons))
            target_neurons = DeepRegionRoutingCalibrator.select_top_k_neurons(target_neurons, k)

        increment = signal.signal_strength / len(target_neurons)
        for n in target_neurons:
            n.activation = getattr(n, "activation", 0.0) + increment

        signal.delivered = True
        signal.reason = "delivered"
        return True

    def route_signal_top_k(
        self,
        signal: RegionSignal,
        target_region_id: str,
        circuit: NeuralCircuit,
        k: int,
    ) -> bool:
        """Deliver signal to top-k most active neurons in target region."""
        all_neurons = circuit.input_neurons + circuit.hidden_neurons + circuit.output_neurons
        target_neurons = [
            n for n in all_neurons if getattr(n, "region", None) == target_region_id
        ]
        if not target_neurons:
            signal.delivered = False
            signal.reason = "no_target_neurons"
            return False

        if len(target_neurons) > k:
            from speace_core.cellular_brain.regions.deep_region_routing_calibrator import (
                DeepRegionRoutingCalibrator,
            )
            target_neurons = DeepRegionRoutingCalibrator.select_top_k_neurons(target_neurons, k)

        increment = signal.signal_strength / len(target_neurons)
        for n in target_neurons:
            n.activation = getattr(n, "activation", 0.0) + increment

        signal.delivered = True
        signal.reason = "delivered_top_k"
        return True

    # ------------------------------------------------------------------ #
    # Batch routing
    # ------------------------------------------------------------------ #

    def route_all(
        self,
        region_connectome: RegionConnectome,
        circuit: NeuralCircuit,
        metrics: Optional[SystemMetrics] = None,
        memory: Optional[MorphologicalMemory] = None,
        confidence_score: float = 0.0,
        routing_multiplier_map: Optional[Dict[str, float]] = None,
        current_tick: int = 0,
    ) -> RegionRoutingResult:
        result = RegionRoutingResult()
        if region_connectome is None or not region_connectome.connections:
            return result

        confidence_weight = max(0.5, 1.0 - confidence_score) if confidence_score > 0.6 else 1.0
        global_energy = metrics.mean_energy if metrics else 0.5
        multiplier_map = routing_multiplier_map or {}

        # T34 — stability-aware routing multiplier correction
        t34_profile = getattr(self, "_t34_profile", None)
        t34_calibrator = None
        if t34_profile is not None and t34_profile.stability_aware_routing:
            from speace_core.cellular_brain.regions.deep_region_routing_calibrator import (
                DeepRegionRoutingCalibrator,
            )
            t34_calibrator = DeepRegionRoutingCalibrator(profile=t34_profile)

        signals_routed = 0
        deep_targeted = 0
        for conn in region_connectome.connections:
            if signals_routed >= self.max_signals_per_tick:
                break

            multiplier = multiplier_map.get(conn.source_region_id, 1.0)

            # T34 — stability-aware correction (don't fully suppress deep regions)
            if t34_calibrator is not None:
                multiplier = t34_calibrator.correct_routing_multiplier(
                    conn.target_region_id, multiplier
                )

            if multiplier <= 0.0:
                result.blocked_signals += 1
                continue

            source_activation = self.compute_soft_region_activation(
                conn.source_region_id, circuit
            )

            # Block: source too weak
            if source_activation < self.min_source_activation:
                result.blocked_signals += 1
                if memory is not None:
                    memory.create_event(
                        event_type=MorphologyEventType.REGION_SIGNAL_BLOCKED,
                        source_id=conn.source_region_id,
                        target_id=conn.target_region_id,
                        metadata={
                            "reason": "source_activation_below_threshold",
                            "source_activation": source_activation,
                            "threshold": self.min_source_activation,
                        },
                    )
                continue

            # Block: pathway too weak
            if conn.strength < self.min_pathway_strength:
                result.blocked_signals += 1
                if memory is not None:
                    memory.create_event(
                        event_type=MorphologyEventType.REGION_SIGNAL_BLOCKED,
                        source_id=conn.source_region_id,
                        target_id=conn.target_region_id,
                        metadata={
                            "reason": "pathway_strength_below_threshold",
                            "pathway_strength": conn.strength,
                            "threshold": self.min_pathway_strength,
                        },
                    )
                continue

            # Block: insufficient energy (soft gate)
            if global_energy < 0.1:
                result.blocked_signals += 1
                if memory is not None:
                    memory.create_event(
                        event_type=MorphologyEventType.REGION_SIGNAL_BLOCKED,
                        source_id=conn.source_region_id,
                        target_id=conn.target_region_id,
                        metadata={
                            "reason": "global_energy_depleted",
                            "global_energy": global_energy,
                        },
                    )
                continue

            signal = self.build_region_signal(
                conn.source_region_id,
                conn.target_region_id,
                conn,
                circuit,
                confidence_weight=confidence_weight,
            )

            # Apply stability multiplier to signal strength
            signal.signal_strength *= multiplier

            # T34 — deep-region targeting tracking
            if t34_calibrator is not None and t34_calibrator.is_deep_region(conn.target_region_id):
                deep_targeted += 1

            if memory is not None:
                memory.create_event(
                    event_type=MorphologyEventType.REGION_SIGNAL_ROUTED,
                    source_id=conn.source_region_id,
                    target_id=conn.target_region_id,
                    metadata={
                        "signal_strength": signal.signal_strength,
                        "pathway_strength": conn.strength,
                        "confidence_weight": confidence_weight,
                        "routing_multiplier": multiplier,
                    },
                )

            # T34 — snapshot pre-route activation for flow delta tracking
            if t34_profile is not None and t34_profile.flow_memory_enabled:
                all_neurons = circuit.input_neurons + circuit.hidden_neurons + circuit.output_neurons
                for n in all_neurons:
                    if getattr(n, "region", None) == conn.target_region_id:
                        n._pre_route_activation = getattr(n, "activation", 0.0)

            delivered = self.route_signal(signal, conn.target_region_id, circuit)

            # T34 — flow memory tracking
            if delivered and t34_profile is not None and t34_profile.flow_memory_enabled:
                flow_mem = getattr(self, "_t34_flow_memory", None)
                if flow_mem is not None:
                    from speace_core.cellular_brain.regions.deep_region_routing_calibrator import (
                        DeepRegionRoutingCalibrator,
                    )
                    cal = DeepRegionRoutingCalibrator(profile=t34_profile)
                    cal._flow_memory = flow_mem
                    cal.record_inflow(conn.target_region_id, signal.signal_strength, current_tick)
                    cal.record_outflow(conn.source_region_id, signal.signal_strength, current_tick)
                    # Activation delta tracking
                    all_neurons = circuit.input_neurons + circuit.hidden_neurons + circuit.output_neurons
                    pre_activations = {n.cell_id: getattr(n, "_pre_route_activation", getattr(n, "activation", 0.0)) for n in all_neurons if getattr(n, "region", None) == conn.target_region_id}
                    post_activations = {n.cell_id: getattr(n, "activation", 0.0) for n in all_neurons if getattr(n, "region", None) == conn.target_region_id}
                    if pre_activations and post_activations:
                        deltas = [abs(post_activations.get(cid, 0.0) - pre_activations.get(cid, 0.0)) for cid in pre_activations]
                        cal.record_activation_delta(conn.target_region_id, sum(deltas) / len(deltas))

            if delivered:
                result.delivered_signals += 1
                result.total_signal_strength += signal.signal_strength
                result.total_energy_cost += signal.energy_cost
                if memory is not None:
                    memory.create_event(
                        event_type=MorphologyEventType.REGION_SIGNAL_DELIVERED,
                        source_id=conn.source_region_id,
                        target_id=conn.target_region_id,
                        metadata={
                            "signal_strength": signal.signal_strength,
                            "energy_cost": signal.energy_cost,
                        },
                    )
            else:
                result.blocked_signals += 1

            result.signals.append(signal)
            signals_routed += 1
            result.routed_signals += 1

        if result.delivered_signals > 0:
            result.mean_signal_strength = (
                result.total_signal_strength / result.delivered_signals
            )

        result.active_pathways = sum(
            1 for c in region_connectome.connections if c.strength >= self.min_pathway_strength
        )
        result.regional_signal_flow_score = self.compute_regional_signal_flow_score(result)

        if memory is not None and result.routed_signals > 0:
            memory.create_event(
                event_type=MorphologyEventType.REGIONAL_SIGNAL_FLOW_UPDATED,
                source_id="region_signal_router",
                metadata={
                    "routed_signals": result.routed_signals,
                    "delivered_signals": result.delivered_signals,
                    "blocked_signals": result.blocked_signals,
                    "total_signal_strength": result.total_signal_strength,
                    "mean_signal_strength": result.mean_signal_strength,
                    "regional_signal_flow_score": result.regional_signal_flow_score,
                    "deep_region_targeted_signals": deep_targeted,
                },
            )

        # T35 — Homeostatic activation clamp after routing
        self._clamp_circuit_activations(circuit, memory)

        return result

    # ------------------------------------------------------------------ #
    # Homeostatic activation clamp (T35)
    # ------------------------------------------------------------------ #

    MAX_REGION_NEURON_ACTIVATION: float = 5.0
    MAX_MEAN_REGION_ACTIVATION: float = 1.0

    @classmethod
    def _clamp_circuit_activations(
        cls,
        circuit: NeuralCircuit,
        memory: Optional[MorphologicalMemory] = None,
    ) -> None:
        """Clamp neuron activations to biologically plausible bounds per region."""
        if circuit is None:
            return
        all_neurons = circuit.input_neurons + circuit.hidden_neurons + circuit.output_neurons
        # Group neurons by region
        region_neurons: Dict[str, List[Any]] = {}
        for n in all_neurons:
            rid = getattr(n, "region", None)
            if rid is None:
                continue
            region_neurons.setdefault(rid, []).append(n)

        for rid, neurons in region_neurons.items():
            if not neurons:
                continue
            activations = [getattr(n, "activation", 0.0) for n in neurons]
            max_act = max(abs(a) for a in activations) if activations else 0.0
            mean_act = sum(abs(a) for a in activations) / len(activations) if activations else 0.0
            clamped = False

            # Clamp individual neurons to max bound
            if max_act > cls.MAX_REGION_NEURON_ACTIVATION:
                scale = cls.MAX_REGION_NEURON_ACTIVATION / max_act
                for n in neurons:
                    n.activation = getattr(n, "activation", 0.0) * scale
                clamped = True

            # After max clamp, recompute mean and scale if mean still too high
            activations = [getattr(n, "activation", 0.0) for n in neurons]
            mean_act = sum(abs(a) for a in activations) / len(activations) if activations else 0.0
            if mean_act > cls.MAX_MEAN_REGION_ACTIVATION:
                scale = cls.MAX_MEAN_REGION_ACTIVATION / mean_act
                for n in neurons:
                    n.activation = getattr(n, "activation", 0.0) * scale
                clamped = True

            if clamped and memory is not None:
                memory.create_event(
                    event_type=MorphologyEventType.REGION_ACTIVATION_CLAMPED,
                    region_id=rid,
                    metadata={
                        "max_activation_before": max_act,
                        "mean_activation_before": mean_act,
                        "max_activation_after": cls.MAX_REGION_NEURON_ACTIVATION if max_act > cls.MAX_REGION_NEURON_ACTIVATION else max_act,
                        "mean_activation_after": cls.MAX_MEAN_REGION_ACTIVATION if mean_act > cls.MAX_MEAN_REGION_ACTIVATION else mean_act,
                    },
                )

    # ------------------------------------------------------------------ #
    # Scoring
    # ------------------------------------------------------------------ #

    @staticmethod
    def compute_regional_signal_flow_score(result: RegionRoutingResult) -> float:
        """Score in [0, 1] measuring effective inter-region communication."""
        if result.routed_signals == 0:
            return 0.0
        delivery_ratio = result.delivered_signals / result.routed_signals
        strength_component = min(1.0, result.mean_signal_strength)
        return max(0.0, min(1.0, delivery_ratio * strength_component))
