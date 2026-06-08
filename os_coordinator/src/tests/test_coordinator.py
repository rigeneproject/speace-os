"""Test del coordinatore OS in modalità dry-run."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from os_coordinator.agentic_brain import AgenticBrain, AgenticDecision
from os_coordinator.coordinator import CoordinatorConfig, OSCoordinator
from os_coordinator.phases import Phase
from os_coordinator.service_registry import ServiceRegistry, ServiceState


@pytest.fixture
def coordinator() -> OSCoordinator:
    cfg = CoordinatorConfig(
        config_path=Path("/nonexistent.yaml"),
        dry_run=True,
        offline=True,
        cognition_tick_sec=0.0,
        idle_tick_sec=0.0,
        ai_consult_every_n_ticks=1,
    )
    brain = AgenticBrain(offline=True)
    registry = ServiceRegistry()
    return OSCoordinator(config=cfg, brain=brain, registry=registry)


def test_status_contains_phase(coordinator: OSCoordinator) -> None:
    s = coordinator.status()
    assert s["phase"] == Phase.BOOT.value
    assert s["dry_run"] is True
    assert s["decisions_count"] == 0
    assert "registry" in s


def test_dry_run_execute_marks_running(coordinator: OSCoordinator) -> None:
    asyncio.run(coordinator._dispatch("speace-brain", "start"))
    rec = coordinator.registry.get("speace-brain")
    assert rec.state == ServiceState.RUNNING


def test_dry_run_stop_marks_stopped(coordinator: OSCoordinator) -> None:
    asyncio.run(coordinator._dispatch("speace-brain", "start"))
    asyncio.run(coordinator._dispatch("speace-brain", "stop"))
    rec = coordinator.registry.get("speace-brain")
    assert rec.state == ServiceState.STOPPED


def test_execute_decision_only_accepts_known_services(coordinator: OSCoordinator) -> None:
    decision = AgenticDecision(
        phase_decision="INTERVENE",
        actions=[{"service": "non-existent-service", "op": "start"}],
        reasoning="test",
        urgency="low",
    )
    asyncio.run(coordinator._execute_decision(decision))
    # Nessun errore, ma il servizio non è stato registrato come running
    assert coordinator.registry.get("non-existent-service") is None


def test_execute_decision_starts_brain(coordinator: OSCoordinator) -> None:
    decision = AgenticDecision(
        phase_decision="START_SERVICES",
        actions=[
            {"service": "speace-brain", "op": "start"},
            {"service": "speace-dashboard", "op": "start"},
        ],
        reasoning="avvio normale",
        urgency="low",
    )
    asyncio.run(coordinator._execute_decision(decision))
    assert coordinator.registry.get("speace-brain").state == ServiceState.RUNNING
    assert coordinator.registry.get("speace-dashboard").state == ServiceState.RUNNING


def test_full_dry_run_to_idle(coordinator: OSCoordinator) -> None:
    """Pipeline BOOT → IGNITION → COGNITION → IDLE in dry-run."""
    async def scenario() -> None:
        await coordinator._phase_boot()
        assert coordinator.state.current == Phase.IGNITION
        await coordinator._phase_ignition()
        assert coordinator.state.current == Phase.COGNITION
        await coordinator._phase_cognition()
        assert coordinator.state.current == Phase.IDLE
    asyncio.run(scenario())
    s = coordinator.status()
    assert s["phase"] == Phase.IDLE.value
    assert s["decisions_count"] == 1  # phase_cognition ha chiamato brain.decide


def test_shutdown_terminates_run(coordinator: OSCoordinator) -> None:
    coordinator.shutdown()
    assert coordinator.state.current == Phase.SHUTDOWN


def test_agentic_decision_parses_plain_json() -> None:
    raw = json.dumps({
        "phase_decision": "IDLE",
        "actions": [],
        "reasoning": "tutto ok",
        "urgency": "low",
    })
    d = AgenticDecision.from_json(raw)
    assert d.phase_decision == "IDLE"
    assert d.reasoning == "tutto ok"
    assert d.urgency == "low"


def test_agentic_decision_handles_code_block() -> None:
    raw = "```json\n" + json.dumps({
        "phase_decision": "INTERVENE",
        "actions": [{"service": "speace-brain", "op": "restart"}],
        "reasoning": "phi basso",
        "urgency": "high",
    }) + "\n```"
    d = AgenticDecision.from_json(raw)
    assert d.phase_decision == "INTERVENE"
    assert d.urgency == "high"
    assert len(d.actions) == 1


def test_agentic_decision_handles_garbage() -> None:
    d = AgenticDecision.from_json("non sono json valido")
    assert d.phase_decision == "IDLE"
    assert "non parsabile" in d.reasoning
