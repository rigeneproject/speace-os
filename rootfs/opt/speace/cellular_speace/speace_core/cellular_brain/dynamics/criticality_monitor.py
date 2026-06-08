import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class Spike:
    neuron_id: str
    timestamp: float


@dataclass
class Avalanche:
    spikes: List[Spike] = field(default_factory=list)

    @property
    def size(self) -> int:
        return len(self.spikes)

    @property
    def duration(self) -> float:
        if not self.spikes:
            return 0.0
        return self.spikes[-1].timestamp - self.spikes[0].timestamp


class CriticalityMonitor:
    """Monitor neural criticality via avalanche statistics.

    Tracks cascades of neuronal firing (avalanches), estimates the branching
    ratio, and recommends global excitability adjustments to self-organize
    near criticality (branching ratio ~1, power-law avalanches).
    """

    def __init__(
        self,
        avalanche_window: float = 10.0,
        branching_bin_size: float = 5.0,
        max_history: int = 10000,
    ):
        self.avalanche_window = avalanche_window
        self.branching_bin_size = branching_bin_size
        self.max_history = max_history
        self._spikes: List[Spike] = []
        self._avalanches: List[Avalanche] = []
        self._branching_ratio: float = 0.0

    # ------------------------------------------------------------------ #
    # Spike recording
    # ------------------------------------------------------------------ #

    def record_activation(self, neuron_id: str, timestamp: float) -> None:
        """Record a single neuronal activation (spike)."""
        self._spikes.append(Spike(neuron_id=neuron_id, timestamp=timestamp))
        if len(self._spikes) > self.max_history:
            self._spikes.pop(0)

    # ------------------------------------------------------------------ #
    # Avalanche detection
    # ------------------------------------------------------------------ #

    def detect_avalanche(self) -> List[Avalanche]:
        """Group recorded spikes into avalanches based on the time window.

        Consecutive spikes separated by <= avalanche_window belong to the
        same avalanche.
        """
        if not self._spikes:
            return []

        sorted_spikes = sorted(self._spikes, key=lambda s: s.timestamp)
        avalanches: List[Avalanche] = []
        current = Avalanche(spikes=[sorted_spikes[0]])

        for spike in sorted_spikes[1:]:
            if spike.timestamp - current.spikes[-1].timestamp <= self.avalanche_window:
                current.spikes.append(spike)
            else:
                avalanches.append(current)
                current = Avalanche(spikes=[spike])
        avalanches.append(current)

        self._avalanches = avalanches
        return avalanches

    # ------------------------------------------------------------------ #
    # Branching ratio
    # ------------------------------------------------------------------ #

    def get_branching_ratio(self) -> float:
        """Estimate the branching ratio as the average descendants per activation.

        Uses a binned approach: within each avalanche, spikes are divided into
        consecutive time bins of size ``branching_bin_size``. The branching
        ratio is the average ratio of activations in bin t+1 to bin t across
        all consecutive non-empty bin pairs.

        A ratio near 1.0 indicates criticality.
        """
        if not self._avalanches:
            self.detect_avalanche()

        ratios: List[float] = []
        for av in self._avalanches:
            if av.size < 2:
                continue
            bins = self._bin_spikes(av.spikes, self.branching_bin_size)
            for i in range(len(bins) - 1):
                if bins[i] == 0:
                    continue
                ratio = bins[i + 1] / bins[i]
                ratios.append(ratio)

        if not ratios:
            self._branching_ratio = 0.0
        else:
            self._branching_ratio = sum(ratios) / len(ratios)

        return self._branching_ratio

    # ------------------------------------------------------------------ #
    # Avalanche size distribution
    # ------------------------------------------------------------------ #

    def get_avalanche_size_distribution(self) -> Dict[int, int]:
        """Return a histogram of avalanche sizes.

        Keys are avalanche sizes, values are counts.
        """
        if not self._avalanches:
            self.detect_avalanche()

        hist: Dict[int, int] = defaultdict(int)
        for av in self._avalanches:
            hist[av.size] += 1
        return dict(hist)

    # ------------------------------------------------------------------ #
    # Criticality check
    # ------------------------------------------------------------------ #

    def is_near_critical(self, branching_tolerance: float = 0.1) -> bool:
        """Return True if the estimated branching ratio is within tolerance of 1.0."""
        br = self.get_branching_ratio()
        return abs(br - 1.0) <= branching_tolerance

    # ------------------------------------------------------------------ #
    # Modulation recommendation
    # ------------------------------------------------------------------ #

    def recommend_modulation(self) -> Dict[str, float]:
        """Recommend a global excitability adjustment to approach criticality.

        Returns a dict with:
        - ``excitability_delta``: signed adjustment (-1 .. +1)
        - ``target_branching_ratio``: 1.0
        - ``current_branching_ratio``: latest estimate
        - ``reason``: human-readable recommendation
        """
        br = self.get_branching_ratio()
        if br < 1.0:
            delta = min(1.0, 1.0 - br)
            reason = f"subcritical (sigma={br:.3f}): increase global excitability"
        elif br > 1.0:
            delta = max(-1.0, 1.0 - br)
            reason = f"supercritical (sigma={br:.3f}): decrease global excitability"
        else:
            delta = 0.0
            reason = f"critical (sigma={br:.3f}): no adjustment needed"

        return {
            "excitability_delta": delta,
            "target_branching_ratio": 1.0,
            "current_branching_ratio": br,
            "reason": reason,
        }

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _bin_spikes(spikes: List[Spike], bin_size: float) -> List[int]:
        """Bin spikes into consecutive time bins of ``bin_size``."""
        if not spikes:
            return []

        start = spikes[0].timestamp
        end = spikes[-1].timestamp
        n_bins = int((end - start) // bin_size) + 1
        bins = [0] * n_bins
        for spike in spikes:
            idx = int((spike.timestamp - start) // bin_size)
            bins[idx] += 1
        return bins
