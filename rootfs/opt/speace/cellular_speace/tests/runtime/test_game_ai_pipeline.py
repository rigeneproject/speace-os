"""Tests for T169 — Game AI Integration Pipeline."""

import pytest

from speace_core.cellular_brain.cognition.bt_runtime_integration import BTRuntimeIntegration
from speace_core.cellular_brain.cognition.goap_runtime_integration import GOAPRuntimeIntegration
from speace_core.cellular_brain.cognition.organism_state_machine import OrganismStateMachine
from speace_core.cellular_brain.regulation.utility_arbitration_engine import UtilityArbitrationEngine
from speace_core.cellular_brain.regulation.utility_drive_system import UtilityDriveSystem
from speace_core.cellular_brain.runtime.coordinators.game_ai_integration_coordinator import (
    GameAIIntegrationCoordinator,
)


class TestGameAIIntegrationCoordinator:
    def _make_coordinator(self) -> GameAIIntegrationCoordinator:
        fsm = OrganismStateMachine()
        ds = UtilityDriveSystem()
        arb = UtilityArbitrationEngine(drive_system=ds)
        bt = BTRuntimeIntegration()
        goap = GOAPRuntimeIntegration()
        return GameAIIntegrationCoordinator(
            organism_state_machine=fsm,
            utility_drive_system=ds,
            utility_arbitration=arb,
            bt_integration=bt,
            goap_integration=goap,
        )

    def test_tick_runs_pipeline(self) -> None:
        coord = self._make_coordinator()
        proposals = coord.tick(
            health_score=0.6,
            cognitive_load=0.3,
            prediction_error=0.2,
            energy=0.8,
            curiosity_score=0.7,
            circadian_phase="day",
        )
        assert isinstance(proposals, list)

    def test_overloaded_skips_bt(self) -> None:
        coord = self._make_coordinator()
        # Force overloaded by setting extreme load for 4 ticks (min_dwell=3)
        for _ in range(4):
            coord.tick(
                health_score=0.3,
                cognitive_load=0.95,
                prediction_error=0.9,
                energy=0.2,
                curiosity_score=0.0,
                circadian_phase="day",
            )
        # FSM should transition to overloaded
        assert coord.fsm.current_state() == "overloaded"
        # Next tick should skip BT
        proposals = coord.tick(
            health_score=0.3,
            cognitive_load=0.95,
            prediction_error=0.9,
            energy=0.2,
            curiosity_score=0.0,
            circadian_phase="day",
        )
        # BT layer should produce no proposals in overloaded state
        assert not any(p.get("source_layer") == "behavior_tree" for p in proposals)

    def test_degraded_mode_when_latency_high(self) -> None:
        coord = self._make_coordinator()
        coord._max_pipeline_ms = 0.001
        proposals = coord.tick(
            health_score=0.6,
            cognitive_load=0.3,
            prediction_error=0.2,
            energy=0.8,
            curiosity_score=0.7,
            circadian_phase="day",
        )
        assert coord._degraded_mode is True
        # In degraded mode, BT and GOAP should be skipped
        assert not any(p.get("source_layer") == "behavior_tree" for p in proposals)

    def test_snapshot(self) -> None:
        coord = self._make_coordinator()
        coord.tick(
            health_score=0.6,
            cognitive_load=0.3,
            prediction_error=0.2,
            energy=0.8,
            curiosity_score=0.7,
            circadian_phase="day",
        )
        snap = coord.snapshot()
        assert "tick_count" in snap
        assert "last_latencies_ms" in snap
        assert "layers" in snap
        assert snap["tick_count"] == 1

    def test_proposals_tagged_with_tick(self) -> None:
        coord = self._make_coordinator()
        proposals = coord.tick(
            health_score=0.6,
            cognitive_load=0.3,
            prediction_error=0.2,
            energy=0.8,
            curiosity_score=0.7,
            circadian_phase="day",
        )
        for p in proposals:
            assert "tick" in p
            assert "organism_state" in p
