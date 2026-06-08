from typing import List

from pydantic import BaseModel, ConfigDict


class BCMNeuronState(BaseModel):
    weights: List[float] = []
    theta_m: float = 0.0  # sliding threshold (moving average of y^2)
    selectivity_index: float = 0.0
    activation_history: List[float] = []

    model_config = ConfigDict(arbitrary_types_allowed=True)


class BCMSelectivityEngine:
    """BCM (Bienenstock-Cooper-Munro) selectivity engine.

    Rule: dw = eta * x * y * (y - theta_m)
    where theta_m is a moving average of y^2 over recent activity.
    """

    def __init__(
        self,
        learning_rate: float = 0.01,
        theta_decay: float = 0.9,
        history_window: int = 100,
    ):
        self.learning_rate = learning_rate
        self.theta_decay = theta_decay
        self.history_window = history_window

    def compute_activation(self, weights: List[float], inputs: List[float]) -> float:
        if len(weights) != len(inputs):
            raise ValueError("weights and inputs must have the same length")
        return sum(w * x for w, x in zip(weights, inputs))

    def update_threshold(self, state: BCMNeuronState, activation: float) -> float:
        # Exponential moving average of activation^2
        new_theta = (
            self.theta_decay * state.theta_m
            + (1 - self.theta_decay) * (activation ** 2)
        )
        return new_theta

    def compute_weight_update(
        self,
        weights: List[float],
        inputs: List[float],
        activation: float,
        theta_m: float,
    ) -> List[float]:
        factor = self.learning_rate * activation * (activation - theta_m)
        return [factor * x for x in inputs]

    def update_neuron(
        self,
        state: BCMNeuronState,
        inputs: List[float],
    ) -> BCMNeuronState:
        activation = self.compute_activation(state.weights, inputs)
        new_theta = self.update_threshold(state, activation)
        dw = self.compute_weight_update(
            state.weights, inputs, activation, new_theta
        )
        new_weights = [w + dw_i for w, dw_i in zip(state.weights, dw)]

        # Update activation history for selectivity calculation
        history = state.activation_history + [activation]
        if len(history) > self.history_window:
            history = history[-self.history_window:]

        # Selectivity index = variance of activations / mean^2 (or CV^2)
        if len(history) > 1:
            mean_a = sum(history) / len(history)
            var_a = sum((a - mean_a) ** 2 for a in history) / len(history)
            selectivity = var_a / (mean_a ** 2 + 1e-8)
        else:
            selectivity = 0.0

        return BCMNeuronState(
            weights=new_weights,
            theta_m=new_theta,
            selectivity_index=selectivity,
            activation_history=history,
        )

    def train_neuron(
        self,
        state: BCMNeuronState,
        inputs: List[float],
        steps: int = 1,
    ) -> BCMNeuronState:
        for _ in range(steps):
            state = self.update_neuron(state, inputs)
        return state
