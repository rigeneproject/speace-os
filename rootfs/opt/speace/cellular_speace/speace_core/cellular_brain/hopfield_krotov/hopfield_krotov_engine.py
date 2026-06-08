from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class HopfieldKrotovNeuronState(BaseModel):
    weights_in: List[float] = []  # input -> hidden weights (flattened per neuron)
    weights_out: List[float] = []  # hidden -> output weights (flattened per neuron)
    bias: float = 0.0

    model_config = ConfigDict(arbitrary_types_allowed=True)


class HopfieldKrotovEngine:
    """Hopfield-Krotov 2019 unsupervised learning with competing hidden units.

    Uses lateral inhibition to enforce competition among hidden units.
    Weight update follows an anti-Hebbian / local learning rule combined
    with reconstruction error minimization.
    """

    def __init__(
        self,
        input_dim: int = 784,
        hidden_dim: int = 100,
        learning_rate: float = 0.01,
        inhibition_strength: float = 0.5,
        reconstruction_weight: float = 1.0,
    ):
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.learning_rate = learning_rate
        self.inhibition_strength = inhibition_strength
        self.reconstruction_weight = reconstruction_weight

    def _dot(self, w: List[float], x: List[float]) -> float:
        return sum(wi * xi for wi, xi in zip(w, x))

    def _subtract(self, a: List[float], b: List[float]) -> List[float]:
        return [ai - bi for ai, bi in zip(a, b)]

    def _scale(self, v: List[float], s: float) -> List[float]:
        return [vi * s for vi in v]

    def _relu(self, x: float) -> float:
        return max(0.0, x)

    def compute_hidden_activations(
        self,
        states: List[HopfieldKrotovNeuronState],
        inputs: List[float],
    ) -> List[float]:
        raw = []
        for state in states:
            z = self._dot(state.weights_in, inputs) + state.bias
            raw.append(z)
        # Apply lateral inhibition (soft competition)
        inhibited = []
        for i in range(len(states)):
            inhibition = sum(
                self.inhibition_strength * raw[j]
                for j in range(len(states))
                if j != i
            )
            val = self._relu(raw[i] - inhibition)
            inhibited.append(val)
        return inhibited

    def compute_output(
        self,
        states: List[HopfieldKrotovNeuronState],
        hidden_activations: List[float],
    ) -> List[float]:
        output = [0.0] * self.input_dim
        for state, h in zip(states, hidden_activations):
            for idx, w in enumerate(state.weights_out):
                output[idx] += w * h
        return output

    def update_weights(
        self,
        states: List[HopfieldKrotovNeuronState],
        inputs: List[float],
        hidden_activations: List[float],
        output: List[float],
    ) -> List[HopfieldKrotovNeuronState]:
        error = self._subtract(output, inputs)
        new_states = []
        for state, h in zip(states, hidden_activations):
            # Update input weights: anti-Hebbian + reconstruction gradient
            # dW_in = -lr * (h * (input - W_in^T input) + recon_weight * error * h)
            # Simplified: use reconstruction error projected back
            recon_grad_in = self._scale(inputs, -self.learning_rate * h * self.reconstruction_weight)
            # Local competition term: if h is high, strengthen selectivity
            local_grad_in = self._scale(inputs, self.learning_rate * h * (1.0 - h))
            new_w_in = [
                wi + gi + li
                for wi, gi, li in zip(state.weights_in, recon_grad_in, local_grad_in)
            ]
            # Update output weights: standard gradient descent on reconstruction error
            grad_out = self._scale(error, self.learning_rate * h)
            new_w_out = [
                wo + go
                for wo, go in zip(state.weights_out, grad_out)
            ]
            new_states.append(
                HopfieldKrotovNeuronState(
                    weights_in=new_w_in,
                    weights_out=new_w_out,
                    bias=state.bias,
                )
            )
        return new_states

    def train_step(
        self,
        states: List[HopfieldKrotovNeuronState],
        inputs: List[float],
    ) -> List[HopfieldKrotovNeuronState]:
        hidden = self.compute_hidden_activations(states, inputs)
        output = self.compute_output(states, hidden)
        return self.update_weights(states, inputs, hidden, output)
