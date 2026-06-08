import math
from typing import Dict, Optional

import numpy as np


class NeuralOscillatorBank:
    """Bank of neural oscillators for theta, alpha, beta and gamma bands.

    Each oscillator tracks frequency (Hz), instantaneous phase and amplitude.
    Neurons can be registered to a band so that their firing threshold is
    modulated by the oscillatory envelope.
    """

    DEFAULT_BANDS = {
        "theta": {"freq": 5.0, "amplitude": 1.0},
        "alpha": {"freq": 10.0, "amplitude": 1.0},
        "beta": {"freq": 20.0, "amplitude": 1.0},
        "gamma": {"freq": 40.0, "amplitude": 1.0},
    }

    def __init__(self, bands: Optional[Dict[str, Dict[str, float]]] = None):
        self.bands = bands if bands is not None else dict(self.DEFAULT_BANDS)
        self.phases: Dict[str, float] = {band: 0.0 for band in self.bands}
        self._coupling_inputs: Dict[str, float] = {band: 0.0 for band in self.bands}
        self._neuron_registry: Dict[str, Dict[str, float]] = {}

    # ------------------------------------------------------------------ #
    # Oscillator state
    # ------------------------------------------------------------------ #

    def get_phase(self, band: str) -> float:
        """Return the current phase of the requested band in radians."""
        if band not in self.bands:
            raise KeyError(f"Unknown band: {band}")
        return self.phases[band]

    def get_envelope(self, band: str) -> float:
        """Return the current amplitude-modulation envelope of the band."""
        if band not in self.bands:
            raise KeyError(f"Unknown band: {band}")
        return self.bands[band]["amplitude"]

    def set_coupling_input(self, band: str, value: float) -> None:
        """Inject an external coupling term for *band* (rad/s)."""
        if band not in self.bands:
            raise KeyError(f"Unknown band: {band}")
        self._coupling_inputs[band] = value

    # ------------------------------------------------------------------ #
    # Time stepping
    # ------------------------------------------------------------------ #

    def step(self, dt: float) -> None:
        """Advance all oscillator phases by *dt* seconds.

        Phase evolution follows:
            dphi/dt = 2*pi*freq + coupling_term
        """
        for band, params in self.bands.items():
            omega = 2.0 * math.pi * params["freq"]
            coupling = self._coupling_inputs[band]
            self.phases[band] += (omega + coupling) * dt
            # wrap to [0, 2*pi)
            self.phases[band] %= 2.0 * math.pi

    # ------------------------------------------------------------------ #
    # Neuron registration / modulation
    # ------------------------------------------------------------------ #

    def register_neuron(self, neuron_id: str, band: str, coupling_strength: float) -> None:
        """Assign a neuron to an oscillatory band with a coupling strength."""
        if band not in self.bands:
            raise KeyError(f"Unknown band: {band}")
        self._neuron_registry[neuron_id] = {
            "band": band,
            "coupling_strength": coupling_strength,
        }

    def unregister_neuron(self, neuron_id: str) -> None:
        """Remove a neuron from the registry."""
        self._neuron_registry.pop(neuron_id, None)

    def get_neural_modulation(self, neuron_id: str) -> float:
        """Return threshold modulation factor: 1 + c * sin(phase).

        Raises KeyError if the neuron has not been registered.
        """
        entry = self._neuron_registry[neuron_id]
        band = entry["band"]
        c = entry["coupling_strength"]
        phase = self.phases[band]
        return 1.0 + c * math.sin(phase)

    def get_band_for_neuron(self, neuron_id: str) -> str:
        """Return the band assigned to a registered neuron."""
        return self._neuron_registry[neuron_id]["band"]

    def list_registered_neurons(self) -> Dict[str, Dict[str, float]]:
        """Return a copy of the neuron registry."""
        return dict(self._neuron_registry)
