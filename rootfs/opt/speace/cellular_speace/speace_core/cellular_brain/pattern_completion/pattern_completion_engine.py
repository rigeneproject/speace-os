import math
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class PatternMemory(BaseModel):
    patterns: List[List[float]] = []
    weight_matrix: List[List[float]] = []
    dim: int = 0

    model_config = ConfigDict(arbitrary_types_allowed=True)


class PatternCompletionEngine:
    """Associative Pattern Completion engine (auto-associative memory).

    Stores patterns via Hebbian weight matrix and reconstructs
    complete patterns from partial or noisy cues.
    """

    def __init__(self, dim: int = 784, use_async_update: bool = True):
        self.dim = dim
        self.use_async_update = use_async_update
        self.memory = PatternMemory(dim=dim)
        self._initialize_weights()

    def _initialize_weights(self) -> None:
        self.memory.weight_matrix = [
            [0.0 for _ in range(self.dim)] for _ in range(self.dim)
        ]

    def _dot_row(self, row: List[float], vec: List[float]) -> float:
        return sum(r * v for r, v in zip(row, vec))

    def _sign(self, x: float) -> float:
        if x > 0:
            return 1.0
        if x < 0:
            return -1.0
        return 0.0

    def store_pattern(self, pattern: List[float]) -> None:
        if len(pattern) != self.dim:
            raise ValueError("pattern dimension must match engine dim")
        self.memory.patterns.append(pattern[:])
        # Hebbian update: w_ij += p_i * p_j / N for i != j
        n = len(self.memory.patterns)
        for i in range(self.dim):
            for j in range(self.dim):
                if i == j:
                    continue
                self.memory.weight_matrix[i][j] += (
                    pattern[i] * pattern[j] / n
                )

    def store_patterns(self, patterns: List[List[float]]) -> None:
        for p in patterns:
            self.store_pattern(p)

    def _update_synchronous(self, state: List[float]) -> List[float]:
        new_state = []
        for i in range(self.dim):
            net = self._dot_row(self.memory.weight_matrix[i], state)
            new_state.append(self._sign(net))
        return new_state

    def _update_asynchronous(self, state: List[float]) -> List[float]:
        import random

        new_state = state[:]
        indices = list(range(self.dim))
        random.shuffle(indices)
        for i in indices:
            net = self._dot_row(self.memory.weight_matrix[i], new_state)
            new_state[i] = self._sign(net)
        return new_state

    def complete_pattern(
        self,
        partial_pattern: List[float],
        steps: int = 10,
        missing_value: Optional[float] = None,
    ) -> List[float]:
        if len(partial_pattern) != self.dim:
            raise ValueError("pattern dimension must match engine dim")
        state = partial_pattern[:]
        if missing_value is not None:
            # Initialize missing values to random small noise
            import random
            state = [
                random.choice([-1.0, 1.0]) if v == missing_value else v
                for v in state
            ]
        for _ in range(steps):
            if self.use_async_update:
                state = self._update_asynchronous(state)
            else:
                state = self._update_synchronous(state)
        return state

    def energy(self, state: List[float]) -> float:
        e = 0.0
        for i in range(self.dim):
            for j in range(self.dim):
                if i == j:
                    continue
                e += self.memory.weight_matrix[i][j] * state[i] * state[j]
        return -e / 2.0
