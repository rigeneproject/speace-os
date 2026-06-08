import pytest

from speace_core.orchestrator import CellularBrainOrchestrator
from speace_core.dna.models import SharedGenome


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _make_orch(t42_enabled: bool = True):
    genome = SharedGenome(genome_id="test", version="1")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    if t42_enabled:
        orch.cellular_adaptive_defense_enabled = True
        orch.cellular_repair_enabled = True
        orch.cellular_epigenetics_enabled = True
        # Re-run post-init to spin up T42 engines
        orch.model_post_init(None)
    return orch


# ------------------------------------------------------------------ #
# Orchestrator integration
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_t42_tick_runs_when_disabled():
    orch = _make_orch(t42_enabled=False)
    await orch.run_ticks(3)
    assert orch.current_tick == 3


@pytest.mark.asyncio
async def test_t42_tick_runs_when_enabled():
    orch = _make_orch(t42_enabled=True)
    await orch.run_ticks(3)
    assert orch.current_tick == 3


@pytest.mark.asyncio
async def test_t42_stress_result_populated():
    orch = _make_orch(t42_enabled=True)
    await orch.run_ticks(1)
    assert orch._last_cellular_stress_result is not None


@pytest.mark.asyncio
async def test_t42_damage_result_populated():
    orch = _make_orch(t42_enabled=True)
    await orch.run_ticks(1)
    assert orch._last_cellular_damage_result is not None


@pytest.mark.asyncio
async def test_t42_defense_result_populated():
    orch = _make_orch(t42_enabled=True)
    await orch.run_ticks(1)
    assert orch._last_cellular_defense_result is not None


@pytest.mark.asyncio
async def test_t42_repair_result_populated():
    orch = _make_orch(t42_enabled=True)
    await orch.run_ticks(1)
    assert orch._last_cellular_repair_result is not None


@pytest.mark.asyncio
async def test_t42_epigenetic_result_populated():
    orch = _make_orch(t42_enabled=True)
    await orch.run_ticks(1)
    assert orch._last_cellular_epigenetic_result is not None


@pytest.mark.asyncio
async def test_t42_defense_reduces_targets_on_high_stress():
    orch = _make_orch(t42_enabled=True)
    # Pre-seed a stressed neuron with targets
    stressed = orch.circuit.hidden_neurons[0]
    stressed.energy = 0.1
    stressed.activation = 2.0
    stressed.consecutive_fires = 5
    stressed.apoptosis_risk = 0.9
    stressed.targets = ["t1", "t2"]
    # Raise newer defense thresholds so quarantine or firewall (which clear targets) can trigger
    defense = orch._cellular_defense_engine
    defense.plasticity_lock_stress_threshold = 1.0
    defense.routing_block_stress_threshold = 1.0
    defense.input_filter_stress_threshold = 1.0
    defense.immune_alert_damage_threshold = 1.0
    await orch.run_ticks(1)
    # Defense may have quarantined or firewalled
    assert len(stressed.targets) == 0


@pytest.mark.asyncio
async def test_t42_repair_does_not_crash():
    orch = _make_orch(t42_enabled=True)
    await orch.run_ticks(5)
    assert orch.current_tick == 5
