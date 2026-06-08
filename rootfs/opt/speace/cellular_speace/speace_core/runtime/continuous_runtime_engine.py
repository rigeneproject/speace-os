"""ContinuousRuntimeEngine — controlled persistent organism loop (T109).

Wraps CellularBrainOrchestrator in a long-running asyncio loop with
circadian phases, health monitoring, checkpointing, safe degradation,
and emergency halt. All governance flags are read-only; the runtime never
modifies source code, executes shell commands, or accesses the internet.
"""

import asyncio
import json
import logging
import pathlib
import time
from typing import Any, Dict, Optional

_logger = logging.getLogger(__name__)

from speace_core.cellular_brain.organism.organism_lifecycle import OrganismLifecycleManager
from speace_core.runtime.checkpoint_manager import CheckpointManager
from speace_core.runtime.circadian_scheduler import CircadianScheduler
from speace_core.runtime.circadian_validator import CircadianValidator
from speace_core.runtime.degradation_drill import DegradationDrill
from speace_core.runtime.emergency_halt_gate import EmergencyHaltGate
from speace_core.runtime.extended_runtime_observer import ExtendedRuntimeObserver
from speace_core.runtime.memory_leak_auditor import MemoryLeakAuditor
from speace_core.runtime.recovery_orchestrator import RecoveryOrchestrator
from speace_core.runtime.runtime_health_monitor import RuntimeHealthMonitor
from speace_core.runtime.safe_degradation_handler import SafeDegradationHandler
from speace_core.cellular_brain.cognitive_evolution.cognitive_homeostasis import CognitiveHomeostasis
from speace_core.cellular_brain.cognition.organism_state_machine import OrganismStateMachine
from speace_core.cellular_brain.cognition.bt_runtime_integration import BTRuntimeIntegration
from speace_core.cellular_brain.regulation.utility_drive_system import UtilityDriveSystem
from speace_core.cellular_brain.regulation.utility_arbitration_engine import UtilityArbitrationEngine
from speace_core.cellular_brain.cognition.goap_runtime_integration import GOAPRuntimeIntegration
from speace_core.cellular_brain.distributed.social_cognition_engine import SocialCognitionEngine
from speace_core.cellular_brain.distributed.trust_reputation_model import TrustReputationModel
from speace_core.cellular_brain.distributed.social_coordinator import SocialCoordinator
from speace_core.cellular_brain.postnatal_learning.nursery_session_orchestrator import NurserySessionOrchestrator
from speace_core.cellular_brain.runtime.coordinators.game_ai_integration_coordinator import (
    GameAIIntegrationCoordinator,
)
from speace_core.cellular_brain.experience.temporal_narrative_engine import TemporalNarrativeEngine
from speace_core.cellular_brain.experience.session_continuity_manager import SessionContinuityManager
from speace_core.cellular_brain.latent_transfer.runtime_latent_integrator import RuntimeLatentIntegrator
from speace_core.cellular_brain.latent_transfer.distributed_latent_sync import DistributedLatentSyncEngine
from speace_core.cellular_brain.language.linguistic_cortical_bridge import LinguisticCorticalBridge


class ContinuousRuntimeEngine:
    """Manages the persistent organism runtime loop."""

    STATES = ("initializing", "running", "paused", "sleeping", "halting", "halted")

    #: Allowed values for ``runtime_mode``.  ``None`` (the default) keeps
    #: the historical, real-hardware behaviour; only ``"simulated"`` is
    #: currently a recognized alternative.  Any other value is rejected
    #: at construction time.
    ALLOWED_RUNTIME_MODES = (None, "simulated")

    def __init__(
        self,
        orchestrator: Any,
        tick_interval: float = 1.0,
        checkpoint_interval_seconds: float = 300.0,
        awake_duration: float = 300.0,
        sleep_duration: float = 60.0,
        runtime_health_config: Optional[Dict[str, Any]] = None,
        emergency_halt_config: Optional[Dict[str, Any]] = None,
        degradation_config: Optional[Dict[str, Any]] = None,
        runtime_mode: Optional[str] = None,
        simulated_seed: int = 42,
        simulated_tick_seconds: Optional[float] = None,
        simulated_enable_anomalies: bool = False,
    ) -> None:
        # Validate runtime_mode up-front so misconfigurations fail loud
        # and early, before any side effects.
        if runtime_mode not in self.ALLOWED_RUNTIME_MODES:
            raise ValueError(
                f"Invalid runtime_mode={runtime_mode!r}. "
                f"Allowed values: {self.ALLOWED_RUNTIME_MODES}."
            )
        self.runtime_mode: Optional[str] = runtime_mode
        self.simulated_seed = int(simulated_seed)
        # Default simulated tick matches the orchestrator's tick_interval
        # so that the simulated world advances at the same rate as the
        # real one.  Fall back to 1.0s if tick_interval is non-positive.
        self.simulated_tick_seconds: float = (
            float(simulated_tick_seconds)
            if simulated_tick_seconds is not None
            else float(tick_interval if tick_interval > 0 else 1.0)
        )
        self.simulated_enable_anomalies = bool(simulated_enable_anomalies)

        self.orchestrator = orchestrator
        self.tick_interval = tick_interval
        self.checkpoint_interval_seconds = checkpoint_interval_seconds

        # Narrative / continuity
        self.narrative_engine = TemporalNarrativeEngine()
        self.session_continuity = SessionContinuityManager()

        # Subsystems
        self.checkpoint_manager = CheckpointManager()
        self.circadian = CircadianScheduler(
            awake_duration=awake_duration,
            sleep_duration=sleep_duration,
            narrative_engine=self.narrative_engine,
        )
        self.health_monitor = RuntimeHealthMonitor(
            target_tick_interval=tick_interval,
            **(runtime_health_config or {}),
        )
        self.observer = ExtendedRuntimeObserver(
            history_window_seconds=3600.0,
            report_interval_seconds=600.0,
            narrative_engine=self.narrative_engine,
        )
        self.circadian_validator = CircadianValidator(
            narrative_engine=self.narrative_engine,
        )
        self.memory_auditor = MemoryLeakAuditor(
            sample_interval_seconds=300.0,
            narrative_engine=self.narrative_engine,
        )
        self.latent_integrator = RuntimeLatentIntegrator(
            orchestrator=self.orchestrator,
            vector_dim=64,
            narrative_engine=self.narrative_engine,
        )
        self.distributed_sync = DistributedLatentSyncEngine(
            node_id="local_runtime",
            latent_bus=self.latent_integrator.local_bus,
            sync_interval_ticks=10,
        )
        self.degradation_handler = SafeDegradationHandler(
            narrative_engine=self.narrative_engine,
            **(degradation_config or {}),
        )
        self.halt_gate = EmergencyHaltGate(
            checkpoint_manager=self.checkpoint_manager,
            narrative_engine=self.narrative_engine,
            **(emergency_halt_config or {}),
        )
        self.recovery = RecoveryOrchestrator(
            checkpoint_manager=self.checkpoint_manager,
            narrative_engine=self.narrative_engine,
            session_continuity=self.session_continuity,
        )
        self.cognitive_homeostasis = CognitiveHomeostasis()
        self.organism_state_machine = OrganismStateMachine(narrative_engine=self.narrative_engine)
        self.bt_integration = BTRuntimeIntegration(narrative_engine=self.narrative_engine)
        self.utility_drive_system = UtilityDriveSystem()
        self.utility_arbitration = UtilityArbitrationEngine(drive_system=self.utility_drive_system)
        self.goap_integration = GOAPRuntimeIntegration(narrative_engine=self.narrative_engine)
        self.social_cognition = SocialCognitionEngine()
        self.trust_reputation = TrustReputationModel()
        self.social_coordinator = SocialCoordinator(trust_model=self.trust_reputation)
        self.nursery_orchestrator = NurserySessionOrchestrator(narrative_engine=self.narrative_engine)
        self.linguistic_bridge = LinguisticCorticalBridge(language="it")
        self.game_ai_coordinator = GameAIIntegrationCoordinator(
            organism_state_machine=self.organism_state_machine,
            utility_drive_system=self.utility_drive_system,
            utility_arbitration=self.utility_arbitration,
            bt_integration=self.bt_integration,
            goap_integration=self.goap_integration,
            narrative_engine=self.narrative_engine,
        )

        # Phase 2 — Simulated Embodiment
        self._simulated_environment: Any = None
        self._digital_twin: Any = None

        # Punto 5 — Simulated Sensor Adapter (runtime_mode="simulated")
        self._simulated_sensor_adapter: Any = None

        # Phase 3 — Limited Physical Embodiment
        self._micro_actuator: Any = None

        # Phase 4 — Distributed Mature Organism
        self._distributed_organism: Any = None

        # Lifecycle (external to orchestrator)
        self.lifecycle = OrganismLifecycleManager(initial_state="initializing")

        # Runtime state
        self._state: str = "initializing"
        self._task: Optional[asyncio.Task] = None
        self._last_checkpoint_at: float = 0.0
        self._tick_count_since_start: int = 0
        self._started_at: float = 0.0

        # T-SRL — continuous substepping layer (opt-in)
        self._substrate_coordinator: Any = None
        self._stability_guard: Any = None
        self._substep_loop: Any = None
        self._last_substrate_free_energy: float = 0.0
        self._last_substrate_state: Any = None
        self._last_guard_report: Any = None

        # Self-improvement runtime hook (opt-in). When attached, the
        # runtime invokes it once per outer tick to feed substrate
        # metrics into the SelfImprovementLoop and consolidate the
        # result in the EvolutionaryMemoryGovernor. See
        # ``speace_core.runtime.self_improvement_runtime_hook``.
        self._self_improvement_hook: Any = None
        # T-Phase 8F — MM-APR Hard Veto Router (opt-in). When
        # attached, the runtime surfaces the router's summary in
        # ``snapshot()`` and the router's audit_dir is writable. The
        # router itself is invoked by the SelfImprovementLoop (when
        # the loop has ``mmapr_router`` set), not by the runtime
        # directly, so this attribute is purely informational and
        # used by the snapshot view.
        self._mmapr_veto_router: Any = None

    # ------------------------------------------------------------------ #
    # T-SRL / T-CDS — Continuous substrate attachment
    # ------------------------------------------------------------------ #

    def attach_continuous_substrate(
        self,
        substrate_coordinator: Any,
        stability_guard: Any = None,
    ) -> None:
        """Attach a :class:`ContinuousSubstrateCoordinator` to this runtime.

        The substrate advances at sub-second resolution on every outer
        tick. The optional stability guard is invoked once per outer
        tick and can request an emergency halt.
        """
        from speace_core.runtime.substep_runtime_loop import SubstepRuntimeLoop

        self._substrate_coordinator = substrate_coordinator
        self._stability_guard = stability_guard
        self._substep_loop = SubstepRuntimeLoop(
            substrate_coordinator=substrate_coordinator,
            stability_guard=stability_guard,
        )
        _logger.info(
            "Continuous substrate attached: substep_dt=%s",
            getattr(substrate_coordinator, "_substep_dt", "?"),
        )

    def tick_substrate(
        self,
        tick_interval: Optional[float] = None,
        activations: Optional[Dict[str, float]] = None,
        prediction_error: Optional[float] = None,
        external_action_likelihoods: Optional[Dict[str, float]] = None,
        last_drive_metrics: Optional[Dict[str, float]] = None,
    ) -> Optional[Any]:
        """Run a single substepped advance of the continuous substrate.

        Returns the :class:`SubstepResult` (or ``None`` if no substrate
        is attached). Catches and logs all internal errors so the
        outer loop never crashes because of the substrate.
        """
        if self._substep_loop is None:
            return None
        interval = (
            float(tick_interval)
            if tick_interval is not None
            else float(self.tick_interval)
        )
        try:
            result = self._substep_loop.advance(
                tick_interval=interval,
                activations=activations,
                prediction_error=prediction_error,
                external_action_likelihoods=external_action_likelihoods,
                last_drive_metrics=last_drive_metrics,
            )
        except Exception as exc:  # pragma: no cover
            _logger.exception("Substrate tick failed: %s", exc)
            return None

        self._last_substrate_state = getattr(result, "substrate_state", None)
        self._last_guard_report = getattr(result, "guard_report", None)
        if self._last_substrate_state is not None:
            self._last_substrate_free_energy = float(
                getattr(self._last_substrate_state, "total_free_energy", 0.0)
            )
        if getattr(result, "halt_requested", False):
            _logger.warning(
                "Substrate stability guard requested emergency halt"
            )
            # Best-effort: schedule an async halt. We can't await here.
            try:
                self._state = "halting"
            except Exception:
                pass
        return result

    # ------------------------------------------------------------------ #
    # Self-improvement runtime hook (opt-in)
    # ------------------------------------------------------------------ #

    def attach_self_improvement_hook(self, hook: Any) -> None:
        """Attach a :class:`SelfImprovementRuntimeHook` to this runtime.

        The hook is invoked once per outer tick (right after the
        orchestrator's own ``_tick()``) and receives the latest
        substrate state. It is **opt-in**: until this method is called,
        the runtime never imports or references the self-improvement
        stack, preserving the runtime's existing behaviour bit-for-bit.
        """
        if hook is None:
            raise ValueError("self-improvement hook cannot be None")
        self._self_improvement_hook = hook
        _logger.info(
            "Self-improvement runtime hook attached (cycle_interval_ticks=%s)",
            getattr(hook, "cycle_interval_ticks", "?"),
        )

    def attach_mmapr_veto_router(self, router: Any) -> None:
        """Attach a :class:`HardVetoRouter` (MM-APR) to this runtime.

        The router is **informational** at the runtime layer: it does
        not introduce a new tick because the actual veto decision is
        made by the :class:`SelfImprovementLoop` via its
        ``mmapr_router`` attribute (see Phase 8C). What the runtime
        does is:

        1. Expose ``router.summary()`` in ``snapshot()`` so the
           supervision dashboard can read it.
        2. Validate that the router has a working ``audit_dir`` if
           one is configured (i.e. the directory is writable).

        This is **opt-in**: without this method, the runtime's
        snapshot view never references MM-APR.
        """
        if router is None:
            raise ValueError("MM-APR veto router cannot be None")
        self._mmapr_veto_router = router
        # Sanity-check the audit directory if configured
        audit_dir = getattr(router, "audit_dir", None)
        if audit_dir is not None:
            try:
                pathlib.Path(audit_dir).mkdir(parents=True, exist_ok=True)
            except Exception as exc:  # pragma: no cover - defensive
                _logger.warning(
                    "MM-APR audit_dir %s is not writable: %s", audit_dir, exc
                )
        _logger.info(
            "MM-APR veto router attached (audit_dir=%s)",
            str(audit_dir) if audit_dir is not None else "<disabled>",
        )

    # ------------------------------------------------------------------ #
    # Lifecycle control
    # ------------------------------------------------------------------ #

    async def start(self) -> Dict[str, Any]:
        """Initialize and begin the runtime loop."""
        self._state = "initializing"
        self._started_at = time.time()

        # Attempt recovery from checkpoint
        recovery_info = self.recovery.boot(self.orchestrator)
        if recovery_info["status"] == "recovered":
            self._tick_count_since_start = recovery_info.get("tick", 0)

        # Transition lifecycle to active
        self.lifecycle.transition_to("active", reason="runtime_start")

        # Enable key organismic subsystems for T109
        self.orchestrator.sleep_enabled = True
        self.orchestrator.brainstem_controller_enabled = True
        self.orchestrator.global_workspace_enabled = True
        self.orchestrator.temporal_dynamics_enabled = True
        self.orchestrator.neural_oscillator_enabled = True
        self.orchestrator.phase_coupling_enabled = True
        self.orchestrator.energy_field_enabled = True
        self.orchestrator.predictive_coding_enabled = True
        self.orchestrator.active_inference_enabled = True
        self.orchestrator.homeostatic_drive_enabled = True
        self.orchestrator.criticality_monitor_enabled = True
        # T147 — activate embodied sensory stream
        self.orchestrator.embodiment_enabled = True
        if hasattr(self.orchestrator, "_initialize_dynamic_modules"):
            self.orchestrator._initialize_dynamic_modules()

        # Phase 2 — initialize simulated embodiment if sensors are available.
        # Use defensive getattr() so partial orchestrators (mocks, reduced builds)
        # do not raise AttributeError during start().
        _sensor_array = getattr(self.orchestrator, "_sensor_array", None)
        _physical_environment = getattr(self.orchestrator, "_physical_environment", None)
        if (
            getattr(self.orchestrator, "embodiment_enabled", False)
            and _sensor_array is not None
            and _physical_environment is not None
        ):
            from speace_core.cellular_brain.embodiment.digital_twin_model import DigitalTwinModel
            from speace_core.cellular_brain.embodiment.simulated_environment_engine import SimulatedEnvironmentEngine

            self._digital_twin = DigitalTwinModel(
                sensor_array=_sensor_array,
                environment_model=_physical_environment,
            )
            self._simulated_environment = SimulatedEnvironmentEngine(
                digital_twin=self._digital_twin,
            )
            self.narrative_engine.record(
                event_type="simulated_embodiment_initialized",
                description="Digital twin and simulated environment engine initialized.",
                importance=5,
            )

        # Punto 5 — Activate simulated runtime mode if requested.  This
        # replaces the orchestrator's real sensor array with the
        # SimulatedSensorAdapter that wraps the Punto 4 SimulatedOrganism,
        # so the rest of the loop (and the orchestrator's tick pipeline)
        # consume synthetic data through the same code path.  All
        # existing guardrails (sandbox profile, action approval, halt
        # gate, checkpointing) remain active — this block only swaps
        # the input source, not the governance.
        if self.runtime_mode == "simulated":
            self._activate_simulated_mode()

        # Phase 3 — initialize limited physical embodiment (micro-actuator)
        from speace_core.cellular_brain.embodiment.micro_actuator_controller import MicroActuatorController

        self._micro_actuator = MicroActuatorController()
        self.narrative_engine.record(
            event_type="micro_actuator_initialized",
            description="MicroActuatorController initialized for Phase 3.",
            importance=5,
        )

        # Phase 4 — initialize distributed organism controller (observational only)
        from speace_core.cellular_brain.embodiment.distributed_organism_controller import DistributedOrganismController

        self._distributed_organism = DistributedOrganismController()
        self.narrative_engine.record(
            event_type="distributed_organism_initialized",
            description="DistributedOrganismController initialized for Phase 4.",
            importance=5,
        )

        self._state = "running"
        self._task = asyncio.create_task(self._loop())

        self.narrative_engine.record(
            event_type="runtime_start",
            description="Continuous runtime engine started.",
            importance=7,
            metadata={
                "tick_interval": self.tick_interval,
                "checkpoint_interval": self.checkpoint_interval_seconds,
                "recovery_status": recovery_info["status"],
            },
        )

        return {
            "state": self._state,
            "recovery": recovery_info,
            "resume_narrative": self.recovery.resume_narrative(),
        }

    # ------------------------------------------------------------------ #
    # Punto 5 — simulated runtime mode
    # ------------------------------------------------------------------ #

    def _activate_simulated_mode(self) -> None:
        """Wire the orchestrator to a :class:`SimulatedSensorAdapter`.

        What this method does, in order:

        1. Stops (or never starts) the orchestrator's real
           :class:`CyberPhysicalSensorArray` so the simulated path is
           the single source of truth for sensor data.
        2. Constructs a :class:`SimulatedSensorAdapter` wrapping the
           Punto 4 :class:`SimulatedOrganism` and the
           ``sensor_bridge`` translation layer.
        3. Swaps the orchestrator's ``_sensor_array`` attribute to the
           adapter.  All downstream code (digital twin, embodied
           actuator, physical environment) continues to call
           ``read_all()`` through the same interface.
        4. Records the activation both in the narrative engine
           (in-process) and in the persistent audit log
           ``data/sandbox/runtime_mode_activations.jsonl``.

        This method is a no-op in safe mode (i.e. when
        ``self.runtime_mode != "simulated"``); it is only invoked from
        :meth:`start` after the explicit runtime_mode check.
        """
        from speace_core.runtime.simulated_sensor_adapter import (
            SIMULATED_MODE,
            SimulatedSensorAdapter,
        )

        # Step 1: stop (or skip) the real sensor array.  We use
        # defensive hasattr() because partial orchestrators (e.g.
        # lightweight test doubles) may not have one.
        existing_sensor_array = getattr(self.orchestrator, "_sensor_array", None)
        if existing_sensor_array is not None and hasattr(
            existing_sensor_array, "stop_continuous_sampling"
        ):
            try:
                existing_sensor_array.stop_continuous_sampling()
            except Exception as exc:  # noqa: BLE001
                _logger.warning(
                    "Failed to stop real sensor array before simulated mode: %s",
                    exc,
                )

        # Step 2: build the adapter.
        self._simulated_sensor_adapter = SimulatedSensorAdapter(
            seed=self.simulated_seed,
            tick_seconds=self.simulated_tick_seconds,
            enable_anomalies=self.simulated_enable_anomalies,
            orchestrator=self.orchestrator,
        )

        # Step 3: wire it into the orchestrator.  The orchestrator's
        # tick pipeline already calls ``self._sensor_array.read_all()``
        # (orchestrator.py line ~655), so this single attribute swap
        # re-routes the entire sensor pipeline through the simulator.
        self.orchestrator._sensor_array = self._simulated_sensor_adapter
        # Also surface the adapter to the rest of the engine for tests
        # and audit hooks.
        self.orchestrator._simulated_sensor_adapter = self._simulated_sensor_adapter

        # Step 4: audit.  Both in-process (narrative) and persistent
        # (JSONL on disk) so the activation is observable from both
        # the engine and external log analyzers.
        self.narrative_engine.record(
            event_type="simulated_runtime_mode_activated",
            description=(
                "Runtime is now using the SimulatedSensorAdapter; the "
                "orchestrator's sensor pipeline is fed by SimulatedOrganism."
            ),
            importance=7,
            metadata={
                "runtime_mode": SIMULATED_MODE,
                "seed": self.simulated_seed,
                "tick_seconds": self.simulated_tick_seconds,
                "enable_anomalies": self.simulated_enable_anomalies,
                "stage": "2.5-sandbox-lab",
            },
        )
        self._log_runtime_mode_activation(event="simulated_mode_activated")

    def _log_runtime_mode_activation(self, event: str) -> None:
        """Append one JSONL line to
        ``data/sandbox/runtime_mode_activations.jsonl``.

        The line carries the timestamp, event name, runtime mode,
        orchestrator id, current user, container detection flag, and
        any other context that is useful for offline auditing.  Errors
        are swallowed with a warning so that an unwritable audit
        directory does not bring the engine down (the activation
        itself is also recorded in the narrative engine).
        """
        import getpass
        import json
        import os
        import socket
        from datetime import datetime, timezone

        try:
            log_dir = pathlib.Path("data") / "sandbox"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / "runtime_mode_activations.jsonl"

            try:
                user = getpass.getuser()
            except Exception:  # noqa: BLE001
                user = "unknown"
            try:
                hostname = socket.gethostname()
            except Exception:  # noqa: BLE001
                hostname = "unknown"

            orchestrator_id = getattr(self.orchestrator, "node_id", None) or id(
                self.orchestrator
            )
            in_container = (
                os.path.exists("/.dockerenv")
                or os.path.isdir("/proc/1/cgroup")
            )

            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": event,
                "runtime_mode": self.runtime_mode,
                "stage": "2.5-sandbox-lab",
                "user": user,
                "hostname": hostname,
                "in_container": bool(in_container),
                "orchestrator_id": str(orchestrator_id),
                "seed": self.simulated_seed,
                "tick_seconds": self.simulated_tick_seconds,
                "enable_anomalies": self.simulated_enable_anomalies,
            }
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as exc:  # noqa: BLE001
            _logger.warning(
                "Failed to write runtime_mode_activations.jsonl entry: %s",
                exc,
            )

    async def pause(self) -> None:
        if self._state == "running":
            self._state = "paused"
            self.narrative_engine.record(
                event_type="runtime_pause",
                description="Runtime paused by operator.",
                importance=5,
            )

    async def resume(self) -> None:
        if self._state == "paused":
            self._state = "running"
            self.narrative_engine.record(
                event_type="runtime_resume",
                description="Runtime resumed by operator.",
                importance=5,
            )
        elif self._state == "halted":
            self.halt_gate.reset()
            self._state = "running"
            self.narrative_engine.record(
                event_type="runtime_resume",
                description="Runtime resumed from halted state by operator.",
                importance=6,
            )
            if self._task is None or self._task.done():
                self._task = asyncio.create_task(self._loop())

    async def halt(self) -> None:
        if self._state in ("running", "paused", "sleeping"):
            self._state = "halting"
            self.narrative_engine.record(
                event_type="runtime_halt_requested",
                description="Halt requested by operator.",
                importance=6,
            )
            # Let the loop handle graceful shutdown on next iteration

    async def force_checkpoint(self) -> Dict[str, Any]:
        cp = self.checkpoint_manager.save(
            orchestrator=self.orchestrator,
            runtime_state=self._state,
            circadian_phase=self.circadian.phase,
        )
        self._last_checkpoint_at = time.time()
        return cp

    async def stop(self) -> None:
        self._state = "halting"
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        # Final checkpoint
        try:
            self.checkpoint_manager.save(
                orchestrator=self.orchestrator,
                runtime_state="halted",
                circadian_phase=self.circadian.phase,
            )
        except Exception:
            logging.getLogger(__name__).warning("Checkpoint save failed during halt", exc_info=True)
        # T147 — stop embodied sensory stream
        try:
            if (
                self.orchestrator._sensor_array is not None
                and hasattr(self.orchestrator._sensor_array, "stop_continuous_sampling")
            ):
                self.orchestrator._sensor_array.stop_continuous_sampling()
        except Exception:
            logging.getLogger(__name__).warning("Sensor array stop failed during halt", exc_info=True)
        self._state = "halted"
        self._task = None

    # ------------------------------------------------------------------ #
    # Main loop
    # ------------------------------------------------------------------ #

    async def _loop(self) -> None:
        try:
            while self._state not in ("halted", "halting"):
                if self._state == "paused":
                    await asyncio.sleep(self.tick_interval)
                    continue

                loop_start = time.time()
                previous_phase = self.circadian.phase

                # Circadian phase tick
                phase = self.circadian.tick()
                if phase != previous_phase:
                    self.circadian_validator.record_phase_transition(previous_phase, phase)
                is_sleeping = self.circadian.is_sleeping()
                if is_sleeping and self._state != "sleeping":
                    self._state = "sleeping"
                elif not is_sleeping and self._state == "sleeping":
                    self._state = "running"

                # T169 — Game AI Integration Pipeline (T163–T166)
                try:
                    self.game_ai_coordinator.tick(
                        health_score=self.health_monitor.health_score(),
                        cognitive_load=min(1.0, self.health_monitor._tick_latency_ms / 1000.0),
                        prediction_error=0.0,
                        energy=self.health_monitor.health_score(),
                        curiosity_score=0.0,
                        circadian_phase=phase,
                        sensor_snapshot=self.orchestrator._last_sensor_snapshot if self.orchestrator.embodiment_enabled else None,
                    )
                except Exception:
                    logging.getLogger(__name__).warning("Game AI coordinator tick failed", exc_info=True)

                # T170 — Linguistic Cortical Bridge (periodic reflective narrative)
                try:
                    if self._tick_count_since_start % 60 == 0 and self._tick_count_since_start > 0:
                        reflective = await self.linguistic_bridge.reflective_narrative(self.snapshot())
                        if reflective.get("narrative"):
                            self.narrative_engine.record(
                                event_type="llm_reflective_narrative",
                                description=reflective["narrative"],
                                importance=4,
                                metadata={
                                    "latency_ms": reflective.get("latency_ms"),
                                    "mode": reflective.get("mode"),
                                    "governance": reflective.get("governance", {}),
                                },
                            )
                except Exception:
                    logging.getLogger(__name__).warning("Reflective narrative generation failed", exc_info=True)

                # T167 — Social Cognition Layer
                try:
                    if self._distributed_organism is not None:
                        nodes = getattr(self._distributed_organism, "known_nodes", [])
                        for node in nodes:
                            self.social_cognition.record_interaction(
                                node_id=node,
                                event_type="latent_sync",
                                outcome="observed",
                            )
                            self.trust_reputation.record_positive(node)
                except Exception:
                    logging.getLogger(__name__).warning("Social cognition recording failed", exc_info=True)

                # Orchestrator tick
                tick_latency_start = time.time()
                try:
                    await self.orchestrator._tick()
                    self._tick_count_since_start += 1
                    self.health_monitor.record_tick(
                        latency_ms=(time.time() - tick_latency_start) * 1000.0
                    )
                except Exception:
                    self.health_monitor.record_exception()

                # Self-improvement runtime hook: feed substrate metrics
                # into the SelfImprovementLoop and consolidate the
                # result in the EvolutionaryMemoryGovernor. Runs only
                # if a hook has been attached (opt-in).
                try:
                    if self._self_improvement_hook is not None:
                        await self._self_improvement_hook.tick(
                            tick=self._tick_count_since_start,
                            orchestrator=self.orchestrator,
                            substrate_state=self._last_substrate_state,
                        )
                except Exception:
                    logging.getLogger(__name__).warning(
                        "Self-improvement hook tick failed", exc_info=True
                    )

                # Cross-process dashboard visibility: write lightweight snapshot every 5 ticks
                try:
                    if self._tick_count_since_start % 5 == 0:
                        snapshot_path = pathlib.Path("data/runtime/latest_snapshot.json")
                        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
                        with snapshot_path.open("w", encoding="utf-8") as f:
                            json.dump(self.snapshot(), f, ensure_ascii=False, indent=2, default=str)
                except Exception:
                    logging.getLogger(__name__).warning("Snapshot write failed", exc_info=True)

                # T162 — Cognitive Integration & Systemic Harmony
                try:
                    if getattr(self.orchestrator, "systemic_harmony_enabled", False):
                        sh_layer = getattr(self.orchestrator, "_systemic_harmony_layer", None)
                        if sh_layer is not None:
                            sh_layer.tick()
                except Exception:
                    logging.getLogger(__name__).warning("Systemic harmony tick failed", exc_info=True)

                # Memory RSS (best effort)
                try:
                    import psutil
                    proc = psutil.Process()
                    self.health_monitor.update_memory(proc.memory_info().rss / (1024 * 1024))
                except Exception:
                    logging.getLogger(__name__).warning("Memory RSS update failed", exc_info=True)

                # Extended runtime observation (T111)
                try:
                    self.observer.sample(
                        memory_rss_mb=self.health_monitor._peak_memory_rss_mb,
                        health_score=self.health_monitor.health_score(),
                        tick_latency_ms=self.health_monitor._tick_latency_ms,
                        orchestrator=self.orchestrator,
                    )
                except Exception:
                    logging.getLogger(__name__).warning("Runtime observation failed", exc_info=True)

                # T147 — Embodied sensory narrative logging
                try:
                    if self.orchestrator.embodiment_enabled and self.orchestrator._last_sensor_snapshot:
                        snap = self.orchestrator._last_sensor_snapshot
                        cpu_pct = snap.get("cpu", {}).get("usage_percent_normalized")
                        mem_pct = snap.get("memory", {}).get("percent_normalized")
                        temp_cpu = snap.get("temperature", {}).get("cpu_celsius_normalized")
                        fs_events = snap.get("filesystem", {}).get("event_count", 0)

                        if cpu_pct is not None and cpu_pct > 0.8:
                            self.narrative_engine.record(
                                event_type="embodied_sensory_alert",
                                description=f"CPU usage elevated: {cpu_pct:.2f}",
                                importance=6,
                                metadata={"sensor": "cpu", "value": cpu_pct},
                            )
                        if mem_pct is not None and mem_pct > 0.9:
                            self.narrative_engine.record(
                                event_type="embodied_sensory_alert",
                                description=f"Memory usage critical: {mem_pct:.2f}",
                                importance=7,
                                metadata={"sensor": "memory", "value": mem_pct},
                            )
                        if temp_cpu is not None and temp_cpu > 0.7:
                            self.narrative_engine.record(
                                event_type="embodied_sensory_alert",
                                description=f"CPU temperature high: {temp_cpu:.2f}",
                                importance=6,
                                metadata={"sensor": "temperature", "value": temp_cpu},
                            )
                        if fs_events > 0:
                            self.narrative_engine.record(
                                event_type="embodied_filesystem_event",
                                description=f"Filesystem activity: {fs_events} events detected",
                                importance=3,
                                metadata={"sensor": "filesystem", "event_count": fs_events},
                            )
                except Exception:
                    logging.getLogger(__name__).warning("Embodied sensory narrative logging failed", exc_info=True)

                # Phase 2 — Simulated Embodiment: run sandboxed experiments periodically
                try:
                    if (
                        self._simulated_environment is not None
                        and self._tick_count_since_start % 100 == 0
                        and self._tick_count_since_start > 0
                    ):
                        # Observe current twin state before simulation
                        self._digital_twin.observe()
                        delta = self._digital_twin.observe_delta()
                        if delta:
                            self._digital_twin.infer_hypotheses_from_delta()

                        # Run one sandboxed experiment
                        result = self._simulated_environment.run_experiment("perturbation")
                        if result.get("safe"):
                            self.narrative_engine.record(
                                event_type="simulated_experiment",
                                description=(
                                    f"Sandbox experiment {result['experiment_id']} predicted "
                                    f"{result['consequences']['effect_count']} effects with max risk "
                                    f"{result['consequences']['max_risk_score']:.2f}"
                                ),
                                importance=4,
                                metadata={
                                    "experiment_id": result["experiment_id"],
                                    "experiment_type": result["experiment_type"],
                                    "safe": result["safe"],
                                    "effects": result["consequences"]["effects"],
                                },
                            )
                        else:
                            self.narrative_engine.record(
                                event_type="simulated_experiment_unsafe",
                                description=(
                                    f"Sandbox experiment {result['experiment_id']} blocked: "
                                    f"risk {result['consequences']['max_risk_score']:.2f} exceeds threshold"
                                ),
                                importance=6,
                                metadata={
                                    "experiment_id": result["experiment_id"],
                                    "max_risk_score": result["consequences"]["max_risk_score"],
                                },
                            )
                except Exception:
                    logging.getLogger(__name__).warning("Sandbox experiment tick failed", exc_info=True)

                # Memory leak audit (T113)
                try:
                    self.memory_auditor.sample(self.orchestrator)
                except Exception:
                    logging.getLogger(__name__).warning("Memory leak audit sample failed", exc_info=True)

                # Latent vector integration (T117 — observe-only)
                try:
                    self.latent_integrator.tick()
                except Exception:
                    logging.getLogger(__name__).warning("Distributed latent sync tick failed", exc_info=True)

                # Distributed latent sync (T118 — observe-only)
                try:
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(
                        None, self.distributed_sync.tick
                    )
                except Exception:
                    logging.getLogger(__name__).warning("Latent integrator tick failed", exc_info=True)

                # Brainstem state extraction
                brainstem_state = self._brainstem_state()

                # Emergency halt evaluation
                halt_reason = self.halt_gate.evaluate(
                    runtime_health=self.health_monitor.snapshot(),
                    brainstem_state=brainstem_state,
                    memory_rss_mb=self.health_monitor._peak_memory_rss_mb,
                    orchestrator=self.orchestrator,
                    runtime_state=self._state,
                    circadian_phase=phase,
                )
                if halt_reason is not None:
                    self._state = "halted"
                    break

                # Safe degradation
                if self.health_monitor.is_degraded():
                    self.degradation_handler.evaluate(
                        runtime_health=self.health_monitor.snapshot(),
                        brainstem_state=brainstem_state,
                        orchestrator=self.orchestrator,
                    )

                # Periodic checkpoint
                if (time.time() - self._last_checkpoint_at) >= self.checkpoint_interval_seconds:
                    try:
                        self.checkpoint_manager.save(
                            orchestrator=self.orchestrator,
                            runtime_state=self._state,
                            circadian_phase=phase,
                        )
                        self._last_checkpoint_at = time.time()
                        self.observer.record_checkpoint()
                    except Exception:
                        logging.getLogger(__name__).warning("Periodic checkpoint save failed", exc_info=True)

                # Session continuity save
                try:
                    self.session_continuity.save({
                        "active_human": getattr(self, "_active_human", None),
                        "last_topic": getattr(self, "_last_topic", None),
                        "tick_count": self._tick_count_since_start,
                        "runtime_state": self._state,
                        "circadian_phase": phase,
                    })
                except Exception:
                    logging.getLogger(__name__).warning("Session continuity save failed", exc_info=True)

                # Sleep until next tick
                elapsed = time.time() - loop_start
                sleep_time = max(0.0, self.tick_interval - elapsed)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            pass
        finally:
            if self._state == "halting":
                self._state = "halted"

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _brainstem_state(self) -> str:
        ctrl = getattr(self.orchestrator, "_brainstem_controller", None)
        if ctrl is None:
            return "unknown"
        # BrainstemFunctionalController stores state in .last_state or ._current_state
        if hasattr(ctrl, "last_state"):
            return str(ctrl.last_state.state)
        if hasattr(ctrl, "_current_state"):
            return str(ctrl._current_state)
        return "unknown"

    # ------------------------------------------------------------------ #
    # Degradation drill (T114)
    # ------------------------------------------------------------------ #

    async def run_degradation_drill(
        self,
        scenario: str = "memory_pressure",
        duration_seconds: float = 30.0,
    ) -> Dict[str, Any]:
        drill = DegradationDrill(
            orchestrator=self.orchestrator,
            health_monitor=self.health_monitor,
            degradation_handler=self.degradation_handler,
            narrative_engine=self.narrative_engine,
        )
        return await drill.run_drill(scenario=scenario, duration_seconds=duration_seconds)

    # ------------------------------------------------------------------ #
    # Snapshot
    # ------------------------------------------------------------------ #

    def snapshot(self) -> Dict[str, Any]:
        return {
            "state": self._state,
            "tick_count": getattr(self.orchestrator, "current_tick", 0),
            "ticks_since_start": self._tick_count_since_start,
            "uptime_seconds": time.time() - self._started_at if self._started_at else 0,
            "tick_interval": self.tick_interval,
            "circadian": self.circadian.phase_context(),
            "health": self.health_monitor.snapshot(),
            "lifecycle": self.lifecycle.snapshot(),
            "halt": self.halt_gate.snapshot(),
            "degradation": self.degradation_handler.summary(),
            "recovery": self.recovery.snapshot(),
            "extended_observation": self.observer.summary(),
            "memory_audit": self.memory_auditor.summary(),
            "circadian_validation": self.circadian_validator.validate(self.orchestrator),
            "latent_integration": self.latent_integrator.snapshot(),
            "distributed_sync": self.distributed_sync.snapshot(),
            "organism_state": self.organism_state_machine.snapshot(),
            "behavior_trees": self.bt_integration.snapshot(),
            "utility_drives": self.utility_drive_system.snapshot(),
            "utility_arbitration": self.utility_arbitration.snapshot(),
            "goap": self.goap_integration.snapshot(),
            "social_cognition": self.social_cognition.snapshot(),
            "trust_reputation": self.trust_reputation.snapshot(),
            "social_coordinator": self.social_coordinator.snapshot(),
            "nursery": self.nursery_orchestrator.snapshot(),
            "linguistic_bridge": self.linguistic_bridge.snapshot(),
            "game_ai_pipeline": self.game_ai_coordinator.snapshot(),
            "self_improvement": (
                self._self_improvement_hook.summary()
                if self._self_improvement_hook is not None
                else {}
            ),
            "mmapr_veto_router": (
                self._mmapr_veto_router.summary()
                if self._mmapr_veto_router is not None
                else {}
            ),
        }
