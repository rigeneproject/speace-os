"""Macchina a stati del coordinatore OS."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from os_coordinator.phases import ALLOWED_TRANSITIONS, Phase, can_transition


@dataclass
class StateRecord:
    """Una singola transizione di stato osservata."""

    phase: Phase
    entered_at: datetime
    exited_at: Optional[datetime] = None
    reason: str = ""


class InvalidTransitionError(RuntimeError):
    """Eccezione sollevata quando si tenta una transizione non permessa."""


class StateMachine:
    """Macchina a stati minimale con tracciamento delle transizioni."""

    def __init__(self, initial: Phase = Phase.BOOT) -> None:
        self._current: Phase = initial
        self._history: list[StateRecord] = [StateRecord(phase=initial, entered_at=_now())]

    @property
    def current(self) -> Phase:
        return self._current

    @property
    def history(self) -> list[StateRecord]:
        return list(self._history)

    def in_(self, phase: Phase) -> bool:
        return self._current == phase

    def time_in_current(self) -> float:
        """Secondi trascorsi nella fase attuale."""
        rec = self._history[-1]
        return (_now() - rec.entered_at).total_seconds()

    def transition(self, dst: Phase, reason: str = "") -> None:
        """Transizione deterministica. Fallisce se dst non è raggiungibile da current."""
        if not can_transition(self._current, dst):
            raise InvalidTransitionError(
                f"transizione non permessa: {self._current.value} → {dst.value}"
            )
        now = _now()
        self._history[-1].exited_at = now
        self._history.append(StateRecord(phase=dst, entered_at=now, reason=reason))
        self._current = dst

    def can_reach(self, dst: Phase) -> bool:
        """True se dst è raggiungibile con uno o più passi di transizione.

        Nota: non considera lo stato attuale come già raggiunto: se dst è
        uguale alla fase corrente, serve almeno un'azione. Questo evita che
        BOOT sia "raggiungibile" da BOOT stesso.
        """
        visited: set[Phase] = {self._current}
        stack: list[Phase] = list(ALLOWED_TRANSITIONS.get(self._current, set()))
        while stack:
            cur = stack.pop()
            if cur == dst:
                return True
            visited.add(cur)
            for nxt in ALLOWED_TRANSITIONS.get(cur, set()):
                if nxt not in visited:
                    stack.append(nxt)
        return False

    def snapshot(self) -> dict:
        """Rappresentazione serializzabile dello stato corrente."""
        return {
            "current": self._current.value,
            "time_in_current_sec": self.time_in_current(),
            "transitions": [
                {
                    "phase": r.phase.value,
                    "entered_at": r.entered_at.isoformat(),
                    "exited_at": r.exited_at.isoformat() if r.exited_at else None,
                    "reason": r.reason,
                }
                for r in self._history
            ],
        }


def _now() -> datetime:
    return datetime.now(timezone.utc)
