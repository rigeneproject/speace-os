"""Test della state machine del coordinatore OS."""

from __future__ import annotations

import pytest

from os_coordinator.phases import Phase, can_transition
from os_coordinator.state_machine import InvalidTransitionError, StateMachine


def test_initial_phase() -> None:
    sm = StateMachine()
    assert sm.current == Phase.BOOT
    assert len(sm.history) == 1


def test_valid_transition_boot_to_ignition() -> None:
    sm = StateMachine()
    sm.transition(Phase.IGNITION, reason="ok")
    assert sm.current == Phase.IGNITION
    assert sm.history[-1].reason == "ok"
    assert sm.history[-2].exited_at is not None


def test_valid_transition_cognition_to_idle() -> None:
    sm = StateMachine()
    sm.transition(Phase.IGNITION)
    sm.transition(Phase.COGNITION)
    sm.transition(Phase.IDLE)
    assert sm.current == Phase.IDLE


def test_invalid_transition_boot_to_idle() -> None:
    sm = StateMachine()
    with pytest.raises(InvalidTransitionError):
        sm.transition(Phase.IDLE)


def test_cannot_transition_from_shutdown() -> None:
    sm = StateMachine()
    sm.transition(Phase.IGNITION)
    sm.transition(Phase.COGNITION)
    sm.transition(Phase.SHUTDOWN)
    assert sm.current == Phase.SHUTDOWN
    with pytest.raises(InvalidTransitionError):
        sm.transition(Phase.IDLE)
    with pytest.raises(InvalidTransitionError):
        sm.transition(Phase.BOOT)


def test_can_reach_shutdown_from_boot() -> None:
    sm = StateMachine()
    assert sm.can_reach(Phase.SHUTDOWN) is True


def test_cannot_reach_boot_again() -> None:
    sm = StateMachine()
    # BOOT non è raggiungibile dopo essere partiti da BOOT, perché la macchina
    # non permette di tornare indietro. È uno stato iniziale.
    assert sm.can_reach(Phase.BOOT) is False


def test_in_helper() -> None:
    sm = StateMachine()
    assert sm.in_(Phase.BOOT) is True
    assert sm.in_(Phase.IDLE) is False


def test_snapshot() -> None:
    sm = StateMachine()
    sm.transition(Phase.IGNITION, reason="ready")
    snap = sm.snapshot()
    assert snap["current"] == "IGNITION"
    assert isinstance(snap["transitions"], list)
    assert len(snap["transitions"]) == 2
    assert snap["transitions"][0]["exited_at"] is not None


def test_can_transition_helper() -> None:
    assert can_transition(Phase.BOOT, Phase.IGNITION) is True
    assert can_transition(Phase.BOOT, Phase.IDLE) is False
    assert can_transition(Phase.SHUTDOWN, Phase.BOOT) is False
