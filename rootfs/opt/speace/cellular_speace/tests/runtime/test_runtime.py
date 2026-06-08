"""Tests for T109 — Controlled Continuous Runtime."""

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List

from speace_core.runtime.checkpoint_manager import CheckpointManager
from speace_core.runtime.circadian_scheduler import CircadianScheduler
from speace_core.runtime.continuous_runtime_engine import ContinuousRuntimeEngine
from speace_core.runtime.emergency_halt_gate import EmergencyHaltGate
from speace_core.runtime.recovery_orchestrator import RecoveryOrchestrator
from speace_core.runtime.runtime_health_monitor import RuntimeHealthMonitor
from speace_core.runtime.safe_degradation_handler import SafeDegradationHandler


# --------------------------------------------------------------------------- #
# Mocks
# --------------------------------------------------------------------------- #

class FakeOrchestrator:
    def __init__(self) -> None:
        self.current_tick = 0
        self.tick_interval = 1.0
        self.execution_mode = "global_tick"
        self.metrics_log: List[Any] = []
        self.sleep_enabled = False
        self.brainstem_controller_enabled = False
        self.global_workspace_enabled = False
        self.temporal_dynamics_enabled = False
        self.neural_oscillator_enabled = False
        self.phase_coupling_enabled = False
        self.energy_field_enabled = False
        self.predictive_coding_enabled = False
        self.active_inference_enabled = False
        self.homeostatic_drive_enabled = False
        self.criticality_monitor_enabled = False
        self.community_detection_enabled = True
        self.evolution_enabled = True
        self._lifecycle_manager = None
        self._brainstem_controller = None

    async def _tick(self) -> None:
        self.current_tick += 1


# --------------------------------------------------------------------------- #
# CheckpointManager
# --------------------------------------------------------------------------- #

def test_checkpoint_save_and_latest(tmp_path):
    mgr = CheckpointManager(checkpoint_dir=str(tmp_path / "cp"))
    orch = FakeOrchestrator()
    cp = mgr.save(orch, runtime_state="running", circadian_phase="awake")
    assert cp["runtime_state"] == "running"
    assert cp["circadian_phase"] == "awake"
    latest = mgr.latest()
    assert latest is not None
    assert latest["orchestrator"]["current_tick"] == 0


def test_checkpoint_trim(tmp_path):
    mgr = CheckpointManager(checkpoint_dir=str(tmp_path / "cp"), max_checkpoints=2)
    orch = FakeOrchestrator()
    mgr.save(orch, runtime_state="running", circadian_phase="awake")
    time.sleep(0.05)
    mgr.save(orch, runtime_state="running", circadian_phase="sleep")
    time.sleep(0.05)
    mgr.save(orch, runtime_state="running", circadian_phase="awake")
    cps = mgr.list_checkpoints(limit=10)
    assert len(cps) == 2


# --------------------------------------------------------------------------- #
# RecoveryOrchestrator
# --------------------------------------------------------------------------- #

def test_recovery_cold_start(tmp_path):
    mgr = CheckpointManager(checkpoint_dir=str(tmp_path / "cp"))
    rec = RecoveryOrchestrator(checkpoint_manager=mgr)
    orch = FakeOrchestrator()
    result = rec.boot(orch)
    assert result["status"] == "cold_start"
    assert result["tick"] == 0


def test_recovery_from_checkpoint(tmp_path):
    mgr = CheckpointManager(checkpoint_dir=str(tmp_path / "cp"))
    orch = FakeOrchestrator()
    orch.current_tick = 42
    mgr.save(orch, runtime_state="running", circadian_phase="awake")
    rec = RecoveryOrchestrator(checkpoint_manager=mgr)
    orch2 = FakeOrchestrator()
    result = rec.boot(orch2)
    assert result["status"] == "recovered"
    assert orch2.current_tick == 42


# --------------------------------------------------------------------------- #
# CircadianScheduler
# --------------------------------------------------------------------------- #

def test_circadian_transitions():
    sched = CircadianScheduler(awake_duration=0.05, sleep_duration=0.05)
    assert sched.phase == "awake"
    sched.tick()
    assert sched.phase == "awake"
    time.sleep(0.06)
    sched.tick()
    assert sched.phase == "pre_sleep"
    # pre_sleep requires 5s; patch phase_entered_at to simulate elapsed time
    sched._phase_entered_at -= 6.0
    sched.tick()
    assert sched.phase == "sleep"
    # sleep requires sleep_duration=0.05s
    time.sleep(0.06)
    sched.tick()
    assert sched.phase == "consolidation"
    # consolidation requires 10s; patch
    sched._phase_entered_at -= 11.0
    sched.tick()
    assert sched.phase == "post_sleep"
    sched._phase_entered_at -= 6.0
    sched.tick()
    assert sched.phase == "awake"


def test_circadian_is_sleeping():
    sched = CircadianScheduler(awake_duration=0.05, sleep_duration=0.05)
    assert not sched.is_sleeping()
    sched._phase = "sleep"
    assert sched.is_sleeping()
    sched._phase = "consolidation"
    assert sched.is_sleeping()


# --------------------------------------------------------------------------- #
# RuntimeHealthMonitor
# --------------------------------------------------------------------------- #

def test_health_perfect():
    mon = RuntimeHealthMonitor()
    mon.record_tick(latency_ms=100)
    assert mon.health_score() == 1.0
    assert not mon.is_degraded()
    assert not mon.is_critical()


def test_health_degraded_by_latency():
    mon = RuntimeHealthMonitor(max_tick_latency_ms=100)
    mon.record_tick(latency_ms=500)
    assert mon.health_score() < 1.0
    assert mon.health_score() < 0.75


def test_health_critical_by_exceptions():
    mon = RuntimeHealthMonitor(
        target_tick_interval=1.0,
        max_tick_jitter_ms=100,
        max_tick_latency_ms=100,
        max_consecutive_exceptions=2,
    )
    # force jitter by setting last tick far in the past
    mon._last_tick_time = time.time() - 3.0
    mon.record_tick(latency_ms=500)
    mon.record_exception()
    mon.record_exception()
    mon.record_exception()
    assert mon.health_score() < 0.3
    assert mon.is_critical()


# --------------------------------------------------------------------------- #
# SafeDegradationHandler
# --------------------------------------------------------------------------- #

def test_degradation_slowdown():
    orch = FakeOrchestrator()
    handler = SafeDegradationHandler()
    actions = handler.evaluate(
        runtime_health={"health_score": 0.5},
        brainstem_state="stable",
        orchestrator=orch,
    )
    assert len(actions) >= 1
    assert actions[0]["action"] == "slowdown"
    assert orch.tick_interval > 1.0


def test_degradation_no_action_when_healthy():
    orch = FakeOrchestrator()
    handler = SafeDegradationHandler()
    actions = handler.evaluate(
        runtime_health={"health_score": 1.0},
        brainstem_state="stable",
        orchestrator=orch,
    )
    assert len(actions) == 0


# --------------------------------------------------------------------------- #
# EmergencyHaltGate
# --------------------------------------------------------------------------- #

def test_halt_not_triggered_when_healthy():
    gate = EmergencyHaltGate()
    orch = FakeOrchestrator()
    reason = gate.evaluate(
        runtime_health={"health_score": 1.0},
        brainstem_state="stable",
        memory_rss_mb=100,
        orchestrator=orch,
        runtime_state="running",
        circadian_phase="awake",
    )
    assert reason is None
    assert not gate.is_halted


def test_halt_triggered_by_health():
    gate = EmergencyHaltGate(health_score_threshold=0.1)
    orch = FakeOrchestrator()
    reason = gate.evaluate(
        runtime_health={"health_score": 0.05},
        brainstem_state="stable",
        memory_rss_mb=100,
        orchestrator=orch,
        runtime_state="running",
        circadian_phase="awake",
    )
    assert reason is not None
    assert gate.is_halted


def test_halt_reset():
    gate = EmergencyHaltGate(health_score_threshold=0.1)
    orch = FakeOrchestrator()
    gate.evaluate(
        runtime_health={"health_score": 0.05},
        brainstem_state="stable",
        memory_rss_mb=100,
        orchestrator=orch,
        runtime_state="running",
        circadian_phase="awake",
    )
    assert gate.is_halted
    gate.reset()
    assert not gate.is_halted


# --------------------------------------------------------------------------- #
# ContinuousRuntimeEngine
# --------------------------------------------------------------------------- #

async def test_engine_start_pause_resume_halt():
    orch = FakeOrchestrator()
    engine = ContinuousRuntimeEngine(
        orchestrator=orch,
        tick_interval=0.05,
        checkpoint_interval_seconds=60.0,
    )
    result = await engine.start()
    assert result["state"] == "running"
    assert engine._state == "running"

    await asyncio.sleep(0.1)
    assert orch.current_tick >= 1

    await engine.pause()
    assert engine._state == "paused"

    ticks = orch.current_tick
    await asyncio.sleep(0.1)
    # paused: no new ticks
    assert orch.current_tick == ticks

    await engine.resume()
    assert engine._state == "running"

    await engine.halt()
    # wait for loop to exit
    for _ in range(50):
        if engine._state == "halted":
            break
        await asyncio.sleep(0.05)
    assert engine._state == "halted"
    await engine.stop()


async def test_engine_force_checkpoint():
    orch = FakeOrchestrator()
    engine = ContinuousRuntimeEngine(
        orchestrator=orch,
        tick_interval=0.05,
        checkpoint_interval_seconds=60.0,
    )
    await engine.start()
    cp = await engine.force_checkpoint()
    assert cp["runtime_state"] == "running"
    await engine.stop()


# --------------------------------------------------------------------------- #
# T111 — Extended Runtime Observer
# --------------------------------------------------------------------------- #

async def test_extended_observer_sampling():
    from speace_core.runtime.extended_runtime_observer import ExtendedRuntimeObserver
    obs = ExtendedRuntimeObserver(history_window_seconds=1.0, report_interval_seconds=0.1)
    orch = FakeOrchestrator()
    obs.sample(memory_rss_mb=100.0, health_score=1.0, tick_latency_ms=50.0, orchestrator=orch)
    import asyncio
    await asyncio.sleep(0.15)
    obs.sample(memory_rss_mb=110.0, health_score=0.9, tick_latency_ms=60.0, orchestrator=orch)
    report = obs.latest_report()
    assert report is not None
    assert "memory_growth_mb" in report
    assert "health_trend" in report


# --------------------------------------------------------------------------- #
# T112 — Circadian Validator
# --------------------------------------------------------------------------- #

def test_circadian_validator_phase_order():
    from speace_core.runtime.circadian_validator import CircadianValidator
    val = CircadianValidator()
    val.record_phase_transition("awake", "pre_sleep")
    val.record_phase_transition("pre_sleep", "sleep")
    val.record_phase_transition("sleep", "consolidation")
    val.record_phase_transition("consolidation", "post_sleep")
    val.record_phase_transition("post_sleep", "awake")
    report = val.validate(FakeOrchestrator())
    assert report["phase_order_valid"] is True
    assert report["is_valid"] is True


def test_circadian_validator_invalid_order():
    from speace_core.runtime.circadian_validator import CircadianValidator
    val = CircadianValidator()
    val.record_phase_transition("awake", "sleep")  # skip
    report = val.validate(FakeOrchestrator())
    assert report["phase_order_valid"] is False


# --------------------------------------------------------------------------- #
# T113 — Memory Leak Auditor
# --------------------------------------------------------------------------- #

def test_memory_leak_auditor_baseline():
    from speace_core.runtime.memory_leak_auditor import MemoryLeakAuditor
    auditor = MemoryLeakAuditor(sample_interval_seconds=0.0)
    orch = FakeOrchestrator()
    report = auditor.sample(orch)
    assert report is not None
    assert "rss_mb" in report
    assert "object_counts" in report
    assert auditor.summary()["baseline_set"] is True


# --------------------------------------------------------------------------- #
# T114 — Degradation Drill
# --------------------------------------------------------------------------- #

async def test_degradation_drill_memory_pressure():
    from speace_core.runtime.degradation_drill import DegradationDrill
    orch = FakeOrchestrator()
    health = RuntimeHealthMonitor()
    handler = SafeDegradationHandler()
    drill = DegradationDrill(orch, health, handler)
    report = await drill.run_drill(scenario="memory_pressure", duration_seconds=0.5)
    assert report["scenario"] == "memory_pressure"
    assert report["passed"] is True
    assert len(report["injected_faults"]) > 0


# --------------------------------------------------------------------------- #
# T117 — Runtime Latent Integration
# --------------------------------------------------------------------------- #

def test_engine_snapshot_includes_latent_integration():
    orch = FakeOrchestrator()
    engine = ContinuousRuntimeEngine(
        orchestrator=orch,
        tick_interval=0.05,
        checkpoint_interval_seconds=60.0,
    )
    snap = engine.snapshot()
    assert "latent_integration" in snap
    assert snap["latent_integration"]["vector_dim"] == 64


# --------------------------------------------------------------------------- #
# T147 — Embodied Sensory Stream Activation
# --------------------------------------------------------------------------- #

async def test_t147_embodiment_activated_in_runtime():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    engine = ContinuousRuntimeEngine(
        orchestrator=orch,
        tick_interval=0.05,
        checkpoint_interval_seconds=60.0,
    )
    result = await engine.start()
    assert result["state"] == "running"
    # T147: embodiment and predictive coding should be initialized
    assert orch.embodiment_enabled is True
    assert orch.predictive_coding_enabled is True
    assert orch._sensor_array is not None
    assert orch._physical_environment is not None
    assert orch._predictive_coding is not None

    await asyncio.sleep(0.15)

    # Narrative engine should have recorded sensory events
    recent = engine.narrative_engine.recent(hours=0.1, limit=50)
    assert isinstance(recent, list)

    await engine.stop()
    assert engine._state == "halted"
    # Sensor thread should have been stopped
    if orch._sensor_array is not None:
        sampling_thread = getattr(orch._sensor_array, "_sampling_thread", None)
        assert sampling_thread is None or not sampling_thread.is_alive()


async def test_t148_micro_actuator_initialized_in_runtime():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    engine = ContinuousRuntimeEngine(
        orchestrator=orch,
        tick_interval=0.05,
        checkpoint_interval_seconds=60.0,
    )
    result = await engine.start()
    assert result["state"] == "running"

    # T148: Phase 3 micro actuator should be initialized
    assert engine._micro_actuator is not None
    assert hasattr(engine._micro_actuator, "propose_action")
    assert hasattr(engine._micro_actuator, "execute_action")
    assert hasattr(engine._micro_actuator, "summary")

    # Narrative engine should have recorded micro actuator initialization
    recent = engine.narrative_engine.recent(hours=0.1, limit=50)
    init_events = [e for e in recent if e.get("event_type") == "micro_actuator_initialized"]
    assert len(init_events) >= 1

    await engine.stop()
    assert engine._state == "halted"


async def test_t149_distributed_organism_initialized_in_runtime():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    engine = ContinuousRuntimeEngine(
        orchestrator=orch,
        tick_interval=0.05,
        checkpoint_interval_seconds=60.0,
    )
    result = await engine.start()
    assert result["state"] == "running"

    # T149: Phase 4 distributed organism should be initialized
    assert engine._distributed_organism is not None
    assert hasattr(engine._distributed_organism, "register_node")
    assert hasattr(engine._distributed_organism, "observe_distributed_state")
    assert hasattr(engine._distributed_organism, "summary")

    # Narrative engine should have recorded distributed organism initialization
    recent = engine.narrative_engine.recent(hours=0.1, limit=50)
    init_events = [e for e in recent if e.get("event_type") == "distributed_organism_initialized"]
    assert len(init_events) >= 1

    await engine.stop()
    assert engine._state == "halted"
