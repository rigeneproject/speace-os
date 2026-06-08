import math
from typing import Dict, Optional, Tuple

import numpy as np


class PhaseCouplingEngine:
    """Kuramoto-like phase-coupling engine for oscillator synchrony.

    Implements:
        dphi_i/dt = omega_i + (K/N) * sum_j sin(phi_j - phi_i)
    where K is the coupling strength and N is the number of oscillators.
    """

    def __init__(self, default_coupling_strength: float = 1.0):
        self.default_coupling_strength = default_coupling_strength
        self._oscillators: Dict[str, Dict[str, float]] = {}
        # (source_id, target_id) -> strength
        self._pairwise_coupling: Dict[Tuple[str, str], float] = {}

    # ------------------------------------------------------------------ #
    # Registration
    # ------------------------------------------------------------------ #

    def register_oscillator(self, osc_id: str, freq: float, initial_phase: float = 0.0) -> None:
        """Add an oscillator with natural frequency *freq* (Hz)."""
        self._oscillators[osc_id] = {
            "freq": freq,
            "phase": initial_phase % (2.0 * math.pi),
        }

    def unregister_oscillator(self, osc_id: str) -> None:
        """Remove an oscillator and any associated coupling edges."""
        self._oscillators.pop(osc_id, None)
        # prune pairwise edges involving this oscillator
        self._pairwise_coupling = {
            k: v
            for k, v in self._pairwise_coupling.items()
            if k[0] != osc_id and k[1] != osc_id
        }

    def set_coupling(self, source_id: str, target_id: str, strength: float) -> None:
        """Set a directed coupling strength from *source_id* to *target_id*."""
        if source_id not in self._oscillators:
            raise KeyError(f"Unknown source oscillator: {source_id}")
        if target_id not in self._oscillators:
            raise KeyError(f"Unknown target oscillator: {target_id}")
        self._pairwise_coupling[(source_id, target_id)] = strength

    def get_coupling(self, source_id: str, target_id: str) -> float:
        """Return the directed coupling strength for a pair."""
        return self._pairwise_coupling.get(
            (source_id, target_id), self.default_coupling_strength
        )

    def list_oscillators(self) -> Dict[str, Dict[str, float]]:
        """Return a shallow copy of the oscillator state dictionary."""
        return {k: dict(v) for k, v in self._oscillators.items()}

    # ------------------------------------------------------------------ #
    # Dynamics
    # ------------------------------------------------------------------ #

    def step(self, dt: float) -> None:
        """Advance all oscillator phases by *dt* seconds."""
        ids = list(self._oscillators.keys())
        n = len(ids)
        if n == 0:
            return

        phases = np.array([self._oscillators[oid]["phase"] for oid in ids])
        freqs = np.array([self._oscillators[oid]["freq"] for oid in ids])

        # Pre-compute pairwise phase differences matrix: phi_j - phi_i
        # shape (n, n)
        diff = phases[np.newaxis, :] - phases[:, np.newaxis]
        sin_diff = np.sin(diff)

        # Build coupling matrix
        coupling_matrix = np.full((n, n), self.default_coupling_strength, dtype=float)
        for (src, tgt), strength in self._pairwise_coupling.items():
            i = ids.index(src)
            j = ids.index(tgt)
            coupling_matrix[i, j] = strength

        # Zero out self-coupling
        np.fill_diagonal(coupling_matrix, 0.0)

        # dphi_i = omega_i + (1/N) * sum_j K_{ji} * sin(phi_j - phi_i)
        # Note: sin_diff[j, i] = phi_j - phi_i, and coupling_matrix[j, i] is strength from j to i
        # So for each i, sum over j of coupling_matrix[j, i] * sin_diff[j, i]
        coupling_sum = np.sum(coupling_matrix.T * sin_diff, axis=1) / n
        dphi = (2.0 * math.pi * freqs + coupling_sum) * dt

        new_phases = (phases + dphi) % (2.0 * math.pi)
        for oid, new_phase in zip(ids, new_phases):
            self._oscillators[oid]["phase"] = float(new_phase)

    # ------------------------------------------------------------------ #
    # Diagnostics
    # ------------------------------------------------------------------ #

    def get_order_parameter(self) -> float:
        """Return the Kuramoto order parameter |<e^{i*phi}>| in [0, 1].

        1 means perfect synchrony, 0 means total incoherence.
        """
        if not self._oscillators:
            return 0.0
        phases = np.array([o["phase"] for o in self._oscillators.values()])
        return float(np.abs(np.mean(np.exp(1j * phases))))

    def get_phase(self, osc_id: str) -> float:
        """Return the current phase of a single oscillator."""
        return self._oscillators[osc_id]["phase"]

    def get_phase_difference(self, id1: str, id2: str) -> float:
        """Return the wrapped phase difference (id1 - id2) in [-pi, pi]."""
        diff = self._oscillators[id1]["phase"] - self._oscillators[id2]["phase"]
        # wrap to [-pi, pi]
        diff = (diff + math.pi) % (2.0 * math.pi) - math.pi
        return diff
