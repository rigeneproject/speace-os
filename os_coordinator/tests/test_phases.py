"""Test delle fasi del coordinatore OS."""

from __future__ import annotations

import pytest

from os_coordinator.phases import ALLOWED_TRANSITIONS, Phase, can_transition


def test_all_phases_have_transitions() -> None:
    for phase in Phase:
        assert phase in ALLOWED_TRANSITIONS


def test_shutdown_is_terminal() -> None:
    assert ALLOWED_TRANSITIONS[Phase.SHUTDOWN] == set()


def test_every_phase_can_reach_shutdown_except_shutdown_itself_obviously() -> None:
    # Ogni fase deve poter portare a SHUTDOWN direttamente o indirettamente.
    for phase in Phase:
        if phase == Phase.SHUTDOWN:
            continue
        # Verifica transizione diretta
        assert can_transition(phase, Phase.SHUTDOWN), f"{phase} non può andare a SHUTDOWN"


def test_boot_to_ignition_to_cognition_to_idle_is_a_valid_path() -> None:
    path = [Phase.BOOT, Phase.IGNITION, Phase.COGNITION, Phase.IDLE]
    for src, dst in zip(path, path[1:]):
        assert can_transition(src, dst), f"transizione invalida: {src} → {dst}"


def test_idle_can_go_to_intervention_and_back() -> None:
    assert can_transition(Phase.IDLE, Phase.INTERVENTION)
    assert can_transition(Phase.INTERVENTION, Phase.IDLE)
