from typing import Dict

import numpy as np


class PredictiveCodingEngine:
    """
    Hierarchical predictive coding engine.

    Layers are arranged sensory (0) -> association (1) -> abstract (2).
    Each layer receives a top-down prediction from higher layers and computes
    a bottom-up prediction error.
    """

    def __init__(self, learning_rate: float = 0.1):
        self.learning_rate = learning_rate
        self.layers: Dict[str, dict] = {}
        # weights[target_id][source_id] = weight matrix (target_dim, source_dim)
        self.weights: Dict[str, Dict[str, np.ndarray]] = {}

    def register_layer(self, layer_id: str, dim: int, level: int) -> None:
        """Register a new processing layer."""
        if level not in (0, 1, 2):
            raise ValueError(
                "level must be 0 (sensory), 1 (association), or 2 (abstract)"
            )
        self.layers[layer_id] = {
            "id": layer_id,
            "dim": dim,
            "level": level,
            "representation": np.zeros(dim),
            "prediction": np.zeros(dim),
            "prediction_error": np.zeros(dim),
        }
        self.weights[layer_id] = {}

    def set_connection(self, source_layer: str, target_layer: str) -> None:
        """Create a directional connection between two layers."""
        if source_layer not in self.layers:
            raise ValueError(f"Source layer '{source_layer}' not registered")
        if target_layer not in self.layers:
            raise ValueError(f"Target layer '{target_layer}' not registered")

        src = self.layers[source_layer]
        tgt = self.layers[target_layer]

        # Simple deterministic initialization: small positive weights scaled by source dim
        weight = np.ones((tgt["dim"], src["dim"])) / max(1, src["dim"])
        self.weights[target_layer][source_layer] = weight

    def predict(self, layer_id: str) -> np.ndarray:
        """
        Compute the top-down prediction for a layer using representations
        from all connected higher-level layers.
        """
        layer = self.layers[layer_id]
        pred = np.zeros(layer["dim"])
        for source_id, weight in self.weights[layer_id].items():
            source_layer = self.layers[source_id]
            if source_layer["level"] > layer["level"]:
                pred += weight @ source_layer["representation"]
        layer["prediction"] = pred
        return pred

    def update(self, layer_id: str, actual_input: np.ndarray) -> None:
        """
        Update a layer's representation given an actual bottom-up input.
        Computes prediction_error = |actual - prediction|.
        """
        layer = self.layers[layer_id]
        actual = np.asarray(actual_input, dtype=float)
        if actual.shape != (layer["dim"],):
            raise ValueError(
                f"actual_input shape {actual.shape} does not match layer dim {layer['dim']}"
            )
        pred = layer["prediction"]
        error = np.abs(actual - pred)
        layer["prediction_error"] = error
        # Simple gradient descent on prediction error
        layer["representation"] = (
            layer["representation"] + self.learning_rate * (actual - pred)
        )

    def step(self) -> None:
        """
        Propagate predictions down and errors up one full level.
        """
        if not self.layers:
            return

        # 1. Top-down prediction pass (high to low)
        sorted_layers = sorted(
            self.layers.values(), key=lambda l: l["level"], reverse=True
        )
        for layer in sorted_layers:
            self.predict(layer["id"])

        # 2. Bottom-up error propagation (low to high)
        incoming: Dict[str, np.ndarray] = {}
        for layer_id, layer in self.layers.items():
            incoming[layer_id] = np.zeros(layer["dim"])

        sorted_layers_asc = sorted(self.layers.values(), key=lambda l: l["level"])
        min_level = sorted_layers_asc[0]["level"]

        for layer in sorted_layers_asc:
            error = layer["prediction_error"]
            # Propagate error to connected higher layers via transposed weights
            for higher_id, weight in self.weights.get(layer["id"], {}).items():
                higher = self.layers[higher_id]
                if higher["level"] > layer["level"]:
                    incoming[higher_id] += weight.T @ error

        for layer_id, signal in incoming.items():
            if self.layers[layer_id]["level"] > min_level:
                self.update(layer_id, signal)
            else:
                # For the sensory layer, freeze representation but recompute error
                layer = self.layers[layer_id]
                layer["prediction_error"] = np.abs(
                    layer["representation"] - layer["prediction"]
                )

    def get_prediction_error(self, layer_id: str) -> float:
        """Return the total prediction error for a layer (sum of absolute errors)."""
        return float(np.sum(self.layers[layer_id]["prediction_error"]))

    def get_free_energy(self) -> float:
        """Return the sum of squared prediction errors across all layers."""
        total = 0.0
        for layer in self.layers.values():
            total += float(np.sum(layer["prediction_error"] ** 2))
        return total
