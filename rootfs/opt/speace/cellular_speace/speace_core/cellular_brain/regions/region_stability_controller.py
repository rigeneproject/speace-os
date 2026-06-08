from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.regions.brain_region import BrainRegion
from speace_core.cellular_brain.regions.region_registry import RegionRegistry


class RegionStabilityState(BaseModel):
    region_id: str
    phi: float = 0.0
    energy: float = 0.0
    activation: float = 0.0
    signal_inflow: float = 0.0
    signal_outflow: float = 0.0
    instability_score: float = 0.0
    cooldown_remaining: int = 0
    damping_factor: float = 1.0
    routing_allowed: bool = True


class RegionStabilityAction(BaseModel):
    region_id: str
    action_type: str
    reason: str
    damping_factor: float = 1.0
    cooldown_ticks: int = 0
    plasticity_multiplier: float = 1.0
    routing_multiplier: float = 1.0


class RegionStabilityResult(BaseModel):
    regions_checked: int = 0
    unstable_regions: int = 0
    actions_applied: int = 0
    mean_instability_score: float = 0.0
    mean_damping_factor: float = 1.0
    phi_guard_triggered: bool = False
    brainstem_override_triggered: bool = False


class RegionLevelStabilityController:
    """Stabilize regional coherence Φ by modulating routing, plasticity, and signal flow.

    T33 addresses the DEEP_REGION_PHI_REGRESSION found in T32B.
    """

    def __init__(
        self,
        phi_baseline: float = 0.25,
        enable_brainstem_override: bool = True,
        brainstem_override_threshold: float = 0.75,
    ):
        self.phi_baseline = phi_baseline
        self.enable_brainstem_override = enable_brainstem_override
        self.brainstem_override_threshold = brainstem_override_threshold
        self._region_states: Dict[str, RegionStabilityState] = {}
        self._global_routing_multiplier: float = 1.0
        self._global_plasticity_multiplier: float = 1.0
        self._brainstem_override_active: bool = False

    # ------------------------------------------------------------------ #
    # Stability state computation
    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    # T34B-FIX: Read actual neuron activations from circuit
    # ------------------------------------------------------------------ #

    @staticmethod
    def _read_region_neuron_metrics(region: BrainRegion, circuit) -> Dict[str, float]:
        """Return actual activation metrics for neurons in this region."""
        if circuit is None:
            return {"mean": 0.0, "max": 0.0, "count": 0}
        all_neurons = (
            getattr(circuit, "input_neurons", [])
            + getattr(circuit, "hidden_neurons", [])
            + getattr(circuit, "output_neurons", [])
        )
        region_neurons = [
            n for n in all_neurons
            if getattr(n, "region", None) == region.region_id or n.cell_id in region.neuron_ids
        ]
        if not region_neurons:
            return {"mean": 0.0, "max": 0.0, "count": 0}
        activations = [getattr(n, "activation", 0.0) for n in region_neurons]
        abs_acts = [abs(a) for a in activations]
        return {
            "mean": sum(abs_acts) / len(abs_acts),
            "max": max(abs_acts) if abs_acts else 0.0,
            "count": len(region_neurons),
        }

    @classmethod
    def compute_region_stability_state(
        cls,
        region: BrainRegion,
        circuit,
        pathway_utility: Optional[float] = None,
        previous_activation: float = 0.0,
        previous_state: Optional[RegionStabilityState] = None,
        flow_memory: Optional[Dict[str, Any]] = None,
    ) -> RegionStabilityState:
        max_activation = 0.0
        mean_activation = 0.0
        if circuit is None and previous_state is not None:
            phi = previous_state.phi
            energy = previous_state.energy
            activation = previous_state.activation
            signal_inflow = previous_state.signal_inflow
            signal_outflow = previous_state.signal_outflow
            max_activation = getattr(previous_state, "max_activation", 0.0)
            mean_activation = activation
        else:
            profile = region.compute_local_metrics(circuit)
            phi = profile.local_phi
            energy = profile.mean_energy

            # T34B-FIX: Read actual neuron activations
            n_neurons = max(1, len(region.neuron_ids))
            neuron_metrics = cls._read_region_neuron_metrics(region, circuit)
            mean_activation = neuron_metrics["mean"]
            max_activation = neuron_metrics["max"]
            # Clamp activation to [0,1] for state representation
            activation = min(1.0, mean_activation)

            # Signal inflow/outflow: prefer flow memory, fallback to buffer
            if flow_memory and region.region_id in flow_memory:
                mem = flow_memory[region.region_id]
                signal_inflow = min(1.0, abs(getattr(mem, "last_signal_inflow", 0.0)))
                signal_outflow = min(1.0, abs(getattr(mem, "last_signal_outflow", 0.0)))
            else:
                signal_inflow = min(1.0, len(region._input_buffer) / (n_neurons * 2.0))
                signal_outflow = min(1.0, len(region._output_buffer) / (n_neurons * 2.0))

        # Activation volatility: absolute change from previous tick
        activation_volatility = abs(activation - previous_activation)

        # Signal overflow: excess inflow vs outflow
        signal_overflow = max(0.0, signal_inflow - signal_outflow)

        # Energy stress
        energy_stress = max(0.0, (energy - 0.7) / 0.3) if energy > 0.7 else 0.0

        # Negative utility pressure
        negative_utility_pressure = max(0.0, -(pathway_utility or 0.0))

        instability_score = cls.compute_instability_score(
            phi_baseline=cls._get_default_phi_baseline(),
            phi=phi,
            activation_volatility=activation_volatility,
            signal_overflow=signal_overflow,
            energy_stress=energy_stress,
            negative_utility_pressure=negative_utility_pressure,
            max_activation=max_activation,
            mean_activation=mean_activation,
        )

        return RegionStabilityState(
            region_id=region.region_id,
            phi=phi,
            energy=energy,
            activation=activation,
            signal_inflow=signal_inflow,
            signal_outflow=signal_outflow,
            instability_score=instability_score,
        )

    @staticmethod
    def _get_default_phi_baseline() -> float:
        return 0.25

    @classmethod
    def compute_instability_score(
        cls,
        phi_baseline: float,
        phi: float,
        activation_volatility: float,
        signal_overflow: float,
        energy_stress: float,
        negative_utility_pressure: float,
        max_activation: float = 0.0,
        mean_activation: float = 0.0,
    ) -> float:
        score = (
            0.35 * max(0.0, phi_baseline - phi)
            + 0.25 * activation_volatility
            + 0.20 * signal_overflow
            + 0.10 * energy_stress
            + 0.10 * negative_utility_pressure
        )
        # T34B-FIX: Activation explosion guards
        if max_activation > 5.0:
            score += 0.40
        if abs(mean_activation) > 1.0:
            score += 0.30
        return round(max(0.0, min(1.0, score)), 4)

    # ------------------------------------------------------------------ #
    # Action decisions
    # ------------------------------------------------------------------ #

    @classmethod
    def decide_stability_action(cls, state: RegionStabilityState) -> Optional[RegionStabilityAction]:
        s = state.instability_score
        if s < 0.25:
            return None
        if s < 0.50:
            # Watch: soft damping
            return RegionStabilityAction(
                region_id=state.region_id,
                action_type="soft_damping",
                reason=f"instability_score={s:.3f} (watch)",
                damping_factor=0.85,
                plasticity_multiplier=0.75,
                routing_multiplier=0.75,
            )
        if s < 0.75:
            # Damp: hard damping
            return RegionStabilityAction(
                region_id=state.region_id,
                action_type="hard_damping",
                reason=f"instability_score={s:.3f} (damp)",
                damping_factor=0.60,
                plasticity_multiplier=0.40,
                routing_multiplier=0.40,
                cooldown_ticks=2,
            )
        # Cooldown / block routing
        return RegionStabilityAction(
            region_id=state.region_id,
            action_type="routing_block",
            reason=f"instability_score={s:.3f} (critical)",
            damping_factor=0.30,
            plasticity_multiplier=0.20,
            routing_multiplier=0.0,
            cooldown_ticks=3,
        )

    def apply_stability_action(
        self,
        region: BrainRegion,
        action: RegionStabilityAction,
        memory: Optional[MorphologicalMemory] = None,
        circuit=None,
    ) -> None:
        state = self._region_states.get(region.region_id)
        if state is None:
            return
        state.damping_factor = action.damping_factor
        state.cooldown_remaining = action.cooldown_ticks
        state.routing_allowed = action.routing_multiplier > 0.0

        # T35 — Forced activation decay on hard damping / routing block
        if circuit is not None and action.action_type in {"hard_damping", "routing_block"}:
            self._force_activation_decay(region, action, circuit, memory)

        if memory is not None:
            if action.action_type == "routing_block":
                event_type = MorphologyEventType.REGION_ROUTING_BLOCKED
            elif action.action_type == "hard_damping":
                event_type = MorphologyEventType.REGION_DAMPING_APPLIED
            elif action.action_type == "soft_damping":
                event_type = MorphologyEventType.REGION_DAMPING_APPLIED
            else:
                event_type = MorphologyEventType.REGION_INSTABILITY_DETECTED
            memory.create_event(
                event_type=event_type,
                region_id=region.region_id,
                metadata={
                    "action_type": action.action_type,
                    "reason": action.reason,
                    "damping_factor": action.damping_factor,
                    "plasticity_multiplier": action.plasticity_multiplier,
                    "routing_multiplier": action.routing_multiplier,
                    "cooldown_ticks": action.cooldown_ticks,
                },
            )

    @staticmethod
    def _force_activation_decay(
        region: BrainRegion,
        action: RegionStabilityAction,
        circuit,
        memory: Optional[MorphologicalMemory] = None,
    ) -> None:
        """Scale down existing neuron activations in the region by damping factor."""
        if circuit is None:
            return
        all_neurons = (
            getattr(circuit, "input_neurons", [])
            + getattr(circuit, "hidden_neurons", [])
            + getattr(circuit, "output_neurons", [])
        )
        region_neurons = [
            n for n in all_neurons
            if getattr(n, "region", None) == region.region_id or getattr(n, "cell_id", None) in region.neuron_ids
        ]
        if not region_neurons:
            return
        decay = action.damping_factor if action.damping_factor > 0 else 0.5
        for n in region_neurons:
            n.activation = getattr(n, "activation", 0.0) * decay
        if memory is not None:
            memory.create_event(
                event_type=MorphologyEventType.REGION_ACTIVATION_CLAMPED,
                region_id=region.region_id,
                metadata={
                    "reason": "forced_decay_after_stability_action",
                    "action_type": action.action_type,
                    "damping_factor": action.damping_factor,
                    "decay_applied": decay,
                    "neurons_affected": len(region_neurons),
                },
            )

    # ------------------------------------------------------------------ #
    # Pre / post routing checks
    # ------------------------------------------------------------------ #

    def pre_routing_stability_check(
        self,
        registry: RegionRegistry,
        circuit,
        memory: Optional[MorphologicalMemory] = None,
        flow_memory: Optional[Dict[str, Any]] = None,
    ) -> RegionStabilityResult:
        return self._run_stability_check(registry, circuit, memory, phase="pre", flow_memory=flow_memory)

    def post_routing_stability_check(
        self,
        registry: RegionRegistry,
        circuit,
        memory: Optional[MorphologicalMemory] = None,
        flow_memory: Optional[Dict[str, Any]] = None,
    ) -> RegionStabilityResult:
        return self._run_stability_check(registry, circuit, memory, phase="post", flow_memory=flow_memory)

    def _run_stability_check(
        self,
        registry: RegionRegistry,
        circuit,
        memory: Optional[MorphologicalMemory],
        phase: str = "pre",
        flow_memory: Optional[Dict[str, Any]] = None,
    ) -> RegionStabilityResult:
        regions = list(registry.regions.values())
        states: List[RegionStabilityState] = []
        actions: List[RegionStabilityAction] = []
        unstable_count = 0

        # Reset global multipliers each tick
        self._global_routing_multiplier = 1.0
        self._global_plasticity_multiplier = 1.0
        self._brainstem_override_active = False

        for region in regions:
            prev = self._region_states.get(region.region_id)
            prev_activation = prev.activation if prev is not None else 0.0

            # Decrement cooldown
            if prev is not None and prev.cooldown_remaining > 0:
                prev.cooldown_remaining -= 1
                if prev.cooldown_remaining == 0:
                    prev.routing_allowed = True
                    prev.damping_factor = 1.0
                    if memory is not None:
                        memory.create_event(
                            event_type=MorphologyEventType.REGION_STABILITY_RECOVERED,
                            region_id=region.region_id,
                        )

            state = self.compute_region_stability_state(
                region=region,
                circuit=circuit,
                previous_activation=prev_activation,
                previous_state=prev,
                flow_memory=flow_memory,
            )
            if prev is not None:
                state.cooldown_remaining = prev.cooldown_remaining
                state.damping_factor = prev.damping_factor
                state.routing_allowed = prev.routing_allowed

            self._region_states[region.region_id] = state
            states.append(state)

            if memory is not None:
                memory.create_event(
                    event_type=MorphologyEventType.REGION_STABILITY_CHECKED,
                    region_id=region.region_id,
                    metadata={
                        "phase": phase,
                        "instability_score": state.instability_score,
                        "phi": state.phi,
                        "activation": state.activation,
                    },
                )

            if state.instability_score >= 0.25:
                unstable_count += 1
                action = self.decide_stability_action(state)
                if action is not None:
                    actions.append(action)
                    self.apply_stability_action(region, action, memory, circuit)
                    # T34B-FIX: Log activation explosion if triggered by high activation
                    if state.activation >= 1.0 and memory is not None:
                        memory.create_event(
                            event_type=MorphologyEventType.REGION_ACTIVATION_EXPLOSION_DETECTED,
                            region_id=region.region_id,
                            metadata={
                                "instability_score": state.instability_score,
                                "activation": state.activation,
                                "action_type": action.action_type,
                            },
                        )

        # Brainstem override if many regions unstable
        if (
            self.enable_brainstem_override
            and unstable_count >= max(2, len(regions) // 3)
        ):
            self._brainstem_override_active = True
            self._global_routing_multiplier = 0.5
            self._global_plasticity_multiplier = 0.5
            if memory is not None:
                memory.create_event(
                    event_type=MorphologyEventType.BRAINSTEM_STABILITY_OVERRIDE,
                    metadata={
                        "unstable_regions": unstable_count,
                        "total_regions": len(regions),
                        "global_routing_multiplier": self._global_routing_multiplier,
                        "global_plasticity_multiplier": self._global_plasticity_multiplier,
                    },
                )

        if states:
            mean_instability = sum(s.instability_score for s in states) / len(states)
            mean_damping = sum(s.damping_factor for s in states) / len(states)
        else:
            mean_instability = 0.0
            mean_damping = 1.0

        return RegionStabilityResult(
            regions_checked=len(regions),
            unstable_regions=unstable_count,
            actions_applied=len(actions),
            mean_instability_score=round(mean_instability, 4),
            mean_damping_factor=round(mean_damping, 4),
            phi_guard_triggered=any(a.action_type in {"hard_damping", "routing_block"} for a in actions),
            brainstem_override_triggered=self._brainstem_override_active,
        )

    # ------------------------------------------------------------------ #
    # Summarize
    # ------------------------------------------------------------------ #

    def summarize_stability(self) -> Dict[str, Any]:
        return {
            "region_states": {
                rid: s.model_dump() for rid, s in self._region_states.items()
            },
            "global_routing_multiplier": self._global_routing_multiplier,
            "global_plasticity_multiplier": self._global_plasticity_multiplier,
            "brainstem_override_active": self._brainstem_override_active,
        }

    # ------------------------------------------------------------------ #
    # Getters for orchestrator integration
    # ------------------------------------------------------------------ #

    def get_routing_multiplier(self, region_id: str) -> float:
        state = self._region_states.get(region_id)
        if state is None:
            return self._global_routing_multiplier
        if not state.routing_allowed:
            return 0.0
        return self._global_routing_multiplier * state.damping_factor

    def get_plasticity_multiplier(self, region_id: str) -> float:
        state = self._region_states.get(region_id)
        if state is None:
            return self._global_plasticity_multiplier
        return self._global_plasticity_multiplier * state.damping_factor
