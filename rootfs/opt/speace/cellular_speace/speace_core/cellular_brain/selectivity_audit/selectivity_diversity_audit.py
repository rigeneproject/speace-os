import math
from typing import List

from pydantic import BaseModel, ConfigDict


class SelectivityDiversityReport(BaseModel):
    mean_selectivity: float = 0.0
    std_selectivity: float = 0.0
    cv_selectivity: float = 0.0  # coefficient of variation
    entropy: float = 0.0
    gini_index: float = 0.0
    specialized_neurons: int = 0
    total_neurons: int = 0
    diversity_score: float = 0.0  # composite score 0-1

    model_config = ConfigDict(arbitrary_types_allowed=True)


class SelectivityDiversityAudit:
    """Audits the diversity of selectivity across a neuron population.

    High diversity means neurons are specialized for different stimuli,
    which is desirable for efficient pattern recognition.
    """

    def __init__(self, specialization_threshold: float = 0.5):
        self.specialization_threshold = specialization_threshold

    def audit(self, selectivity_indices: List[float]) -> SelectivityDiversityReport:
        n = len(selectivity_indices)
        if n == 0:
            return SelectivityDiversityReport(total_neurons=0)

        mean_sel = sum(selectivity_indices) / n
        var_sel = (
            sum((s - mean_sel) ** 2 for s in selectivity_indices) / n
            if n > 0
            else 0.0
        )
        std_sel = math.sqrt(var_sel)
        cv = std_sel / (mean_sel + 1e-8)

        # Entropy of selectivity distribution (discretized into bins)
        entropy = self._compute_entropy(selectivity_indices)

        # Gini index (inequality measure)
        gini = self._compute_gini(selectivity_indices)

        specialized = sum(1 for s in selectivity_indices if s >= self.specialization_threshold)

        # Composite diversity score: higher entropy, higher CV, lower Gini = more diverse
        # Normalize entropy (max entropy for uniform over 10 bins ~ 2.3)
        normalized_entropy = min(entropy / 2.3, 1.0)
        normalized_cv = min(cv / 2.0, 1.0)
        # For diversity we want high entropy and high CV, but not extreme inequality (Gini)
        diversity_score = (normalized_entropy * 0.4 + normalized_cv * 0.4 + (1.0 - gini) * 0.2)

        return SelectivityDiversityReport(
            mean_selectivity=mean_sel,
            std_selectivity=std_sel,
            cv_selectivity=cv,
            entropy=entropy,
            gini_index=gini,
            specialized_neurons=specialized,
            total_neurons=n,
            diversity_score=diversity_score,
        )

    def _compute_entropy(self, values: List[float], bins: int = 10) -> float:
        if not values:
            return 0.0
        min_v = min(values)
        max_v = max(values)
        if min_v == max_v:
            return 0.0
        # Discretize into bins
        counts = [0] * bins
        for v in values:
            idx = int((v - min_v) / (max_v - min_v + 1e-8) * bins)
            idx = min(idx, bins - 1)
            counts[idx] += 1
        entropy = 0.0
        n = len(values)
        for c in counts:
            if c > 0:
                p = c / n
                entropy -= p * math.log(p)
        return entropy

    def _compute_gini(self, values: List[float]) -> float:
        """Compute Gini coefficient (0 = perfect equality, 1 = max inequality)."""
        n = len(values)
        if n == 0:
            return 0.0
        sorted_values = sorted(values)
        cumsum = 0.0
        for i, v in enumerate(sorted_values, 1):
            cumsum += (2 * i - n - 1) * v
        denominator = n * sum(sorted_values)
        if denominator == 0:
            return 0.0
        return cumsum / denominator
