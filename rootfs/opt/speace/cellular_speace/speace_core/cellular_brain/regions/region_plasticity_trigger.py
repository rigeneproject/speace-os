from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.regions.region_connectome import InterRegionConnection


class RegionActivationTrace(BaseModel):
    region_id: str
    tick_id: int
    soft_activation: float = 0.0
    mean_activation: float = 0.0
    max_activation: float = 0.0
    active_fraction: float = 0.0
    routed_input_strength: float = 0.0
    delta_activation: float = 0.0


class RegionPlasticityTriggerResult(BaseModel):
    source_region_id: str
    target_region_id: str
    triggered: bool = False
    trigger_type: str = "none"
    delta_tick: Optional[int] = None
    source_trace: Optional[RegionActivationTrace] = None
    target_trace: Optional[RegionActivationTrace] = None
    causal_score: float = 0.0
    recommended_update: Optional[str] = None
    confidence: float = 0.0


class RegionPlasticityTrigger:
    """Determines when inter-region pathways should undergo LTP/LTD.

    T27 replaces the rigid activation > 0.5 threshold with a multi-modal
    trigger: soft activation, routing awareness, temporal correlation, or
    any combination (hybrid).
    """

    def __init__(
        self,
        trigger_mode: str = "hybrid",
        min_soft_activation: float = 0.03,
        min_routed_signal: float = 0.001,
        temporal_window: int = 2,
        history_depth: int = 5,
    ):
        self.trigger_mode = trigger_mode
        self.min_soft_activation = min_soft_activation
        self.min_routed_signal = min_routed_signal
        self.temporal_window = temporal_window
        self.history_depth = history_depth
        self._activation_history: Dict[str, List[RegionActivationTrace]] = {}

    # ------------------------------------------------------------------ #
    # Soft activation
    # ------------------------------------------------------------------ #

    @staticmethod
    def compute_soft_region_activation(region_id: str, circuit: NeuralCircuit) -> float:
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
    # Trace capture
    # ------------------------------------------------------------------ #

    def capture_region_trace(
        self,
        region_id: str,
        circuit: NeuralCircuit,
        tick_id: int,
        routed_input_strength: float = 0.0,
    ) -> RegionActivationTrace:
        soft = self.compute_soft_region_activation(region_id, circuit)
        all_neurons = circuit.input_neurons + circuit.hidden_neurons + circuit.output_neurons
        region_neurons = [
            n for n in all_neurons if getattr(n, "region", None) == region_id
        ]
        activations = [abs(getattr(n, "activation", 0.0)) for n in region_neurons]
        mean_act = sum(activations) / len(activations) if activations else 0.0
        max_act = max(activations) if activations else 0.0
        active_frac = sum(1 for a in activations if a > 0.05) / len(activations) if activations else 0.0

        previous_soft = 0.0
        hist = self._activation_history.get(region_id, [])
        if hist:
            previous_soft = hist[-1].soft_activation

        delta = soft - previous_soft

        trace = RegionActivationTrace(
            region_id=region_id,
            tick_id=tick_id,
            soft_activation=soft,
            mean_activation=mean_act,
            max_activation=max_act,
            active_fraction=active_frac,
            routed_input_strength=routed_input_strength,
            delta_activation=delta,
        )

        # Update history
        self._activation_history.setdefault(region_id, [])
        self._activation_history[region_id].append(trace)
        if len(self._activation_history[region_id]) > self.history_depth:
            self._activation_history[region_id].pop(0)

        return trace

    # ------------------------------------------------------------------ #
    # Temporal correlation
    # ------------------------------------------------------------------ #

    def detect_temporal_correlation(
        self, source_region_id: str, target_region_id: str
    ) -> tuple[bool, Optional[int]]:
        src_hist = self._activation_history.get(source_region_id, [])
        tgt_hist = self._activation_history.get(target_region_id, [])
        if not src_hist or not tgt_hist:
            return False, None

        # Look for source increase followed by target increase within window
        for i, src_trace in enumerate(src_hist):
            if src_trace.delta_activation <= 0:
                continue
            for j in range(i + 1, min(i + 1 + self.temporal_window, len(tgt_hist))):
                tgt_trace = tgt_hist[j]
                if tgt_trace.delta_activation > 0:
                    delta_tick = tgt_trace.tick_id - src_trace.tick_id
                    return True, delta_tick

        # Look for target increase before source (LTD candidate)
        for i, tgt_trace in enumerate(tgt_hist):
            if tgt_trace.delta_activation <= 0:
                continue
            for j in range(i + 1, min(i + 1 + self.temporal_window, len(src_hist))):
                src_trace = src_hist[j]
                if src_trace.delta_activation > 0:
                    delta_tick = src_trace.tick_id - tgt_trace.tick_id
                    return True, -delta_tick

        return False, None

    # ------------------------------------------------------------------ #
    # Routing causality
    # ------------------------------------------------------------------ #

    def detect_routing_causality(
        self,
        source_region_id: str,
        target_region_id: str,
        routing_result,
    ) -> bool:
        if routing_result is None:
            return False
        for signal in getattr(routing_result, "signals", []):
            if (
                signal.source_region_id == source_region_id
                and signal.target_region_id == target_region_id
                and signal.delivered
                and signal.signal_strength > self.min_routed_signal
            ):
                return True
        return False

    # ------------------------------------------------------------------ #
    # Trigger evaluation
    # ------------------------------------------------------------------ #

    def evaluate_pathway_trigger(
        self,
        source_region_id: str,
        target_region_id: str,
        connection: InterRegionConnection,
        circuit: NeuralCircuit,
        routing_result: Any,
        tick: int = 0,
        memory: Optional[MorphologicalMemory] = None,
    ) -> RegionPlasticityTriggerResult:
        # Capture traces
        src_trace = self.capture_region_trace(source_region_id, circuit, tick)
        tgt_trace = self.capture_region_trace(target_region_id, circuit, tick)

        # Determine routed input strength for target
        routed_input = 0.0
        if routing_result is not None:
            for signal in getattr(routing_result, "signals", []):
                if signal.target_region_id == target_region_id and signal.delivered:
                    routed_input += signal.signal_strength
        tgt_trace.routed_input_strength = routed_input

        result = RegionPlasticityTriggerResult(
            source_region_id=source_region_id,
            target_region_id=target_region_id,
            source_trace=src_trace,
            target_trace=tgt_trace,
        )

        # Hard spike mode (original T23 behavior)
        hard_triggered = False
        if tgt_trace.max_activation > 0.5 or src_trace.max_activation > 0.5:
            hard_triggered = True

        # Soft activation mode
        soft_triggered = (
            src_trace.soft_activation >= self.min_soft_activation
            or tgt_trace.soft_activation >= self.min_soft_activation
        )

        # Routing aware mode
        routing_triggered = self.detect_routing_causality(
            source_region_id, target_region_id, routing_result
        )

        # Temporal correlation mode
        temporal_triggered, delta_tick = self.detect_temporal_correlation(
            source_region_id, target_region_id
        )

        # Hybrid: any valid trigger
        if self.trigger_mode == "hard_spike":
            triggered = hard_triggered
            trigger_type = "hard_spike"
        elif self.trigger_mode == "soft_activation":
            triggered = soft_triggered
            trigger_type = "soft_activation"
        elif self.trigger_mode == "routing_aware":
            triggered = routing_triggered
            trigger_type = "routing_aware"
        elif self.trigger_mode == "temporal_correlation":
            triggered = temporal_triggered
            trigger_type = "temporal_correlation"
        else:  # hybrid
            triggered = hard_triggered or soft_triggered or routing_triggered or temporal_triggered
            types = []
            if hard_triggered:
                types.append("hard_spike")
            if soft_triggered:
                types.append("soft_activation")
            if routing_triggered:
                types.append("routing_aware")
            if temporal_triggered:
                types.append("temporal_correlation")
            trigger_type = "+".join(types) if types else "none"

        result.triggered = triggered
        result.trigger_type = trigger_type
        result.delta_tick = delta_tick

        if triggered:
            # Compute causal score
            result.causal_score = (
                0.3 * (1.0 if hard_triggered else 0.0)
                + 0.25 * (1.0 if soft_triggered else 0.0)
                + 0.25 * (1.0 if routing_triggered else 0.0)
                + 0.2 * (1.0 if temporal_triggered else 0.0)
            )

            # Determine recommended update
            if routing_triggered or soft_triggered or hard_triggered:
                if delta_tick is not None and delta_tick < 0:
                    result.recommended_update = "ltd"
                else:
                    result.recommended_update = "ltp"
            elif temporal_triggered and delta_tick is not None:
                result.recommended_update = "ltp" if delta_tick > 0 else "ltd"
            else:
                result.recommended_update = "ltp"

            result.confidence = result.causal_score

            if memory is not None:
                memory.create_event(
                    event_type=MorphologyEventType.REGION_PLASTICITY_TRIGGERED,
                    source_id=source_region_id,
                    target_id=target_region_id,
                    metadata={
                        "trigger_type": trigger_type,
                        "causal_score": result.causal_score,
                        "recommended_update": result.recommended_update,
                        "tick": tick,
                        "source_soft_activation": src_trace.soft_activation,
                        "target_soft_activation": tgt_trace.soft_activation,
                    },
                )
        else:
            if memory is not None:
                memory.create_event(
                    event_type=MorphologyEventType.REGION_PLASTICITY_TRIGGER_SKIPPED,
                    source_id=source_region_id,
                    target_id=target_region_id,
                    metadata={
                        "reason": "no_trigger_condition_met",
                        "tick": tick,
                        "source_soft_activation": src_trace.soft_activation,
                        "target_soft_activation": tgt_trace.soft_activation,
                    },
                )

        return result

    def clear_history(self) -> None:
        self._activation_history.clear()
