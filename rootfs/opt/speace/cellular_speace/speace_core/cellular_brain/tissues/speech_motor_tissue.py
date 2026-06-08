from typing import List, Optional

from pydantic import BaseModel, Field


class ArticulationEvent(BaseModel):
    """A single articulation event produced by the motor tissue."""

    token: str
    energy_cost: float = 0.0
    jitter: float = 0.0
    timestamp: float = 0.0


class SpeechMotorTissue:
    """Motor execution layer for language production.

    Receives tokens from Broca-like planning areas and buffers them into
    a motor output stream, modelling the articulatory execution stage.
    """

    def __init__(
        self,
        energy_budget: float = 1.0,
        articulation_cost: float = 0.05,
        jitter_sigma: float = 0.01,
    ):
        self.energy_budget = energy_budget
        self.articulation_cost = articulation_cost
        self.jitter_sigma = jitter_sigma
        self._output_buffer: List[ArticulationEvent] = []
        self._tick_counter: int = 0

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def articulate(self, token: str) -> Optional[ArticulationEvent]:
        """Execute motor articulation for a single token.

        Returns an ``ArticulationEvent`` if sufficient energy is available,
        otherwise returns ``None`` to signal motor fatigue.
        """
        if self.energy_budget < self.articulation_cost:
            return None

        self.energy_budget -= self.articulation_cost
        self._tick_counter += 1

        # Simple jitter model: longer tokens cost slightly more
        jitter = self.jitter_sigma * len(token)
        event = ArticulationEvent(
            token=token,
            energy_cost=self.articulation_cost + jitter,
            jitter=jitter,
            timestamp=float(self._tick_counter),
        )
        self._output_buffer.append(event)
        return event

    def get_output_buffer(self) -> List[ArticulationEvent]:
        """Return the full articulation output buffer."""
        return list(self._output_buffer)

    def clear_buffer(self) -> None:
        """Empty the output buffer without resetting energy."""
        self._output_buffer = []

    def reset(self) -> None:
        """Reset both buffer and energy budget."""
        self._output_buffer = []
        self.energy_budget = 1.0
        self._tick_counter = 0

    def recover_energy(self, amount: float = 0.1) -> None:
        """Replenish motor energy (e.g. during rest ticks)."""
        self.energy_budget = min(1.0, self.energy_budget + amount)

    @property
    def is_fatigued(self) -> bool:
        """True when energy is too low for further articulation."""
        return self.energy_budget < self.articulation_cost

    @property
    def buffer_tokens(self) -> List[str]:
        """Convenience accessor for raw token strings in the buffer."""
        return [e.token for e in self._output_buffer]
