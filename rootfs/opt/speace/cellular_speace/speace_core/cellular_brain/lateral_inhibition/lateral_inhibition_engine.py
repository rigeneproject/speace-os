from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class LateralInhibitionState(BaseModel):
    raw_activations: List[float] = []
    inhibited_activations: List[float] = []

    model_config = ConfigDict(arbitrary_types_allowed=True)


class LateralInhibitionEngine:
    """Applies lateral inhibition among neurons in the same layer.

    Inhibited activation_i = raw_i - sum_j (w_inh[i][j] * raw_j)
    where w_inh[i][j] represents the lateral inhibition strength from j to i.
    """

    def __init__(
        self,
        inhibition_matrix: Optional[List[List[float]]] = None,
        inhibition_strength: float = 0.1,
        local_radius: Optional[int] = None,
        use_softmax_competition: bool = False,
    ):
        self.inhibition_matrix = inhibition_matrix
        self.inhibition_strength = inhibition_strength
        self.local_radius = local_radius
        self.use_softmax_competition = use_softmax_competition

    def _build_inhibition_matrix(self, n: int) -> List[List[float]]:
        if self.inhibition_matrix is not None:
            return self.inhibition_matrix
        matrix = [[0.0 for _ in range(n)] for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                if self.local_radius is not None:
                    distance = abs(i - j)
                    if distance > self.local_radius:
                        continue
                    strength = self.inhibition_strength * (1.0 - distance / (self.local_radius + 1))
                else:
                    strength = self.inhibition_strength / (n - 1)
                matrix[i][j] = strength
        return matrix

    def apply(self, raw_activations: List[float]) -> LateralInhibitionState:
        n = len(raw_activations)
        matrix = self._build_inhibition_matrix(n)
        inhibited = []
        for i in range(n):
            inhibition = sum(matrix[i][j] * raw_activations[j] for j in range(n))
            val = raw_activations[i] - inhibition
            if self.use_softmax_competition:
                # Softmax competition: subtract mean inhibition, keep relative ordering
                val = max(val, 0.0)
            inhibited.append(val)
        return LateralInhibitionState(
            raw_activations=raw_activations,
            inhibited_activations=inhibited,
        )

    def apply_and_normalize(
        self,
        raw_activations: List[float],
        normalize: bool = True,
    ) -> LateralInhibitionState:
        state = self.apply(raw_activations)
        if normalize and state.inhibited_activations:
            max_val = max(abs(a) for a in state.inhibited_activations)
            if max_val > 0:
                state.inhibited_activations = [
                    a / max_val for a in state.inhibited_activations
                ]
        return state
