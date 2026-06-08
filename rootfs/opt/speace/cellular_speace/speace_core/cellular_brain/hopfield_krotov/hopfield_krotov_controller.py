from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from speace_core.cellular_brain.hopfield_krotov.hopfield_krotov_engine import (
    HopfieldKrotovEngine,
    HopfieldKrotovNeuronState,
)


class HopfieldKrotovTrainingResult(BaseModel):
    final_states: List[HopfieldKrotovNeuronState] = []
    mean_reconstruction_error: float = 0.0

    model_config = ConfigDict(arbitrary_types_allowed=True)


class HopfieldKrotovController:
    """Coordinates training of a Hopfield-Krotov competitive hidden layer."""

    def __init__(
        self,
        engine: Optional[HopfieldKrotovEngine] = None,
        input_dim: int = 784,
        hidden_dim: int = 100,
    ):
        self.engine = engine or HopfieldKrotovEngine(
            input_dim=input_dim, hidden_dim=hidden_dim
        )
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim

    def initialize_population(self) -> List[HopfieldKrotovNeuronState]:
        import random

        states = []
        for _ in range(self.hidden_dim):
            w_in = [random.gauss(0, 0.01) for _ in range(self.input_dim)]
            w_out = [random.gauss(0, 0.01) for _ in range(self.input_dim)]
            states.append(
                HopfieldKrotovNeuronState(
                    weights_in=w_in,
                    weights_out=w_out,
                    bias=0.0,
                )
            )
        return states

    def train(
        self,
        states: List[HopfieldKrotovNeuronState],
        dataset: List[List[float]],
        epochs: int = 1,
    ) -> HopfieldKrotovTrainingResult:
        total_error = 0.0
        count = 0
        for _ in range(epochs):
            for sample in dataset:
                states = self.engine.train_step(states, sample)
                hidden = self.engine.compute_hidden_activations(states, sample)
                output = self.engine.compute_output(states, hidden)
                error = sum((o - s) ** 2 for o, s in zip(output, sample)) / len(sample)
                total_error += error
                count += 1
        mean_error = total_error / count if count else 0.0
        return HopfieldKrotovTrainingResult(
            final_states=states,
            mean_reconstruction_error=mean_error,
        )
