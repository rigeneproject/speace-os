from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SequenceToken(BaseModel):
    """A single token in a production sequence with activation metadata."""

    symbol: str
    activation: float = 0.0
    produced: bool = False


class DigitalBrocaArea:
    """Language production area modelled after Broca's area.

    Uses a central-pattern-generator-like mechanism to sequentially
    activate symbolic tokens (words, phonemes, or abstract tokens).
    """

    def __init__(
        self,
        cpg_period: int = 3,
        decay_rate: float = 0.1,
        min_activation: float = 0.2,
    ):
        self.cpg_period = cpg_period
        self.decay_rate = decay_rate
        self.min_activation = min_activation
        self._sequence: List[SequenceToken] = []
        self._current_index: int = 0
        self._tick_counter: int = 0
        self._paused: bool = False

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def activate_sequence(self, sequence: List[str]) -> None:
        """Load a new symbolic sequence for production."""
        self._sequence = [
            SequenceToken(symbol=sym, activation=0.0, produced=False)
            for sym in sequence
        ]
        self._current_index = 0
        self._tick_counter = 0
        self._paused = False

    def next_token(self) -> Optional[str]:
        """Advance the CPG and return the next token if ready.

        The central pattern generator paces production: every ``cpg_period``
        ticks the current token's activation is incremented. Once activation
        crosses ``min_activation`` the token is emitted and the index moves
        forward.
        """
        if not self._sequence or self._current_index >= len(self._sequence):
            return None
        if self._paused:
            return None

        self._tick_counter += 1

        # CPG rhythm: only boost activation on CPG beats
        if self._tick_counter % self.cpg_period == 0:
            token = self._sequence[self._current_index]
            token.activation = min(1.0, token.activation + 0.5)

            if token.activation >= self.min_activation:
                token.produced = True
                emitted = token.symbol
                self._current_index += 1
                return emitted

        return None

    def reset_sequence(self) -> None:
        """Reset the production state without clearing the sequence."""
        self._current_index = 0
        self._tick_counter = 0
        for token in self._sequence:
            token.activation = 0.0
            token.produced = False

    def pause(self) -> None:
        """Pause production (e.g. for error correction or inhibition)."""
        self._paused = True

    def resume(self) -> None:
        """Resume production."""
        self._paused = False

    @property
    def sequence(self) -> List[str]:
        """Return the loaded symbols in order."""
        return [t.symbol for t in self._sequence]

    @property
    def remaining(self) -> List[str]:
        """Return symbols not yet produced."""
        return [
            t.symbol
            for t in self._sequence[self._current_index :]
            if not t.produced
        ]

    @property
    def is_active(self) -> bool:
        """True if there are still tokens left to produce."""
        return self._current_index < len(self._sequence) and not self._paused

    def get_production_state(self) -> Dict[str, Any]:
        """Diagnostic snapshot of the production pipeline."""
        return {
            "tick_counter": self._tick_counter,
            "current_index": self._current_index,
            "paused": self._paused,
            "tokens": [
                {
                    "symbol": t.symbol,
                    "activation": t.activation,
                    "produced": t.produced,
                }
                for t in self._sequence
            ],
        }
