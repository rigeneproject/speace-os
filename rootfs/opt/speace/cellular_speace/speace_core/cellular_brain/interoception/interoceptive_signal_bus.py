"""T-ISB — Interoceptive Signal Bus.

Aggregates *internal bodily* signals (energy, stress, damage, fatigue,
cellular damage, immune load) into a single, normalised, continuous
state vector that downstream consumers — the global workspace, the
self-model, the active inference engine — can subscribe to.

Why this exists
---------------
Biological interoception is what allows the brain to continuously
"feel" its own metabolic state. Without it, higher cognition is
starved of one of the most important feedback channels.

The bus is read-only with respect to its sources: it normalises
whatever values they expose and produces:

* ``signals``     — per-channel normalised values in [0, 1]
* ``vector``      — a flat list ready to feed into the workspace
* ``salience``    — a scalar summarising "how alarming" the body feels
* ``as_dict()``   — JSON-serialisable snapshot for audit and tests

All thresholds default to safe values. Sources are optional: any
source that is ``None`` is skipped silently.
"""
from __future__ import annotations

import json
import logging
import math
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_logger = logging.getLogger(__name__)


# Default interoceptive channels. Each maps a *raw* numeric signal into
# a normalised salience in [0, 1]. Lower = healthier for the
# ``energy_field`` and ``metabolic`` channels; higher = more alarming
# for the ``stress``/``damage``/``immune`` channels.
DEFAULT_CHANNELS = (
    "energy_field",
    "metabolic",
    "cellular_stress",
    "cellular_damage",
    "immune_load",
    "fatigue_fraction",
    "prediction_error",
    "homeostatic_drift",
)


@dataclass
class InteroceptiveSnapshot:
    """Single interoceptive reading."""

    tick: int
    wall_time: float
    signals: Dict[str, float] = field(default_factory=dict)
    salience: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tick": self.tick,
            "wall_time": self.wall_time,
            "signals": dict(self.signals),
            "salience": float(self.salience),
        }


class InteroceptiveSignalBus:
    """Collect, normalise and publish internal-state signals."""

    def __init__(
        self,
        channels: Optional[List[str]] = None,
        # Healthy / alarm ranges for each channel. Lower-is-better channels
        # are normalised as (alarm - value) / (alarm - healthy).
        # Higher-is-better channels are normalised as (value - alarm) / (healthy - alarm).
        channel_polarity: Optional[Dict[str, str]] = None,
        channel_ranges: Optional[Dict[str, tuple]] = None,
    ):
        self.channels: List[str] = list(channels or list(DEFAULT_CHANNELS))
        # "lower_better" (default for stress/damage/immune/error) or
        # "higher_better" (energy, metabolic).
        self.channel_polarity: Dict[str, str] = dict(
            channel_polarity
            or {
                "energy_field": "higher_better",
                "metabolic": "higher_better",
                "cellular_stress": "lower_better",
                "cellular_damage": "lower_better",
                "immune_load": "lower_better",
                "fatigue_fraction": "lower_better",
                "prediction_error": "lower_better",
                "homeostatic_drift": "lower_better",
            }
        )
        # (healthy, alarm). If None we fall back to sensible defaults.
        self.channel_ranges: Dict[str, tuple] = dict(
            channel_ranges
            or {
                "energy_field": (1.0, 0.05),
                "metabolic": (1.0, 0.1),
                "cellular_stress": (0.0, 1.0),
                "cellular_damage": (0.0, 1.0),
                "immune_load": (0.0, 1.0),
                "fatigue_fraction": (0.0, 0.7),
                "prediction_error": (0.0, 1.0),
                "homeostatic_drift": (0.0, 1.0),
            }
        )
        self._tick: int = 0
        self._snapshot: InteroceptiveSnapshot = InteroceptiveSnapshot(
            tick=0, wall_time=time.time()
        )
        self._history: List[InteroceptiveSnapshot] = []
        self._max_history: int = 1024

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def read(
        self,
        energy_field: Any = None,
        metabolic_state: Any = None,
        cellular_stress: Any = None,
        cellular_damage: Any = None,
        immune_controller: Any = None,
        fatigue_count: int = 0,
        neuron_count: int = 0,
        prediction_error: float = 0.0,
        homeostatic_drift: float = 0.0,
    ) -> InteroceptiveSnapshot:
        """Sample all available sources and produce a snapshot.

        Any source may be ``None``; the corresponding channel will be
        left at the default (healthy) value of 0.0 salience.
        """
        signals: Dict[str, float] = {}

        # Energy field
        signals["energy_field"] = self._normalise(
            "energy_field",
            _safe_call(energy_field, "get_global_energy", default=1.0),
        )
        # Metabolic
        if metabolic_state is None:
            metabolic_val = 1.0
        elif isinstance(metabolic_state, dict):
            metabolic_val = float(
                metabolic_state.get("global_energy_reserve", 1.0)
            )
        else:
            metabolic_val = _safe_call(metabolic_state, "model_dump", default=None)
            if not isinstance(metabolic_val, dict):
                metabolic_val = 1.0
            else:
                metabolic_val = float(metabolic_val.get("global_energy_reserve", 1.0))
        signals["metabolic"] = self._normalise("metabolic", metabolic_val)

        # Cellular stress
        stress_val = 0.0
        if cellular_stress is not None:
            stress_val = _safe_call(cellular_stress, "evaluate", default=None)
            if hasattr(stress_val, "per_cell"):
                cells = stress_val.per_cell or {}
                if cells:
                    stress_val = float(sum(cells.values()) / len(cells))
                else:
                    stress_val = 0.0
            elif stress_val is None:
                stress_val = 0.0
            else:
                try:
                    stress_val = float(stress_val)
                except (TypeError, ValueError):
                    stress_val = 0.0
        signals["cellular_stress"] = self._normalise("cellular_stress", stress_val)

        # Cellular damage
        damage_val = 0.0
        if cellular_damage is not None:
            damage_val = _safe_call(cellular_damage, "evaluate", default=None)
            if hasattr(damage_val, "per_cell"):
                cells = damage_val.per_cell or {}
                if cells:
                    damage_val = float(sum(cells.values()) / len(cells))
                else:
                    damage_val = 0.0
            elif damage_val is None:
                damage_val = 0.0
            else:
                try:
                    damage_val = float(damage_val)
                except (TypeError, ValueError):
                    damage_val = 0.0
        signals["cellular_damage"] = self._normalise("cellular_damage", damage_val)

        # Immune load
        immune_val = 0.0
        if immune_controller is not None:
            try:
                if hasattr(immune_controller, "get_load"):
                    immune_val = float(immune_controller.get_load())
            except Exception:
                immune_val = 0.0
        signals["immune_load"] = self._normalise("immune_load", immune_val)

        # Fatigue fraction
        fatigue_frac = 0.0
        if neuron_count > 0:
            fatigue_frac = max(0.0, min(1.0, fatigue_count / neuron_count))
        signals["fatigue_fraction"] = self._normalise(
            "fatigue_fraction", fatigue_frac
        )

        # Prediction error (already a salience in [0, 1] in our pipeline).
        signals["prediction_error"] = self._normalise(
            "prediction_error", max(0.0, min(1.0, float(prediction_error)))
        )
        # Homeostatic drift: scalar in [0, 1].
        signals["homeostatic_drift"] = self._normalise(
            "homeostatic_drift", max(0.0, min(1.0, float(homeostatic_drift)))
        )

        self._tick += 1
        salience = self._salience(signals)
        snap = InteroceptiveSnapshot(
            tick=self._tick,
            wall_time=time.time(),
            signals=signals,
            salience=salience,
        )
        self._snapshot = snap
        self._history.append(snap)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history // 2 :]
        return snap

    def vector(self, snapshot: Optional[InteroceptiveSnapshot] = None) -> List[float]:
        """Return a flat list of channel values for workspace input."""
        snap = snapshot or self._snapshot
        return [float(snap.signals.get(c, 0.0)) for c in self.channels]

    def salience(self, snapshot: Optional[InteroceptiveSnapshot] = None) -> float:
        return float((snapshot or self._snapshot).salience)

    def broadcast_to_workspace(
        self, workspace: Any, target_dim: int = 64
    ) -> None:
        """Queue the interoceptive state in *workspace* (if it has broadcast)."""
        if workspace is None or not hasattr(workspace, "broadcast"):
            return
        vec = self.vector()
        if len(vec) < target_dim:
            vec = vec + [0.0] * (target_dim - len(vec))
        else:
            vec = vec[:target_dim]
        try:
            workspace.broadcast("interoception", vec)
        except Exception as exc:  # pragma: no cover
            _logger.debug("Interoceptive broadcast failed: %s", exc)

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def save_history(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump([s.to_dict() for s in self._history], fh, indent=2)

    @property
    def last_snapshot(self) -> InteroceptiveSnapshot:
        return self._snapshot

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _normalise(self, channel: str, value: float) -> float:
        if channel not in self.channel_ranges:
            return max(0.0, min(1.0, float(value)))
        healthy, alarm = self.channel_ranges[channel]
        polarity = self.channel_polarity.get(channel, "lower_better")
        try:
            value_f = float(value)
        except (TypeError, ValueError):
            return 0.0
        if healthy == alarm:
            return 0.0
        if polarity == "higher_better":
            if value_f >= healthy:
                return 0.0
            if value_f <= alarm:
                return 1.0
            return (healthy - value_f) / (healthy - alarm)
        # lower_better
        if value_f <= healthy:
            return 0.0
        if value_f >= alarm:
            return 1.0
        return (value_f - healthy) / (alarm - healthy)

    def _salience(self, signals: Dict[str, float]) -> float:
        if not signals:
            return 0.0
        # L2 norm of the signal vector, normalised by sqrt(n) so a
        # uniform 1.0 across all channels yields salience 1.0.
        s = math.sqrt(sum(v * v for v in signals.values()))
        return min(1.0, s / max(1.0, math.sqrt(len(signals))))


def _safe_call(obj: Any, method_name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    method = getattr(obj, method_name, None)
    if method is None or not callable(method):
        return default
    try:
        return method()
    except Exception:
        return default
