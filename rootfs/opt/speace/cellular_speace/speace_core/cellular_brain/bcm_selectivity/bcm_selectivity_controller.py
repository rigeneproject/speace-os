from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict

from speace_core.cellular_brain.bcm_selectivity.bcm_selectivity_engine import (
    BCMNeuronState,
    BCMSelectivityEngine,
)


class BCMTrainingResult(BaseModel):
    final_states: List[BCMNeuronState] = []
    mean_selectivity: float = 0.0
    selectivity_diversity: float = 0.0  # variance of selectivity indices

    model_config = ConfigDict(arbitrary_types_allowed=True)


class BCMSelectivityController:
    """Coordinates BCM training across a population of neurons."""

    def __init__(
        self,
        engine: Optional[BCMSelectivityEngine] = None,
        input_dim: int = 784,
    ):
        self.engine = engine or BCMSelectivityEngine()
        self.input_dim = input_dim

    def initialize_neurons(self, count: int) -> List[BCMNeuronState]:
        import random

        states = []
        for _ in range(count):
            weights = [random.gauss(0, 0.01) for _ in range(self.input_dim)]
            states.append(
                BCMNeuronState(
                    weights=weights,
                    theta_m=0.0,
                    selectivity_index=0.0,
                    activation_history=[],
                )
            )
        return states

    def train_population(
        self,
        states: List[BCMNeuronState],
        dataset: List[List[float]],
        epochs: int = 1,
    ) -> BCMTrainingResult:
        for _ in range(epochs):
            for sample in dataset:
                for i, state in enumerate(states):
                    states[i] = self.engine.update_neuron(state, sample)

        selectivities = [s.selectivity_index for s in states]
        mean_sel = sum(selectivities) / len(selectivities) if selectivities else 0.0
        diversity = (
            sum((s - mean_sel) ** 2 for s in selectivities) / len(selectivities)
            if selectivities else 0.0
        )
        return BCMTrainingResult(
            final_states=states,
            mean_selectivity=mean_sel,
            selectivity_diversity=diversity,
        )

    def compute_population_response(
        self,
        states: List[BCMNeuronState],
        inputs: List[float],
    ) -> List[float]:
        return [
            self.engine.compute_activation(s.weights, inputs) for s in states
        ]
