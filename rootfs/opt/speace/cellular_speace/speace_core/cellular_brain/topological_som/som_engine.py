import math
from typing import List, Tuple

from pydantic import BaseModel, ConfigDict


class SOMNeuron(BaseModel):
    weights: List[float] = []
    grid_x: int = 0
    grid_y: int = 0

    model_config = ConfigDict(arbitrary_types_allowed=True)


class SOMEngine:
    """Self-Organizing Map (SOM) / Kohonen map engine.

    Maps high-dimensional input vectors onto a 2D topological grid
    while preserving neighborhood relationships.
    """

    def __init__(
        self,
        input_dim: int = 784,
        grid_width: int = 10,
        grid_height: int = 10,
        initial_learning_rate: float = 0.1,
        initial_radius: float = 5.0,
        radius_decay: float = 0.995,
        lr_decay: float = 0.995,
    ):
        self.input_dim = input_dim
        self.grid_width = grid_width
        self.grid_height = grid_height
        self.initial_learning_rate = initial_learning_rate
        self.initial_radius = initial_radius
        self.radius_decay = radius_decay
        self.lr_decay = lr_decay
        self.current_radius = initial_radius
        self.current_lr = initial_learning_rate
        self.map: List[SOMNeuron] = []
        self._initialize_map()

    def _initialize_map(self) -> None:
        import random

        self.map = []
        for y in range(self.grid_height):
            for x in range(self.grid_width):
                weights = [random.uniform(-0.01, 0.01) for _ in range(self.input_dim)]
                self.map.append(
                    SOMNeuron(weights=weights, grid_x=x, grid_y=y)
                )

    def _euclidean_distance(self, a: List[float], b: List[float]) -> float:
        return math.sqrt(sum((ai - bi) ** 2 for ai, bi in zip(a, b)))

    def find_bmu(self, inputs: List[float]) -> SOMNeuron:
        best = self.map[0]
        best_dist = self._euclidean_distance(best.weights, inputs)
        for neuron in self.map[1:]:
            dist = self._euclidean_distance(neuron.weights, inputs)
            if dist < best_dist:
                best = neuron
                best_dist = dist
        return best

    def _grid_distance(self, a: SOMNeuron, b: SOMNeuron) -> float:
        return math.sqrt((a.grid_x - b.grid_x) ** 2 + (a.grid_y - b.grid_y) ** 2)

    def _neighborhood_function(self, distance: float) -> float:
        if self.current_radius <= 0.0:
            return 1.0 if distance == 0.0 else 0.0
        return math.exp(-(distance ** 2) / (2 * (self.current_radius ** 2)))

    def update(self, inputs: List[float]) -> None:
        bmu = self.find_bmu(inputs)
        new_map = []
        for neuron in self.map:
            dist = self._grid_distance(neuron, bmu)
            influence = self._neighborhood_function(dist)
            new_weights = [
                w + self.current_lr * influence * (inp - w)
                for w, inp in zip(neuron.weights, inputs)
            ]
            new_map.append(
                SOMNeuron(
                    weights=new_weights,
                    grid_x=neuron.grid_x,
                    grid_y=neuron.grid_y,
                )
            )
        self.map = new_map
        self.current_lr *= self.lr_decay
        self.current_radius *= self.radius_decay

    def train(self, dataset: List[List[float]], epochs: int = 1) -> None:
        for _ in range(epochs):
            for sample in dataset:
                self.update(sample)

    def get_quantization_error(self, dataset: List[List[float]]) -> float:
        total = 0.0
        for sample in dataset:
            bmu = self.find_bmu(sample)
            total += self._euclidean_distance(bmu.weights, sample)
        return total / len(dataset) if dataset else 0.0
