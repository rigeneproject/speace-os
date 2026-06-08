"""T-EDP — Energy-Driven Plasticity.

Couples :class:`EnergyFieldEngine` to per-synapse plasticity rates.

Biological motivation
---------------------
In the brain, long-term synaptic modification is metabolically
expensive (protein synthesis, vesicle recycling, mitochondrial load).
A neuron's local energy budget therefore gates how plastic its
synapses can be: under fatigue, the cell suppresses LTP and shifts
toward LTD, effectively protecting the tissue from runaway
potentiation.

Computational model
-------------------
For every synapse ``s = (pre -> post)``:

    energy_eff = E[post] / (E[post] + fatigue_threshold)
    metabolic_cost_multiplier = clamp(energy_eff, 0.0, 1.0)
    effective_ltp_rate = base_ltp_rate * metabolic_cost_multiplier
    effective_ltd_rate = base_ltd_rate * (1.0 + (1.0 - metabolic_cost_multiplier))

This means:

* Healthy neurons: full LTP, baseline LTD.
* Fatigued neurons: LTP suppressed, LTD amplified (forgetting > learning).
* Energy field can also *boost* high-utility synapses via
  :meth:`apply_energy_bonus`.

The class does not mutate synapses itself; it returns a per-synapse
multiplier map that the caller (STDP engine, plasticity engine,
orchestrator) is expected to honour.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

_logger = logging.getLogger(__name__)


@dataclass
class SynapseEnergyModulation:
    """Per-synapse plasticity modulation derived from post-synaptic energy."""

    synapse_key: tuple
    ltp_multiplier: float
    ltd_multiplier: float
    energy_efficiency: float


class EnergyDrivenPlasticity:
    """Translate post-synaptic energy into per-synapse plasticity gates."""

    def __init__(
        self,
        fatigue_threshold: float = 0.2,
        ltp_floor: float = 0.05,
        ltd_ceiling: float = 3.0,
        utility_bonus_scale: float = 0.5,
    ):
        self.fatigue_threshold = float(fatigue_threshold)
        self.ltp_floor = float(ltp_floor)
        self.ltd_ceiling = float(ltd_ceiling)
        self.utility_bonus_scale = float(utility_bonus_scale)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def compute_modulation_map(
        self,
        synapses: Iterable[Any],
        energy_field: Any,
        utility_map: Optional[Dict[tuple, float]] = None,
    ) -> Dict[tuple, SynapseEnergyModulation]:
        """Compute one modulation entry per synapse.

        ``synapses`` is an iterable of objects exposing ``source`` and
        ``target`` identifiers (string-like). ``energy_field`` must
        expose ``get_energy(neuron_id) -> float``. ``utility_map`` is an
        optional per-synapse utility signal in [0, 1] used to grant an
        LTP boost to highly useful synapses even under fatigue.
        """
        utility_map = utility_map or {}
        out: Dict[tuple, SynapseEnergyModulation] = {}
        for s in synapses:
            src = getattr(s, "source", None)
            tgt = getattr(s, "target", None)
            if src is None or tgt is None:
                continue
            try:
                energy = float(energy_field.get_energy(tgt))
            except Exception:
                energy = 1.0

            # E / (E + K): sigmoid-like fatigue function.
            denom = energy + self.fatigue_threshold
            efficiency = energy / denom if denom > 0 else 1.0
            efficiency = max(0.0, min(1.0, efficiency))

            ltp_mult = max(self.ltp_floor, efficiency)
            ltd_mult = min(self.ltd_ceiling, 1.0 + (1.0 - efficiency))

            # Utility bonus: high-utility synapses are still plastic
            # even when the post neuron is slightly fatigued.
            utility = float(utility_map.get((src, tgt), 0.0))
            if utility > 0.0 and efficiency < 1.0:
                bonus = self.utility_bonus_scale * utility * (1.0 - efficiency)
                ltp_mult = min(1.0, ltp_mult + bonus)

            out[(src, tgt)] = SynapseEnergyModulation(
                synapse_key=(src, tgt),
                ltp_multiplier=float(ltp_mult),
                ltd_multiplier=float(ltd_mult),
                energy_efficiency=float(efficiency),
            )
        return out

    def apply_to_stdp_engine(
        self,
        stdp_engine: Any,
        modulation_map: Dict[tuple, SynapseEnergyModulation],
    ) -> None:
        """Mutate *stdp_engine*'s rates to reflect the average modulation.

        This is a coarse but safe way to feed energy into existing
        STDP. Fine-grained per-synapse gating should be done by the
        orchestrator using :meth:`compute_modulation_map` directly.
        """
        if not modulation_map:
            return
        avg_ltp = sum(m.ltp_multiplier for m in modulation_map.values()) / len(
            modulation_map
        )
        avg_ltd = sum(m.ltd_multiplier for m in modulation_map.values()) / len(
            modulation_map
        )
        if hasattr(stdp_engine, "ltp_rate"):
            stdp_engine.ltp_rate = max(
                0.0, float(getattr(stdp_engine, "ltp_rate", 0.05)) * avg_ltp
            )
        if hasattr(stdp_engine, "ltd_rate"):
            stdp_engine.ltd_rate = max(
                0.0, float(getattr(stdp_engine, "ltd_rate", 0.03)) * avg_ltd
            )

    def apply_energy_bonus(
        self,
        energy_field: Any,
        high_utility_synapses: Iterable[Any],
        bonus_amount: float = 0.05,
    ) -> int:
        """Give high-utility synapses a small metabolic bonus.

        Returns the number of neurons that received a bonus. This is a
        crude astrocyte-like effect: useful connections get
        preferentially replenished.
        """
        count = 0
        for s in high_utility_synapses:
            tgt = getattr(s, "target", None)
            if tgt is None:
                continue
            try:
                energy_field.add_supply(tgt, bonus_amount)
                count += 1
            except Exception:
                continue
        return count

    # ------------------------------------------------------------------ #
    # Diagnostics
    # ------------------------------------------------------------------ #

    def summarise(self, modulation_map: Dict[tuple, SynapseEnergyModulation]) -> Dict[str, float]:
        if not modulation_map:
            return {
                "count": 0,
                "mean_ltp_mult": 1.0,
                "mean_ltd_mult": 1.0,
                "mean_efficiency": 1.0,
            }
        n = len(modulation_map)
        return {
            "count": float(n),
            "mean_ltp_mult": sum(m.ltp_multiplier for m in modulation_map.values()) / n,
            "mean_ltd_mult": sum(m.ltd_multiplier for m in modulation_map.values()) / n,
            "mean_efficiency": sum(m.energy_efficiency for m in modulation_map.values()) / n,
        }
