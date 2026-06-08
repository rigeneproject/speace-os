from typing import Dict, List, Optional

import numpy as np


class EnergyFieldEngine:
    """Continuous distributed energy/metabolic field over neurons.

    Dynamics per neuron i:
        de_i/dt = D * sum_{j~i}(e_j - e_i)  -- diffusion over synaptic neighbors
                - c * |a_i|^2                -- consumption proportional to activation
                + supply * baseline_i        -- global metabolic supply
                + recovery * resting_i         -- faster recharge when resting
    Energy is clipped to [0, 1].
    """

    def __init__(
        self,
        global_supply_rate: float = 0.02,
        recovery_boost: float = 0.03,
        fatigue_threshold: float = 0.2,
        max_energy: float = 1.0,
        min_energy: float = 0.0,
    ):
        self.global_supply_rate = global_supply_rate
        self.recovery_boost = recovery_boost
        self.fatigue_threshold = fatigue_threshold
        self.max_energy = max_energy
        self.min_energy = min_energy

        # id -> index
        self._index: Dict[str, int] = {}
        self._ids: List[str] = []

        # per-neuron parameters (numpy arrays)
        self._baseline: np.ndarray = np.array([], dtype=np.float64)
        self._consumption: np.ndarray = np.array([], dtype=np.float64)
        self._diffusion: np.ndarray = np.array([], dtype=np.float64)
        self._degree: np.ndarray = np.array([], dtype=np.int64)
        self._energy: np.ndarray = np.array([], dtype=np.float64)

        # edges for diffusion: list of (source_idx, target_idx)
        # Diffusion is symmetric along synapses, so we store both directions.
        self._edges: List[tuple[int, int]] = []
        self._edge_array: Optional[np.ndarray] = None  # shape (E, 2)

    # ------------------------------------------------------------------ #
    # Registration
    # ------------------------------------------------------------------ #

    def register_neuron(
        self,
        neuron_id: str,
        baseline_supply: float = 0.1,
        consumption_rate: float = 0.05,
        diffusion_rate: float = 0.01,
        initial_energy: float = 1.0,
    ) -> None:
        """Add a neuron to the field."""
        if neuron_id in self._index:
            # Update parameters for existing neuron
            idx = self._index[neuron_id]
            self._baseline[idx] = baseline_supply
            self._consumption[idx] = consumption_rate
            self._diffusion[idx] = diffusion_rate
            self._energy[idx] = np.clip(initial_energy, self.min_energy, self.max_energy)
            return

        idx = len(self._ids)
        self._index[neuron_id] = idx
        self._ids.append(neuron_id)

        self._baseline = np.append(self._baseline, baseline_supply)
        self._consumption = np.append(self._consumption, consumption_rate)
        self._diffusion = np.append(self._diffusion, diffusion_rate)
        self._degree = np.append(self._degree, 0)
        self._energy = np.append(
            self._energy, np.clip(initial_energy, self.min_energy, self.max_energy)
        )

    def register_synapse(self, source: str, target: str) -> None:
        """Register a diffusion edge between two neurons."""
        if source not in self._index:
            raise KeyError(f"Source neuron '{source}' not registered")
        if target not in self._index:
            raise KeyError(f"Target neuron '{target}' not registered")

        s = self._index[source]
        t = self._index[target]
        self._edges.append((s, t))
        self._edges.append((t, s))
        self._degree[s] += 1
        self._degree[t] += 1
        self._edge_array = None  # invalidate cached edge array

    # ------------------------------------------------------------------ #
    # Simulation step
    # ------------------------------------------------------------------ #

    def step(self, dt: float, activations: Dict[str, float]) -> None:
        """Advance the energy field by dt given current activations."""
        if self._energy.size == 0:
            return

        n = self._energy.size
        activations_arr = np.zeros(n, dtype=np.float64)
        for nid, a in activations.items():
            idx = self._index.get(nid)
            if idx is not None:
                activations_arr[idx] = a

        # ---- Diffusion: D * sum_{neighbors}(e_j - e_i) ----
        if self._edges:
            edge_arr = self._edge_array
            if edge_arr is None:
                edge_arr = np.array(self._edges, dtype=np.int64)
                self._edge_array = edge_arr
            # neighbor_sum[i] = sum of energy of neighbors of i
            neighbor_sum = np.zeros(n, dtype=np.float64)
            np.add.at(neighbor_sum, edge_arr[:, 1], self._energy[edge_arr[:, 0]])
            diffusion_delta = self._diffusion * (neighbor_sum - self._degree * self._energy)
        else:
            diffusion_delta = np.zeros(n, dtype=np.float64)

        # ---- Consumption: -c * a^2 ----
        consumption_delta = -self._consumption * (activations_arr**2)

        # ---- Global supply: supply_rate * baseline_i ----
        supply_delta = self.global_supply_rate * self._baseline

        # ---- Recovery boost for resting neurons (|a| < small epsilon) ----
        resting = np.abs(activations_arr) < 1e-9
        recovery_delta = np.where(resting, self.recovery_boost, 0.0)

        # ---- Total update ----
        denergy = diffusion_delta + consumption_delta + supply_delta + recovery_delta
        self._energy += dt * denergy
        self._energy = np.clip(self._energy, self.min_energy, self.max_energy)

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def get_energy(self, neuron_id: str) -> float:
        """Return the current energy of a neuron."""
        idx = self._index.get(neuron_id)
        if idx is None:
            raise KeyError(f"Neuron '{neuron_id}' not registered")
        return float(self._energy[idx])

    def get_global_energy(self) -> float:
        """Average energy across all registered neurons."""
        if self._energy.size == 0:
            return 0.0
        return float(self._energy.mean())

    def get_fatigued_neurons(self, threshold: float = 0.2) -> List[str]:
        """Return neuron IDs with energy below threshold."""
        mask = self._energy < threshold
        return [self._ids[i] for i in np.flatnonzero(mask)]

    def add_supply(self, neuron_id: str, amount: float) -> None:
        """Astrocyte-like local supply boost."""
        idx = self._index.get(neuron_id)
        if idx is None:
            raise KeyError(f"Neuron '{neuron_id}' not registered")
        self._energy[idx] = np.clip(
            self._energy[idx] + amount, self.min_energy, self.max_energy
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def get_all_energies(self) -> Dict[str, float]:
        """Return a mapping of all neuron IDs to current energies."""
        return {nid: float(self._energy[i]) for i, nid in enumerate(self._ids)}

    def neuron_count(self) -> int:
        return len(self._ids)

    def synapse_count(self) -> int:
        # Each physical synapse is stored as two directed edges
        return len(self._edges) // 2
