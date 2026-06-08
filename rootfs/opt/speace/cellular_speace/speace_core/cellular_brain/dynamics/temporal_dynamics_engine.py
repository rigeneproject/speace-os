from typing import Any, Dict, List, Tuple

import numpy as np


class TemporalDynamicsEngine:
    """Core continuous-time substrate for SPEACE neural dynamics.

    Evolves continuous variables between and within discrete ticks using
    coupled first-order ODEs for activation, synaptic weight and metabolic
    energy.

    Equations (per neuron / synapse, Euler integration):
        da/dt = -a/tau + input(t) + noise
        dw/dt = -w/tau_w + plasticity_rate * correlation(t) - decay
        de/dt = -e/tau_e + supply - consumption * |a(t)|
    """

    def __init__(
        self,
        neurons: List[Any],
        synapses: List[Any],
        tau: float = 1.0,
        tau_w: float = 10.0,
        tau_e: float = 5.0,
        noise_std: float = 0.0,
        supply: float = 0.1,
        consumption: float = 0.05,
        plasticity_rate: float = 0.05,
        weight_bounds: Tuple[float, float] = (0.0, 1.0),
        energy_bounds: Tuple[float, float] = (0.0, 1.0),
    ):
        self.tau = tau
        self.tau_w = tau_w
        self.tau_e = tau_e
        self.noise_std = noise_std
        self.supply = supply
        self.consumption = consumption
        self.plasticity_rate = plasticity_rate
        self.weight_bounds = weight_bounds
        self.energy_bounds = energy_bounds

        self.t: float = 0.0

        # ------------------------------------------------------------------ #
        # Neuron indexing
        # ------------------------------------------------------------------ #
        self.neuron_ids: List[str] = []
        self.neuron_id_to_idx: Dict[str, int] = {}
        self.thresholds: np.ndarray = np.array([], dtype=np.float64)

        for n in neurons:
            nid = getattr(n, "cell_id", None)
            if nid is None and isinstance(n, dict):
                nid = n.get("cell_id") or n.get("id")
            if nid is None:
                raise ValueError("Neuron must have an identifier (cell_id or id)")

            idx = len(self.neuron_ids)
            self.neuron_ids.append(nid)
            self.neuron_id_to_idx[nid] = idx

            thresh = getattr(n, "threshold", None)
            if thresh is None and isinstance(n, dict):
                thresh = n.get("threshold", 0.5)
            if thresh is None:
                thresh = 0.5
            self.thresholds = np.append(self.thresholds, float(thresh))

        self.num_neurons = len(self.neuron_ids)

        # Continuous state arrays
        self.a = np.zeros(self.num_neurons, dtype=np.float64)          # activation
        self.e = np.ones(self.num_neurons, dtype=np.float64) * 0.5      # energy
        self.input_buffer = np.zeros(self.num_neurons, dtype=np.float64)
        self.oscillator_forcing = np.zeros(self.num_neurons, dtype=np.float64)

        # ------------------------------------------------------------------ #
        # Synapse indexing
        # ------------------------------------------------------------------ #
        self.synapse_keys: List[Tuple[str, str]] = []
        self.synapse_to_idx: Dict[Tuple[str, str], int] = {}
        self.pre_idx = np.array([], dtype=np.int64)
        self.post_idx = np.array([], dtype=np.int64)
        self.w = np.array([], dtype=np.float64)
        self.decay = np.array([], dtype=np.float64)

        for s in synapses:
            src = getattr(s, "source", None)
            if src is None and isinstance(s, dict):
                src = s.get("source")
            tgt = getattr(s, "target", None)
            if tgt is None and isinstance(s, dict):
                tgt = s.get("target")
            if src is None or tgt is None:
                raise ValueError("Synapse must have source and target identifiers")

            key = (src, tgt)
            if key in self.synapse_to_idx:
                continue

            if src not in self.neuron_id_to_idx or tgt not in self.neuron_id_to_idx:
                raise ValueError(
                    f"Synapse {key} references unknown neuron"
                )

            idx = len(self.synapse_keys)
            self.synapse_keys.append(key)
            self.synapse_to_idx[key] = idx

            self.pre_idx = np.append(self.pre_idx, self.neuron_id_to_idx[src])
            self.post_idx = np.append(self.post_idx, self.neuron_id_to_idx[tgt])

            w_init = getattr(s, "weight", None)
            if w_init is None and isinstance(s, dict):
                w_init = s.get("weight", 0.5)
            if w_init is None:
                w_init = 0.5
            self.w = np.append(self.w, float(w_init))

            d_init = getattr(s, "decay", None)
            if d_init is None and isinstance(s, dict):
                d_init = s.get("decay", 0.001)
            if d_init is None:
                d_init = 0.001
            self.decay = np.append(self.decay, float(d_init))

        self.num_synapses = len(self.synapse_keys)

    # ------------------------------------------------------------------ #
    # Dynamic registration (T156-fix)
    # ------------------------------------------------------------------ #

    def _register_neuron(self, neuron_id: str) -> int:
        """Auto-register a neuron that was not present at construction time.

        Used by ``get_neuron_state`` and ``inject_input`` to gracefully handle
        neurons added to the circuit after this engine was built (e.g. via
        neurogenesis). The neuron is appended with default state (a=0,
        threshold=0.5, energy=1.0) and the input buffer is extended to match.
        """
        if neuron_id in self.neuron_id_to_idx:
            return self.neuron_id_to_idx[neuron_id]
        idx = len(self.neuron_ids)
        self.neuron_ids.append(neuron_id)
        self.neuron_id_to_idx[neuron_id] = idx

        # Extend state arrays (only those initialized in __init__)
        self.a = np.append(self.a, 0.0)
        self.e = np.append(self.e, 0.5)  # match __init__ default energy
        self.input_buffer = np.append(self.input_buffer, 0.0)
        self.oscillator_forcing = np.append(self.oscillator_forcing, 0.0)

        self.num_neurons = len(self.neuron_ids)
        return idx

    # ------------------------------------------------------------------ #
    # Simulation step
    # ------------------------------------------------------------------ #

    def step(self, dt: float) -> None:
        """Advance all continuous ODEs by *dt* using Euler integration."""
        if self.num_neurons == 0:
            self.t += dt
            return

        # Gaussian noise treated as an additive rate term
        noise = self.noise_std * np.random.normal(size=self.num_neurons)

        # Total continuous input = injected stimuli + oscillatory forcing + noise
        total_input = self.input_buffer + self.oscillator_forcing + noise

        # Activation ODE: da/dt = -a/tau + input(t) + noise
        da = (-self.a / self.tau + total_input) * dt
        self.a += da

        # Synapse plasticity ODE: dw/dt = -w/tau_w + plasticity_rate * correlation - decay
        if self.num_synapses > 0:
            correlation = self.a[self.pre_idx] * self.a[self.post_idx]
            dw = (-self.w / self.tau_w + self.plasticity_rate * correlation - self.decay) * dt
            self.w += dw
            self.w = np.clip(self.w, self.weight_bounds[0], self.weight_bounds[1])

        # Energy ODE: de/dt = -e/tau_e + supply - consumption * |a(t)|
        de = (-self.e / self.tau_e + self.supply - self.consumption * np.abs(self.a)) * dt
        self.e += de
        self.e = np.clip(self.e, self.energy_bounds[0], self.energy_bounds[1])

        # Advance global time
        self.t += dt

        # Clear instantaneous stimulus buffer (oscillator forcing persists)
        self.input_buffer.fill(0.0)

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def get_neuron_state(self, neuron_id: str) -> float:
        """Return the current continuous activation *a(t)* for a neuron."""
        idx = self.neuron_id_to_idx.get(neuron_id)
        if idx is None:
            # T156-fix: auto-register late-added neurons (e.g. after
            # neurogenesis) so downstream benchmark lookups do not crash.
            idx = self._register_neuron(neuron_id)
        return float(self.a[idx])

    def get_synapse_weight(self, source: str, target: str) -> float:
        """Return the current continuous weight *w(t)* for a synapse."""
        idx = self.synapse_to_idx.get((source, target))
        if idx is None:
            raise KeyError(f"Synapse {source}->{target} not found")
        return float(self.w[idx])

    # ------------------------------------------------------------------ #
    # External perturbations
    # ------------------------------------------------------------------ #

    def inject_input(self, neuron_id: str, stimulus: float) -> None:
        """Add an instantaneous stimulus to a neuron's input buffer.

        The stimulus is consumed during the next *step()*.
        """
        idx = self.neuron_id_to_idx.get(neuron_id)
        if idx is None:
            # T156-fix: auto-register late-added neurons (conservative).
            idx = self._register_neuron(neuron_id)
        self.input_buffer[idx] += stimulus

    def couple_oscillations(self, oscillator_values: Dict[str, float]) -> None:
        """Apply oscillatory forcing to neurons.

        *oscillator_values* maps neuron identifiers to a continuous forcing
        value (e.g. from a :class:`NeuralOscillatorBank`). The forcing is
        added to the neuron's input term during every *step()* until it is
        overwritten by a subsequent call.
        """
        self.oscillator_forcing.fill(0.0)
        for nid, val in oscillator_values.items():
            idx = self.neuron_id_to_idx.get(nid)
            if idx is not None:
                self.oscillator_forcing[idx] += val
