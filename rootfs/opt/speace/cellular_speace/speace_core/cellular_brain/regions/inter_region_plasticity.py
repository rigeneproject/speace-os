from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.regions.region_registry import RegionRegistry
from speace_core.cellular_brain.regions.region_connectome import InterRegionConnection
from speace_core.cellular_brain.regions.region_plasticity_trigger import RegionPlasticityTrigger
from speace_core.cellular_brain.regulation.homeostasis_engine import SystemMetrics


class RegionPathwayState(BaseModel):
    """Mutable state of a single inter-region pathway."""

    source_region_id: str
    target_region_id: str
    pathway_strength: float = 0.5
    plasticity_rate: float = 1.0
    last_source_activation_tick: Optional[int] = None
    last_target_activation_tick: Optional[int] = None
    ltp_events: int = 0
    ltd_events: int = 0
    energy_cost: float = 0.0
    confidence_modulation: float = 1.0


class InterRegionPlasticityResult(BaseModel):
    """Result snapshot of an inter-region plasticity tick."""

    updated_pathways: int = 0
    reinforced_pathways: int = 0
    weakened_pathways: int = 0
    mean_pathway_strength: float = 0.0
    total_energy_cost: float = 0.0
    events: List[Dict[str, Any]] = Field(default_factory=list)


class InterRegionPlasticityEngine:
    """Pathway-specific STDP between brain regions.

    Transforms the static T21 pipeline into an adaptive network:
    sensory ↔ hippocampus ↔ prefrontal ↔ motor
    """

    def __init__(
        self,
        ltp_rate: float = 0.05,
        ltd_rate: float = 0.03,
        min_strength: float = 0.0,
        max_strength: float = 1.0,
        stdp_window: int = 1,
        energy_cost_per_update: float = 0.001,
        confidence_modulation_strength: float = 1.0,
        energy_modulation_strength: float = 1.0,
        trigger_mode: str = "hard_spike",
        tuner_profile: Any = None,
    ):
        self.ltp_rate = ltp_rate
        self.ltd_rate = ltd_rate
        self.min_strength = min_strength
        self.max_strength = max_strength
        self.stdp_window = stdp_window
        self.energy_cost_per_update = energy_cost_per_update
        self.confidence_modulation_strength = confidence_modulation_strength
        self.energy_modulation_strength = energy_modulation_strength
        self.trigger_mode = trigger_mode
        self._trigger = RegionPlasticityTrigger(trigger_mode=trigger_mode)
        self.tuner_profile = tuner_profile

    # ------------------------------------------------------------------ #
    # Activation tracking
    # ------------------------------------------------------------------ #

    @staticmethod
    def compute_region_activation(region_id: str, circuit: NeuralCircuit) -> bool:
        """A region is considered activated if any of its neurons fired recently."""
        for n in circuit.hidden_neurons + circuit.input_neurons + circuit.output_neurons:
            if getattr(n, "region", None) == region_id and getattr(n, "activation", 0.0) > 0.5:
                return True
        return False

    def compute_delta_tick(
        self,
        pathway: RegionPathwayState,
        tick: int,
    ) -> int | None:
        """Return target_tick - source_tick, or None if out of window."""
        src = pathway.last_source_activation_tick
        tgt = pathway.last_target_activation_tick
        if src is None or tgt is None:
            return None
        delta = tgt - src
        if abs(delta) > self.stdp_window:
            return None
        return delta

    # ------------------------------------------------------------------ #
    # Core update rules
    # ------------------------------------------------------------------ #

    def apply_pathway_ltp(self, pathway: RegionPathwayState, multiplier: float = 1.0) -> None:
        pathway.pathway_strength = min(
            self.max_strength,
            pathway.pathway_strength + self.ltp_rate * pathway.plasticity_rate * multiplier,
        )
        pathway.ltp_events += 1
        pathway.energy_cost += self.energy_cost_per_update * multiplier

    def apply_pathway_ltd(self, pathway: RegionPathwayState, multiplier: float = 1.0) -> None:
        pathway.pathway_strength = max(
            self.min_strength,
            pathway.pathway_strength - self.ltd_rate * pathway.plasticity_rate * multiplier,
        )
        pathway.ltd_events += 1
        pathway.energy_cost += self.energy_cost_per_update * multiplier

    def modulate_by_energy(
        self,
        pathway: RegionPathwayState,
        mean_region_energy: float,
    ) -> None:
        # Low energy reduces plasticity rate but never to zero
        if mean_region_energy < 0.3:
            pathway.plasticity_rate = max(0.1, mean_region_energy)
        elif mean_region_energy > 0.8:
            pathway.plasticity_rate = 1.2
        else:
            pathway.plasticity_rate = 1.0
        pathway.plasticity_rate *= self.energy_modulation_strength

    def modulate_by_confidence(
        self,
        pathway: RegionPathwayState,
        confidence_score: float,
        coherence_phi: float,
    ) -> None:
        # High confidence + stable phi → preserve useful pathways (reduce plasticity)
        if confidence_score > 0.6 and coherence_phi > 0.2:
            pathway.confidence_modulation = 0.7
        # Low confidence → increase plasticity on ambiguous pathways
        elif confidence_score < 0.3:
            pathway.confidence_modulation = 1.3
        else:
            pathway.confidence_modulation = 1.0
        pathway.confidence_modulation *= self.confidence_modulation_strength
        pathway.plasticity_rate *= pathway.confidence_modulation

    def _is_isolated_region(
        self,
        region_id: str,
        registry: RegionRegistry,
    ) -> bool:
        conn = registry.connectome
        outgoing = len(conn.get_connections_from(region_id))
        incoming = len(conn.get_connections_to(region_id))
        return outgoing + incoming <= 1

    # ------------------------------------------------------------------ #
    # Batch update
    # ------------------------------------------------------------------ #

    def update_pathways(
        self,
        circuit: NeuralCircuit,
        registry: RegionRegistry,
        metrics: Optional[SystemMetrics] = None,
        memory: Optional[MorphologicalMemory] = None,
        tick: int = 0,
        confidence_score: float = 0.0,
        routing_result: Any = None,
        plasticity_multiplier_map: Optional[Dict[str, float]] = None,
    ) -> InterRegionPlasticityResult:
        result = InterRegionPlasticityResult()
        if registry is None or registry.connectome is None:
            return result

        connections = registry.connectome.connections
        if not connections:
            return result

        multiplier_map = plasticity_multiplier_map or {}

        # T29 — PathwayPlasticityTuner integration
        if self.tuner_profile is not None:
            from speace_core.cellular_brain.regions.pathway_plasticity_tuner import PathwayPlasticityTuner
            tuner = PathwayPlasticityTuner()
            tuning_result = tuner.tune_all_pathways(
                engine=self,
                registry=registry,
                circuit=circuit,
                profile=self.tuner_profile,
                metrics=metrics,
                memory=memory,
                confidence_state=None,
                routing_result=routing_result,
                tick=tick,
            )
            result.updated_pathways = tuning_result.accepted_updates
            result.reinforced_pathways = tuning_result.ltp_updates
            result.weakened_pathways = tuning_result.ltd_updates
            if connections:
                strengths = [
                    getattr(c, "_pathway_state", None).pathway_strength
                    for c in connections
                    if hasattr(c, "_pathway_state") and getattr(c, "_pathway_state", None) is not None
                ]
                result.mean_pathway_strength = sum(strengths) / len(strengths) if strengths else 0.0
            if memory is not None and tuning_result.accepted_updates > 0:
                memory.create_event(
                    event_type=MorphologyEventType.INTER_REGION_PLASTICITY_APPLIED,
                    source_id="inter_region_plasticity_engine",
                    metadata={
                        "updated_pathways": tuning_result.accepted_updates,
                        "reinforced": tuning_result.ltp_updates,
                        "weakened": tuning_result.ltd_updates,
                        "skipped": tuning_result.skipped_updates,
                        "rolled_back": tuning_result.rolled_back_updates,
                        "mean_pathway_strength": result.mean_pathway_strength,
                        "tick": tick,
                        "trigger_mode": self.trigger_mode,
                        "tuner_profile": self.tuner_profile.profile_id,
                    },
                )
            return result

        global_energy = metrics.mean_energy if metrics else 0.5
        global_phi = metrics.coherence_phi if metrics else 0.0

        use_trigger = self.trigger_mode != "hard_spike"
        if use_trigger:
            self._trigger.clear_history()

        for conn in connections:
            if not conn.plasticity_enabled:
                continue
            multiplier = multiplier_map.get(conn.source_region_id, 1.0)
            if multiplier <= 0.0:
                continue

            # Build or recover pathway state stored in connection metadata
            if not hasattr(conn, "_pathway_state"):
                conn._pathway_state = RegionPathwayState(
                    source_region_id=conn.source_region_id,
                    target_region_id=conn.target_region_id,
                    pathway_strength=conn.strength,
                )
            pw: RegionPathwayState = conn._pathway_state

            if use_trigger:
                trigger_result = self._trigger.evaluate_pathway_trigger(
                    source_region_id=conn.source_region_id,
                    target_region_id=conn.target_region_id,
                    connection=conn,
                    circuit=circuit,
                    routing_result=routing_result,
                    tick=tick,
                    memory=memory,
                )
                src_active = trigger_result.triggered
                tgt_active = trigger_result.triggered
                if src_active:
                    pw.last_source_activation_tick = tick
                if tgt_active:
                    pw.last_target_activation_tick = tick

                # Skip if trigger not met
                if not trigger_result.triggered:
                    continue

                # For trigger modes, use recommended update when available
                if trigger_result.recommended_update == "ltp":
                    self.apply_pathway_ltp(pw, multiplier=multiplier)
                    result.reinforced_pathways += 1
                    if memory is not None:
                        memory.create_event(
                            event_type=MorphologyEventType.REGION_PATHWAY_REINFORCED,
                            source_id=conn.source_region_id,
                            target_id=conn.target_region_id,
                            metadata={
                                "mechanism": "inter_region_stdp",
                                "trigger_type": trigger_result.trigger_type,
                                "causal_score": trigger_result.causal_score,
                                "tick": tick,
                                "stability_multiplier": multiplier,
                            },
                        )
                elif trigger_result.recommended_update == "ltd":
                    self.apply_pathway_ltd(pw, multiplier=multiplier)
                    result.weakened_pathways += 1
                    if memory is not None:
                        memory.create_event(
                            event_type=MorphologyEventType.REGION_PATHWAY_WEAKENED,
                            source_id=conn.source_region_id,
                            target_id=conn.target_region_id,
                            metadata={
                                "mechanism": "inter_region_stdp",
                                "trigger_type": trigger_result.trigger_type,
                                "causal_score": trigger_result.causal_score,
                                "tick": tick,
                                "stability_multiplier": multiplier,
                            },
                        )
            else:
                # Legacy hard_spike mode (T23 original)
                src_active = self.compute_region_activation(conn.source_region_id, circuit)
                tgt_active = self.compute_region_activation(conn.target_region_id, circuit)

                if src_active:
                    pw.last_source_activation_tick = tick
                if tgt_active:
                    pw.last_target_activation_tick = tick

                if not src_active and not tgt_active:
                    continue

                # Modulate by energy
                self.modulate_by_energy(pw, global_energy)

                # Modulate by confidence
                self.modulate_by_confidence(pw, confidence_score, global_phi)

                # Compensatory strengthening for isolated/weak regions
                if self._is_isolated_region(conn.source_region_id, registry) or self._is_isolated_region(conn.target_region_id, registry):
                    pw.plasticity_rate = max(pw.plasticity_rate, 1.0)

                # Apply STDP if both have fired within window
                delta = self.compute_delta_tick(pw, tick)
                if delta is not None:
                    if delta > 0:
                        self.apply_pathway_ltp(pw, multiplier=multiplier)
                        result.reinforced_pathways += 1
                        if memory is not None:
                            memory.create_event(
                                event_type=MorphologyEventType.REGION_PATHWAY_REINFORCED,
                                source_id=conn.source_region_id,
                                target_id=conn.target_region_id,
                                metadata={
                                    "mechanism": "inter_region_stdp",
                                    "pathway_strength": pw.pathway_strength,
                                    "delta_tick": delta,
                                    "tick": tick,
                                    "stability_multiplier": multiplier,
                                },
                            )
                    elif delta < 0:
                        self.apply_pathway_ltd(pw, multiplier=multiplier)
                        result.weakened_pathways += 1
                        if memory is not None:
                            memory.create_event(
                                event_type=MorphologyEventType.REGION_PATHWAY_WEAKENED,
                                source_id=conn.source_region_id,
                                target_id=conn.target_region_id,
                                metadata={
                                    "mechanism": "inter_region_stdp",
                                    "pathway_strength": pw.pathway_strength,
                                    "delta_tick": delta,
                                    "tick": tick,
                                    "stability_multiplier": multiplier,
                                },
                            )

            # Clamp and sync back to connection
            pw.pathway_strength = max(
                self.min_strength, min(self.max_strength, pw.pathway_strength)
            )
            conn.strength = pw.pathway_strength
            result.updated_pathways += 1
            result.total_energy_cost += pw.energy_cost
            pw.energy_cost = 0.0  # reset per-tick cost

        if result.updated_pathways > 0:
            strengths = [
                c._pathway_state.pathway_strength
                for c in connections
                if hasattr(c, "_pathway_state")
            ]
            result.mean_pathway_strength = sum(strengths) / len(strengths) if strengths else 0.0

            if memory is not None:
                memory.create_event(
                    event_type=MorphologyEventType.INTER_REGION_PLASTICITY_APPLIED,
                    source_id="inter_region_plasticity_engine",
                    metadata={
                        "updated_pathways": result.updated_pathways,
                        "reinforced": result.reinforced_pathways,
                        "weakened": result.weakened_pathways,
                        "mean_pathway_strength": result.mean_pathway_strength,
                        "total_energy_cost": result.total_energy_cost,
                        "tick": tick,
                        "trigger_mode": self.trigger_mode,
                    },
                )

        return result
