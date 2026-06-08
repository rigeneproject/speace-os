"""T-CDS — Continuous Dynamics Substrate Coordinator.

Wires the continuous-time neural substrate modules into the runtime loop:

- TemporalDynamicsEngine  (ODE activations, weights, energy)
- NeuralOscillatorBank     (theta/alpha/beta/gamma rhythms)
- PhaseCouplingEngine      (Kuramoto synchronisation)
- EnergyFieldEngine        (metabolic diffusion field)
- PredictiveCodingEngine   (hierarchical prediction errors)
- ActiveInferenceEngine    (beliefs, EFE, action selection)
- GlobalHomeostaticDrive   (exploration/stability/survival/efficiency)
- CriticalityMonitor       (avalanche / branching ratio)

The coordinator owns *all* continuous modules and is responsible for:

1. Initialising them lazily on first call.
2. Advancing them at a sub-stepping ``dt`` smaller than the runtime
   tick interval (so gamma-band ~40 Hz can actually oscillate within a
   one-second wall-clock tick).
3. Coupling them together (oscillator → ODE forcing, prediction error
   → active inference, drive → plasticity, criticality → threshold).
4. Exposing a small, *observable* state dict to the rest of the runtime
   and to the safety guard.

This module never mutates the host circuit directly: it only feeds
modulations and reads activations. The :class:`CellularBrainOrchestrator`
applies the returned modulations to the real neurons and synapses.
"""
from __future__ import annotations

import json
import logging
import math
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

_logger = logging.getLogger(__name__)


@dataclass
class SubstrateState:
    """Snapshot of the continuous substrate at a given moment.

    Exposed to the rest of the runtime as a plain, JSON-serialisable
    dict. The intent is observability + audit, not introspection: every
    field is either a scalar, a small numpy array cast to ``list``, or a
    short string.
    """

    sim_time: float = 0.0
    wall_time: float = 0.0
    substeps: int = 0
    kuramoto_order_parameter: float = 0.0
    mean_energy_field: float = 1.0
    total_free_energy: float = 0.0
    branching_ratio: float = 0.0
    drives: Dict[str, float] = field(default_factory=dict)
    modulations: Dict[str, float] = field(default_factory=dict)
    fatigue_count: int = 0
    criticality_recommendation: str = "unknown"
    selected_action: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sim_time": self.sim_time,
            "wall_time": self.wall_time,
            "substeps": self.substeps,
            "kuramoto_order_parameter": self.kuramoto_order_parameter,
            "mean_energy_field": self.mean_energy_field,
            "total_free_energy": self.total_free_energy,
            "branching_ratio": self.branching_ratio,
            "drives": dict(self.drives),
            "modulations": dict(self.modulations),
            "fatigue_count": self.fatigue_count,
            "criticality_recommendation": self.criticality_recommendation,
            "selected_action": self.selected_action,
        }


class ContinuousSubstrateCoordinator:
    """Coordinator for the continuous-time substrate modules.

    Parameters
    ----------
    circuit:
        The :class:`NeuralCircuit` whose neurons and synapses feed the
        substrate. Only read-only introspection is used.
    genome:
        The shared genome; dynamics configuration is read from
        ``genome.dynamics`` if available.
    substep_dt:
        Internal sub-step size in *simulated* seconds. The runtime
        advances the substrate by ``tick_interval / substep_dt``
        substeps per outer tick. A ``substep_dt`` of 0.01 with a
        1 s tick interval → 100 substeps, enough for gamma-band
        (40 Hz) dynamics.
    substeps_per_tick:
        Optional explicit substep count. Overrides the ratio derived
        from ``tick_interval`` when given.
    """

    def __init__(
        self,
        circuit: Any,
        genome: Any,
        substep_dt: float = 0.01,
        substeps_per_tick: Optional[int] = None,
    ):
        self._circuit = circuit
        self._genome = genome
        self._substep_dt = float(substep_dt)
        self._substeps_per_tick = substeps_per_tick

        # Lazily initialised modules (filled in by ``initialize``)
        self._temporal_dynamics: Any = None
        self._oscillator_bank: Any = None
        self._phase_coupling: Any = None
        self._energy_field: Any = None
        self._predictive_coding: Any = None
        self._active_inference: Any = None
        self._homeostatic_drive: Any = None
        self._criticality: Any = None

        self._sim_time: float = 0.0
        self._last_wall_time: float = time.time()
        self._total_substeps: int = 0
        self._last_substep_count: int = 0
        self._last_state: SubstrateState = SubstrateState()
        self._initialised: bool = False

        # Active inference state/action registry is configured by the
        # orchestrator via the public ``register_*`` methods below.
        self._ai_registered: bool = False

    # ------------------------------------------------------------------ #
    # Public configuration
    # ------------------------------------------------------------------ #

    def register_active_inference_states(
        self,
        states: Dict[str, float],
        actions: Dict[str, Dict[str, float]],
    ) -> None:
        """Configure the active inference engine.

        Must be called *after* :meth:`initialize` and only once.
        """
        if not self._initialised:
            raise RuntimeError(
                "SubstrateCoordinator.initialize must be called before "
                "register_active_inference_states"
            )
        if self._ai_registered:
            return
        for sid, prior in states.items():
            self._active_inference.register_state(sid, prior)
        for aid, dist in actions.items():
            self._active_inference.register_action(aid, dist)
        self._ai_registered = True

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def initialize(self) -> None:
        """Construct every substrate module and register neurons/synapses.

        Idempotent: safe to call multiple times.
        """
        if self._initialised:
            return

        # Read dynamics config from genome (fallback to safe defaults).
        dyn_cfg = {}
        if self._genome is not None and getattr(self._genome, "dynamics", None):
            try:
                dyn_cfg = self._genome.dynamics.model_dump()
            except Exception:  # pragma: no cover - non-pydantic genome
                dyn_cfg = {}

        neurons = self._all_neurons()
        synapses = list(getattr(self._circuit, "synapses", []) or [])

        # --- Temporal dynamics (ODE) ----------------------------------- #
        td_cfg = dyn_cfg.get("temporal_dynamics", {}) if isinstance(dyn_cfg, dict) else {}
        try:
            from speace_core.cellular_brain.dynamics.temporal_dynamics_engine import (
                TemporalDynamicsEngine,
            )
            self._temporal_dynamics = TemporalDynamicsEngine(
                neurons=neurons,
                synapses=synapses,
                tau=td_cfg.get("tau", 1.0),
                tau_w=td_cfg.get("tau_w", 10.0),
                tau_e=td_cfg.get("tau_e", 5.0),
                noise_std=td_cfg.get("noise_std", 0.0),
                supply=td_cfg.get("supply", 0.1),
                consumption=td_cfg.get("consumption", 0.05),
                plasticity_rate=td_cfg.get("plasticity_rate", 0.05),
            )
        except Exception as exc:  # pragma: no cover - defensive
            _logger.warning("TemporalDynamicsEngine unavailable: %s", exc)

        # --- Neural oscillator bank ----------------------------------- #
        try:
            from speace_core.cellular_brain.dynamics.neural_oscillator_bank import (
                NeuralOscillatorBank,
            )
            self._oscillator_bank = NeuralOscillatorBank()
            for n in neurons:
                # Default to theta coupling; host may rebind later.
                self._oscillator_bank.register_neuron(
                    getattr(n, "cell_id", str(id(n))), "theta", 0.1
                )
        except Exception as exc:  # pragma: no cover
            _logger.warning("NeuralOscillatorBank unavailable: %s", exc)

        # --- Phase coupling (Kuramoto) --------------------------------- #
        try:
            from speace_core.cellular_brain.dynamics.phase_coupling_engine import (
                PhaseCouplingEngine,
            )
            self._phase_coupling = PhaseCouplingEngine(
                default_coupling_strength=1.0
            )
            if self._oscillator_bank is not None:
                for band, params in self._oscillator_bank.bands.items():
                    self._phase_coupling.register_oscillator(
                        band, freq=params["freq"]
                    )
        except Exception as exc:  # pragma: no cover
            _logger.warning("PhaseCouplingEngine unavailable: %s", exc)

        # --- Energy field --------------------------------------------- #
        ef_cfg = dyn_cfg.get("energy_field", {}) if isinstance(dyn_cfg, dict) else {}
        try:
            from speace_core.cellular_brain.dynamics.energy_field_engine import (
                EnergyFieldEngine,
            )
            self._energy_field = EnergyFieldEngine(
                global_supply_rate=ef_cfg.get("global_supply_rate", 0.02),
                recovery_boost=ef_cfg.get("recovery_boost", 0.03),
                fatigue_threshold=ef_cfg.get("fatigue_threshold", 0.2),
            )
            for n in neurons:
                self._energy_field.register_neuron(
                    getattr(n, "cell_id", str(id(n))),
                    baseline_supply=0.1,
                    consumption_rate=0.05,
                    diffusion_rate=0.01,
                    initial_energy=getattr(n, "energy", 1.0),
                )
            for s in synapses:
                if getattr(s, "state", "active") != "pruned":
                    self._energy_field.register_synapse(
                        getattr(s, "source", ""), getattr(s, "target", "")
                    )
        except Exception as exc:  # pragma: no cover
            _logger.warning("EnergyFieldEngine unavailable: %s", exc)

        # --- Predictive coding ---------------------------------------- #
        pc_cfg = dyn_cfg.get("predictive_coding", {}) if isinstance(dyn_cfg, dict) else {}
        try:
            from speace_core.cellular_brain.dynamics.predictive_coding_engine import (
                PredictiveCodingEngine,
            )
            self._predictive_coding = PredictiveCodingEngine(
                learning_rate=pc_cfg.get("learning_rate", 0.1)
            )
            input_dim = len(getattr(self._circuit, "input_neurons", []) or [])
            hidden_dim = len(getattr(self._circuit, "hidden_neurons", []) or [])
            output_dim = len(getattr(self._circuit, "output_neurons", []) or [])
            self._predictive_coding.register_layer("sensory", max(1, input_dim), 0)
            self._predictive_coding.register_layer("association", max(1, hidden_dim), 1)
            self._predictive_coding.register_layer("abstract", max(1, output_dim), 2)
            if input_dim and hidden_dim:
                self._predictive_coding.set_connection("association", "sensory")
            if hidden_dim and output_dim:
                self._predictive_coding.set_connection("abstract", "association")
        except Exception as exc:  # pragma: no cover
            _logger.warning("PredictiveCodingEngine unavailable: %s", exc)

        # --- Active inference ----------------------------------------- #
        try:
            from speace_core.cellular_brain.dynamics.active_inference_engine import (
                ActiveInferenceEngine,
            )
            self._active_inference = ActiveInferenceEngine()
        except Exception as exc:  # pragma: no cover
            _logger.warning("ActiveInferenceEngine unavailable: %s", exc)

        # --- Homeostatic drive ---------------------------------------- #
        hd_cfg = dyn_cfg.get("homeostatic_drive", {}) if isinstance(dyn_cfg, dict) else {}
        try:
            from speace_core.cellular_brain.dynamics.global_homeostatic_drive import (
                GlobalHomeostaticDrive,
            )
            self._homeostatic_drive = GlobalHomeostaticDrive(
                plasticity_range=tuple(hd_cfg.get("plasticity_range", [0.0, 2.0])),
                exploration_range=tuple(hd_cfg.get("exploration_range", [0.0, 2.0])),
                energy_supply_range=tuple(hd_cfg.get("energy_supply_range", [0.5, 1.5])),
                stability_range=tuple(hd_cfg.get("stability_range", [0.5, 1.5])),
                survival_suppression_threshold=hd_cfg.get(
                    "survival_suppression_threshold", 0.3
                ),
                efficiency_plasticity_threshold=hd_cfg.get(
                    "efficiency_plasticity_threshold", -0.2
                ),
            )
        except Exception as exc:  # pragma: no cover
            _logger.warning("GlobalHomeostaticDrive unavailable: %s", exc)

        # --- Criticality monitor -------------------------------------- #
        cm_cfg = dyn_cfg.get("criticality_monitor", {}) if isinstance(dyn_cfg, dict) else {}
        try:
            from speace_core.cellular_brain.dynamics.criticality_monitor import (
                CriticalityMonitor,
            )
            self._criticality = CriticalityMonitor(
                avalanche_window=cm_cfg.get("avalanche_window", 10.0),
                branching_bin_size=cm_cfg.get("branching_bin_size", 5.0),
                max_history=cm_cfg.get("max_history", 10000),
            )
        except Exception as exc:  # pragma: no cover
            _logger.warning("CriticalityMonitor unavailable: %s", exc)

        self._initialised = True
        _logger.info(
            "ContinuousSubstrateCoordinator initialised: %d neurons, %d synapses",
            len(neurons),
            len(synapses),
        )

    # ------------------------------------------------------------------ #
    # Substepping
    # ------------------------------------------------------------------ #

    def substeps_for_tick(self, tick_interval: float) -> int:
        """How many internal substeps to run for a given outer tick.

        Returns ``substeps_per_tick`` if explicitly configured, else
        ``max(1, round(tick_interval / substep_dt))``.
        """
        if self._substeps_per_tick is not None:
            return max(1, int(self._substeps_per_tick))
        if tick_interval <= 0:
            return 1
        return max(1, int(round(tick_interval / self._substep_dt)))

    def advance(
        self,
        tick_interval: float,
        activations: Optional[Dict[str, float]] = None,
        prediction_error: Optional[float] = None,
        external_action_likelihoods: Optional[Dict[str, float]] = None,
        last_drive_metrics: Optional[Dict[str, float]] = None,
    ) -> SubstrateState:
        """Advance the entire continuous substrate by one outer tick.

        Parameters
        ----------
        tick_interval:
            Wall-clock duration of this outer tick (seconds).
        activations:
            Optional per-neuron activations read from the host circuit.
            Used to drive ODE input and energy consumption.
        prediction_error:
            Optional real prediction error from the embodiment layer,
            used to update the active inference beliefs.
        external_action_likelihoods:
            Optional dict mapping ``state_id`` → ``likelihood`` for
            Bayesian updates.
        last_drive_metrics:
            Optional dict of drive source values (e.g.
            ``{"exploration": noise_level, "stability": phi,
            "survival": 1-mean_energy, "efficiency": mean_energy}``).
        """
        if not self._initialised:
            self.initialize()

        n_substeps = self.substeps_for_tick(tick_interval)
        dt = self._substep_dt

        for _ in range(n_substeps):
            self._substep(dt, activations or {}, prediction_error)

        # Make the per-tick substep count observable to callers
        # (the SubstepRuntimeLoop uses the delta between snapshots to
        # report how many substeps ran during the previous outer tick).
        self._last_substep_count = n_substeps

        if external_action_likelihoods and self._active_inference is not None:
            for sid, lik in external_action_likelihoods.items():
                try:
                    self._active_inference.observe(sid, max(0.0, float(lik)))
                except (KeyError, ValueError):
                    pass

        if last_drive_metrics and self._homeostatic_drive is not None:
            for name, value in last_drive_metrics.items():
                try:
                    self._homeostatic_drive.update_drive(name, float(value))
                except KeyError:
                    pass

        modulations: Dict[str, float] = {}
        if self._homeostatic_drive is not None:
            modulations = self._homeostatic_drive.step()

        state = self._collect_state(modulations)
        self._last_state = state
        self._total_substeps += n_substeps
        return state

    def _substep(
        self,
        dt: float,
        activations: Dict[str, float],
        prediction_error: Optional[float],
    ) -> None:
        """Run a single internal substep across all continuous modules."""
        # 1) Oscillator bank advances and computes forcing per neuron.
        forcing_map: Dict[str, float] = {}
        if self._oscillator_bank is not None:
            self._oscillator_bank.step(dt)
            for nid in self._oscillator_bank.list_registered_neurons():
                try:
                    forcing_map[nid] = self._oscillator_bank.get_neural_modulation(nid)
                except KeyError:
                    continue

        # 2) Kuramoto coupling updates phase differences.
        if self._phase_coupling is not None:
            self._phase_coupling.step(dt)

        # 3) ODE activations / weights / energy advance.
        if self._temporal_dynamics is not None:
            for nid, val in activations.items():
                try:
                    self._temporal_dynamics.inject_input(nid, float(val))
                except Exception:
                    continue
            if forcing_map:
                try:
                    self._temporal_dynamics.couple_oscillations(forcing_map)
                except Exception:
                    pass
            try:
                self._temporal_dynamics.step(dt)
            except Exception as exc:  # pragma: no cover - defensive
                _logger.debug("ODE step failed: %s", exc)

        # 4) Energy field: feed in current ODE activations if available.
        if self._energy_field is not None:
            ode_state: Dict[str, float] = {}
            for nid in activations:
                if self._temporal_dynamics is not None:
                    try:
                        ode_state[nid] = self._temporal_dynamics.get_neuron_state(nid)
                    except Exception:
                        ode_state[nid] = activations[nid]
                else:
                    ode_state[nid] = activations[nid]
            try:
                self._energy_field.step(dt, ode_state)
            except Exception as exc:  # pragma: no cover
                _logger.debug("Energy field step failed: %s", exc)

        # 5) Predictive coding: top-down prediction + bottom-up error.
        if self._predictive_coding is not None:
            try:
                self._predictive_coding.step()
            except Exception as exc:  # pragma: no cover
                _logger.debug("Predictive coding step failed: %s", exc)

        # 6) Active inference: select action, propagate beliefs.
        if self._active_inference is not None:
            try:
                self._active_inference.step()
            except Exception as exc:  # pragma: no cover
                _logger.debug("Active inference step failed: %s", exc)

        # 7) Criticality monitor: record activations for avalanche stats.
        if self._criticality is not None and activations:
            for nid, a in activations.items():
                if abs(float(a)) > 0.5:
                    self._criticality.record_activation(
                        nid, self._sim_time + dt
                    )

        self._sim_time += dt

    # ------------------------------------------------------------------ #
    # State / observability
    # ------------------------------------------------------------------ #

    def _collect_state(self, modulations: Dict[str, float]) -> SubstrateState:
        kuramoto = 0.0
        if self._phase_coupling is not None:
            try:
                kuramoto = self._phase_coupling.get_order_parameter()
            except Exception:
                kuramoto = 0.0

        mean_energy = 1.0
        fatigue = 0
        if self._energy_field is not None:
            try:
                mean_energy = self._energy_field.get_global_energy()
                fatigue = len(self._energy_field.get_fatigued_neurons())
            except Exception:
                pass

        free_energy = 0.0
        if self._predictive_coding is not None:
            try:
                free_energy = self._predictive_coding.get_free_energy()
            except Exception:
                pass

        branching = 0.0
        crit_reason = "unknown"
        if self._criticality is not None:
            try:
                branching = self._criticality.get_branching_ratio()
                rec = self._criticality.recommend_modulation()
                crit_reason = rec.get("reason", "unknown")
            except Exception:
                pass

        drives_snapshot: Dict[str, float] = {}
        if self._homeostatic_drive is not None:
            for name in self._homeostatic_drive.list_drives():
                try:
                    drives_snapshot[name] = float(
                        self._homeostatic_drive.get_drive_signal(name)
                    )
                except Exception:
                    pass

        selected = None
        if self._active_inference is not None:
            try:
                selected = self._active_inference.step()
            except Exception:
                selected = None

        self._last_wall_time = time.time()
        return SubstrateState(
            sim_time=self._sim_time,
            wall_time=self._last_wall_time,
            substeps=self._total_substeps,
            kuramoto_order_parameter=float(kuramoto),
            mean_energy_field=float(mean_energy),
            total_free_energy=float(free_energy),
            branching_ratio=float(branching),
            drives=drives_snapshot,
            modulations=dict(modulations),
            fatigue_count=int(fatigue),
            criticality_recommendation=str(crit_reason),
            selected_action=selected,
        )

    @property
    def last_state(self) -> SubstrateState:
        return self._last_state

    @property
    def sim_time(self) -> float:
        return self._sim_time

    # ------------------------------------------------------------------ #
    # Convenience accessors used by other tasks
    # ------------------------------------------------------------------ #

    def get_oscillator_phase(self, band: str) -> Optional[float]:
        if self._oscillator_bank is None:
            return None
        try:
            return self._oscillator_bank.get_phase(band)
        except KeyError:
            return None

    def get_modulations(self) -> Dict[str, float]:
        """Return the latest drive-derived modulation map."""
        if self._homeostatic_drive is None:
            return {
                "plasticity_multiplier": 1.0,
                "exploration_multiplier": 1.0,
                "energy_supply_multiplier": 1.0,
                "stability_multiplier": 1.0,
            }
        return self._homeostatic_drive.get_global_modulation()

    def get_criticality_recommendation(self) -> Dict[str, float]:
        if self._criticality is None:
            return {
                "excitability_delta": 0.0,
                "target_branching_ratio": 1.0,
                "current_branching_ratio": 0.0,
                "reason": "criticality_disabled",
            }
        try:
            return self._criticality.recommend_modulation()
        except Exception:
            return {
                "excitability_delta": 0.0,
                "target_branching_ratio": 1.0,
                "current_branching_ratio": 0.0,
                "reason": "criticality_error",
            }

    def get_free_energy(self) -> float:
        if self._predictive_coding is None:
            return 0.0
        try:
            return float(self._predictive_coding.get_free_energy())
        except Exception:
            return 0.0

    def get_kuramoto_order(self) -> float:
        if self._phase_coupling is None:
            return 0.0
        try:
            return float(self._phase_coupling.get_order_parameter())
        except Exception:
            return 0.0

    def get_mean_energy(self) -> float:
        if self._energy_field is None:
            return 1.0
        try:
            return float(self._energy_field.get_global_energy())
        except Exception:
            return 1.0

    def get_fatigue_count(self, threshold: float = 0.2) -> int:
        if self._energy_field is None:
            return 0
        try:
            return len(self._energy_field.get_fatigued_neurons(threshold))
        except Exception:
            return 0

    def apply_oscillator_forcing_to_workspace(
        self, base_representation: List[float]
    ) -> List[float]:
        """Return a phase-gated copy of *base_representation*.

        Used by the GlobalWorkspace to apply a "temporal binding" gain:
        if the dominant gamma band is in a positive phase, the
        representation is amplified; if in a negative phase, it is
        attenuated. This is a *very* simple model of phase-amplitude
        coupling, sufficient to produce observable binding effects.
        """
        if not base_representation:
            return []
        phase = self.get_oscillator_phase("gamma")
        if phase is None:
            phase = self.get_oscillator_phase("beta")
        if phase is None:
            return list(base_representation)
        gain = 1.0 + 0.5 * math.sin(phase)
        return [float(v) * gain for v in base_representation]

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def snapshot(self) -> Dict[str, Any]:
        """Return a JSON-serialisable snapshot of the substrate state."""
        snap = self._last_state.to_dict()
        snap["config"] = {
            "substep_dt": self._substep_dt,
            "substeps_per_tick": self._substeps_per_tick,
            "initialised": self._initialised,
        }
        return snap

    def save_snapshot(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.snapshot(), fh, indent=2)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _all_neurons(self) -> List[Any]:
        if self._circuit is None:
            return []
        return (
            list(getattr(self._circuit, "input_neurons", []) or [])
            + list(getattr(self._circuit, "hidden_neurons", []) or [])
            + list(getattr(self._circuit, "output_neurons", []) or [])
        )
