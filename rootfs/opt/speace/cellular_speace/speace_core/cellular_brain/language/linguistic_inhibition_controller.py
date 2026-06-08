"""LinguisticInhibitionController — symbolic-level inhibition for linguistic production.

Prevents ecolalia (immediate token repetition), perseveration (excessive
repetition of the same token), and production loops (repeating cycles of tokens)
by tracking production history and maintaining token-level refractory periods.

Optionally integrates with NeuralOscillatorBank to modulate inhibition parameters
based on oscillatory dynamics (e.g., theta/gamma band state).
"""

from __future__ import annotations

from collections import Counter, deque
from typing import Any, Dict, List, Optional


class LinguisticInhibitionController:
    """Symbolic-level inhibition for linguistic production.

    Tracks token production frequency and maintains refractory periods for
    recently produced tokens to prevent pathological repetition patterns.
    """

    def __init__(
        self,
        token_refractory_ticks: int = 8,
        loop_detection_window: int = 24,
        max_token_repeat: int = 2,
        max_loop_cycles: int = 2,
        perseveration_threshold: int = 4,
        oscillator_bank: Any = None,
    ):
        self.token_refractory_ticks = token_refractory_ticks
        self.loop_detection_window = loop_detection_window
        self.max_token_repeat = max_token_repeat
        self.max_loop_cycles = max_loop_cycles
        self.perseveration_threshold = perseveration_threshold
        self._oscillator_bank = oscillator_bank

        self._production_history: List[str] = []
        self._token_refractory_end: Dict[str, int] = {}
        self._token_count: Counter = Counter()
        self._tick: int = 0
        self._inhibited: bool = False
        self._inhibition_reason: Optional[str] = None
        self._inhibition_history: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def record_production(self, token: str) -> Dict[str, Any]:
        """Record a token production and check inhibition status.

        Returns a dict with inhibition checks:
        - ``inhibited``: whether production should be suppressed
        - ``reason``: why inhibition was triggered (or None)
        - ``repeat_count``: how many times this token has been produced
        - ``refractory_remaining``: ticks until token is available again
        """
        self._tick += 1

        inhibition = self._check_inhibition(token)

        self._production_history.append(token)
        self._token_count[token] = self._token_count.get(token, 0) + 1

        self._token_refractory_end[token] = self._tick + self._get_refractory_ticks()

        self._prune_history()

        if inhibition["inhibited"]:
            self._inhibited = True
            self._inhibition_reason = inhibition["reason"]
            self._inhibition_history.append({
                "tick": self._tick,
                "token": token,
                "reason": inhibition["reason"],
                "repeat_count": inhibition["repeat_count"],
                "refractory_remaining": inhibition["refractory_remaining"],
            })
        else:
            self._inhibited = False
            self._inhibition_reason = None

        return inhibition

    def is_token_inhibited(self, token: str) -> bool:
        """Check if a specific token is in its refractory period."""
        end = self._token_refractory_end.get(token, 0)
        return self._tick < end

    def is_production_inhibited(self) -> bool:
        """Check if production is globally inhibited (loop/perseveration)."""
        return self._inhibited

    def inhibition_status(self) -> Dict[str, Any]:
        """Return current inhibition state snapshot."""
        return {
            "inhibited": self._inhibited,
            "reason": self._inhibition_reason,
            "tick": self._tick,
            "production_count": len(self._production_history),
            "unique_tokens": len(self._token_count),
            "token_frequencies": dict(self._token_count.most_common(10)),
            "history_window": list(self._production_history[-self.loop_detection_window:]),
        }

    def reset(self) -> None:
        """Clear all inhibition state."""
        self._production_history.clear()
        self._token_refractory_end.clear()
        self._token_count.clear()
        self._tick = 0
        self._inhibited = False
        self._inhibition_reason = None

    # ------------------------------------------------------------------ #
    # Internal checks
    # ------------------------------------------------------------------ #

    def _check_inhibition(self, token: str) -> Dict[str, Any]:
        """Run all inhibition checks for the given token."""
        repeat_count = self._token_count[token]

        refract_remaining = self._token_refractory_end.get(token, 0) - self._tick

        if refract_remaining > 0:
            # Token is in its refractory period → ecolalia prevention
            return {
                "inhibited": True,
                "reason": "ecolalia",
                "repeat_count": repeat_count,
                "refractory_remaining": refract_remaining,
            }

        if repeat_count > self.max_token_repeat and self._is_perseverating(token):
            return {
                "inhibited": True,
                "reason": "perseveration",
                "repeat_count": repeat_count,
                "refractory_remaining": 0,
            }

        if self._detect_loop():
            return {
                "inhibited": True,
                "reason": "production_loop",
                "repeat_count": repeat_count,
                "refractory_remaining": 0,
            }

        return {
            "inhibited": False,
            "reason": None,
            "repeat_count": repeat_count,
            "refractory_remaining": 0,
        }

    def _is_perseverating(self, token: str) -> bool:
        """Check if the same token dominates recent production."""
        if len(self._production_history) < self.perseveration_threshold:
            return False
        recent = self._production_history[-self.perseveration_threshold:]
        return sum(1 for t in recent if t == token) >= self.perseveration_threshold - 1

    def _detect_loop(self) -> bool:
        """Detect repeating cycles in the production history.

        Uses autocorrelation-like matching: checks if the tail of the
        production history matches a prefix of itself at various periodicities.
        """
        if len(self._production_history) < self.loop_detection_window:
            return False

        window = self._production_history[-self.loop_detection_window:]
        n = len(window)

        for period in range(2, n // 2 + 1):
            match = True
            for i in range(n - period):
                if window[i] != window[i + period]:
                    match = False
                    break
            if match:
                cycles = n // period
                if cycles >= self.max_loop_cycles:
                    return True

        return False

        return False

    def _prune_history(self) -> None:
        """Keep only the most recent production history entries."""
        max_len = max(self.loop_detection_window * 2, 100)
        while len(self._production_history) > max_len:
            oldest = self._production_history.pop(0)
            self._token_count[oldest] -= 1
            if self._token_count[oldest] <= 0:
                del self._token_count[oldest]

    def _get_refractory_ticks(self) -> int:
        """Get the current refractory period, optionally modulated by oscillators."""
        if self._oscillator_bank is not None:
            try:
                modulation = self._oscillator_bank.get_neural_modulation()
                if modulation is not None:
                    gamma = modulation.get("gamma", 0.0)
                    theta = modulation.get("theta", 0.0)
                    # Gamma ↑ → faster production (shorter refractory)
                    # Theta ↑ → slower, more deliberate (longer refractory)
                    base = float(self.token_refractory_ticks)
                    modulated = base * (1.0 - 0.3 * gamma + 0.3 * theta)
                    return max(1, int(round(modulated)))
            except Exception:
                pass
        return self.token_refractory_ticks
