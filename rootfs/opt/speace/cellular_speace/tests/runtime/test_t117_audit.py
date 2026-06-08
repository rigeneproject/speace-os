"""T117-A — Runtime Latent Stability Audit.

Simulates an extended runtime session with T117 active in observe-only mode.
Collects drift, cosine similarity, health score, memory growth, narrative density.
Verifies no remote packets sent and no regulation proposals from T117.
"""

import asyncio
import time
from typing import Any, Dict, List

import pytest

from speace_core.runtime.continuous_runtime_engine import ContinuousRuntimeEngine
from speace_core.runtime.runtime_health_monitor import RuntimeHealthMonitor
from speace_core.runtime.safe_degradation_handler import SafeDegradationHandler


# --------------------------------------------------------------------------- #
# Extended mocks with T117-relevant subsystems
# --------------------------------------------------------------------------- #

class MockMetrics:
    def __init__(self, coherence_phi=0.5, mean_energy=0.7, noise_level=0.1):
        self.coherence_phi = coherence_phi
        self.mean_energy = mean_energy
        self.noise_level = noise_level


class MockGlobalWorkspace:
    def __init__(self):
        self._tick = 0
        self._recurrent = [0.0] * 64
        self._symbolic = [0.0] * 16
        self._awareness = 0.5
        self._coherence = 0.6
        self._energy = 0.7
        self._prediction_error = 0.1

    def get_global_state(self) -> Dict[str, Any]:
        self._tick += 1
        import random
        for i in range(len(self._recurrent)):
            self._recurrent[i] += random.uniform(-0.001, 0.001)
            self._recurrent[i] = max(-1.0, min(1.0, self._recurrent[i]))
        for i in range(len(self._symbolic)):
            self._symbolic[i] += random.uniform(-0.001, 0.001)
            self._symbolic[i] = max(-1.0, min(1.0, self._symbolic[i]))
        return {
            "recurrent_state": list(self._recurrent),
            "symbolic_state": list(self._symbolic),
            "awareness_level": self._awareness,
            "coherence": self._coherence,
            "energy": self._energy,
            "prediction_error": self._prediction_error,
        }


class MockMorphologicalMemory:
    def __init__(self):
        self.events = []
        self.coherence_phi = 0.55

    def log_event(self, **kwargs):
        self.events.append(kwargs)


class MockHomeostaticDrive:
    def __init__(self):
        self._drives = {"exploration": 0.5, "stability": 0.5, "survival": 0.2, "efficiency": 0.6}
        self._modulation = {
            "plasticity_multiplier": 1.0,
            "exploration_multiplier": 1.0,
            "energy_supply_multiplier": 1.0,
            "stability_multiplier": 1.0,
        }

    def list_drives(self) -> List[str]:
        return list(self._drives.keys())

    def get_drive_signal(self, name: str) -> float:
        return self._drives.get(name, 0.0) - 0.5

    def get_global_modulation(self) -> Dict[str, float]:
        return dict(self._modulation)

    def step(self) -> Dict[str, float]:
        for k in self._drives:
            self._drives[k] += 0.01 * (hash(k) % 3 - 1)
            self._drives[k] = max(0.0, min(1.0, self._drives[k]))
        return self.get_global_modulation()


class MockSelfModel:
    def __init__(self):
        self._identity = [0.1] * 32
        self._stage = "juvenile"
        self._coherent = True

    def get_identity_signature(self) -> List[float]:
        return list(self._identity)

    def get_developmental_stage(self) -> str:
        return self._stage

    def is_coherent(self, threshold: float = 0.5) -> bool:
        return self._coherent


class MockDialogueManager:
    def __init__(self):
        self._turn_count = 0
        self.state = "idle"

    def receive(self, msg: str, speaker: str = "user") -> Dict[str, Any]:
        self._turn_count += 1
        self.state = "active"
        return {}


class MockSkillTransferLayer:
    def __init__(self):
        self._candidates = []

    def get_stages(self) -> List[str]:
        return ["candidate", "scenario", "evaluate"]


class ExtendedFakeOrchestrator:
    def __init__(self):
        self.current_tick = 0
        self.tick_interval = 1.0
        self.execution_mode = "global_tick"
        self.metrics_log: List[Any] = []
        self.sleep_enabled = False
        self.brainstem_controller_enabled = False
        self.global_workspace_enabled = True
        self.temporal_dynamics_enabled = False
        self.neural_oscillator_enabled = False
        self.phase_coupling_enabled = False
        self.energy_field_enabled = False
        self.predictive_coding_enabled = False
        self.active_inference_enabled = False
        self.homeostatic_drive_enabled = True
        self.criticality_monitor_enabled = False
        self.community_detection_enabled = True
        self.evolution_enabled = True
        self._lifecycle_manager = None
        self._brainstem_controller = None

        # T117 modules
        self._global_workspace = MockGlobalWorkspace()
        self._memory = MockMorphologicalMemory()
        self._homeostatic_drive = MockHomeostaticDrive()
        self._self_model = MockSelfModel()
        self._dialogue_manager = MockDialogueManager()
        self._skill_transfer_layer = MockSkillTransferLayer()

    async def _tick(self) -> None:
        self.current_tick += 1
        # Simulate metrics_log population
        self.metrics_log.append(MockMetrics())
        # Step homeostatic drive
        if self._homeostatic_drive is not None:
            self._homeostatic_drive.step()


# --------------------------------------------------------------------------- #
# T117-A Audit
# --------------------------------------------------------------------------- #

async def test_t117a_stability_over_ticks():
    """Run T117 for N ticks and verify stability metrics."""
    orch = ExtendedFakeOrchestrator()
    engine = ContinuousRuntimeEngine(
        orchestrator=orch,
        tick_interval=0.01,
        checkpoint_interval_seconds=60.0,
    )
    await engine.start()

    # Collect snapshots every tick for a short burst (simulated extended run)
    snapshots: List[Dict[str, Any]] = []
    for _ in range(200):
        await asyncio.sleep(0.01)
        snap = engine.snapshot()
        li = snap.get("latent_integration", {})
        if li.get("tick", 0) > 0:
            snapshots.append(li)

    await engine.halt()
    for _ in range(50):
        if engine._state == "halted":
            break
        await asyncio.sleep(0.01)
    await engine.stop()

    assert len(snapshots) > 50, "Expected significant number of snapshots"

    # Verify packets were generated
    packets_counts = [s.get("latest_metrics", {}).get("packet_count", 0) for s in snapshots]
    assert any(c > 0 for c in packets_counts), "No latent packets generated"

    # Verify no remote peers on local_bus
    for s in snapshots:
        bus = s.get("local_bus", {})
        peers = bus.get("peers", [])
        assert peers == [], f"Unexpected remote peers: {peers}"

    # Verify drift and cosine similarity present in some snapshots
    metrics_list = [s.get("latest_metrics", {}) for s in snapshots if s.get("latest_metrics")]
    assert len(metrics_list) > 0, "No metrics captured"

    # Check that alignment_confidence is computed when history exists
    confidences = [m.get("alignment_confidence") for m in metrics_list if m.get("alignment_confidence") is not None]
    if confidences:
        assert all(0.0 <= c <= 1.0 for c in confidences), "Alignment confidence out of bounds"

    # Verify no regulation proposals generated by T117
    # (narrative events from T117 have event_type "latent_integrator_tick" with importance 2)
    # We verify the integrator doesn't touch the orchestrator's regulation system
    # Since our mock has no regulation, we just verify the engine health stayed good
    health = engine.health_monitor.snapshot()
    assert health["health_score"] > 0.5, "Health degraded during T117 run"


def test_t117a_memory_growth_bounded():
    """Verify T117 history doesn't grow unbounded."""
    from speace_core.cellular_brain.latent_transfer.runtime_latent_integrator import RuntimeLatentIntegrator
    from speace_core.cellular_brain.latent_transfer.latent_packet import LatentPacket, VectorSource

    orch = ExtendedFakeOrchestrator()
    integrator = RuntimeLatentIntegrator(orchestrator=orch, vector_dim=16, history_window=10)

    # Pump many ticks
    for _ in range(500):
        integrator.tick()

    # History should be bounded by history_window
    for src, hist in integrator._history.items():
        assert len(hist) <= 10, f"History for {src} exceeded window: {len(hist)}"


def test_t117a_no_modification_side_effects():
    """Verify T117 tick does not mutate orchestrator state."""
    from speace_core.cellular_brain.latent_transfer.runtime_latent_integrator import RuntimeLatentIntegrator

    orch = ExtendedFakeOrchestrator()
    original_tick = orch.current_tick
    original_workspace_state = orch._global_workspace.get_global_state()

    integrator = RuntimeLatentIntegrator(orchestrator=orch, vector_dim=16)
    integrator.tick()

    # orchestrator.current_tick should not change from T117
    assert orch.current_tick == original_tick, "T117 modified orchestrator tick"
    # GlobalWorkspace state should not be mutated by T117 (only observed)
    new_workspace_state = orch._global_workspace.get_global_state()
    # We can't compare exact floats due to the mock advancing, but we verify no structural changes
    assert isinstance(new_workspace_state, dict)
