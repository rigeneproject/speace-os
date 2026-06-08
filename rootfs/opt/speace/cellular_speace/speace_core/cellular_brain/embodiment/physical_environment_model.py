"""Persistent model of SPEACE's physical body (the computer it runs on)."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np


class PhysicalEnvironmentModel:
    """
    Discrete-time continuous-state model of the machine SPEACE runs on.

    Maintains an 8-dimensional state vector representing physical sensors,
    learns transition dynamics via online gradient descent, and persists
    history to JSONL.  It exposes ``predict_next_state`` and
    ``get_prediction_error`` so that :class:`ActiveInferenceEngine` can use
    it as an observation model.
    """

    STATE_KEYS = [
        "cpu_avg",
        "mem_used",
        "disk_used",
        "net_in",
        "net_out",
        "temp_avg",
        "process_count",
        "battery_level",
    ]
    STATE_DIM = len(STATE_KEYS)

    def __init__(
        self,
        base_path: str = "data/embodiment",
        learning_rate: float = 0.01,
        history_limit: int = 10000,
        error_window: int = 100,
    ) -> None:
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.state_path = self.base_path / "environment_state.jsonl"

        self.state: np.ndarray = np.zeros(self.STATE_DIM, dtype=float)
        self._last_predicted_state: np.ndarray = np.zeros(self.STATE_DIM, dtype=float)

        # Linear transition model: next = current + W @ current + b
        self.transition_weights: np.ndarray = np.zeros(
            (self.STATE_DIM, self.STATE_DIM), dtype=float
        )
        self.transition_bias: np.ndarray = np.zeros(self.STATE_DIM, dtype=float)

        # Action effect model: action features that match state dims are
        # mapped to state deltas through a learned weight matrix.
        self.action_effect_weights: np.ndarray = np.zeros(
            (self.STATE_DIM, self.STATE_DIM), dtype=float
        )

        self.learning_rate = learning_rate
        self.history: List[List[float]] = []
        self.prediction_errors: List[float] = []
        self.history_limit = history_limit
        self.error_window = error_window

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _sensor_to_vector(self, reading: Dict[str, float]) -> np.ndarray:
        """Extract an ordered state vector from a sensor dict."""
        return np.array([float(reading.get(k, 0.0)) for k in self.STATE_KEYS], dtype=float)

    def _vector_to_dict(self, vec: np.ndarray) -> Dict[str, float]:
        """Convert an ordered state vector back to a labelled dict."""
        return {k: float(vec[i]) for i, k in enumerate(self.STATE_KEYS)}

    def _clip_state(self, vec: np.ndarray) -> np.ndarray:
        """Physical quantities cannot be negative."""
        return np.clip(vec, 0.0, None)

    def _persist_state(self) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "state": self._vector_to_dict(self.state),
        }
        with open(self.state_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _record_error(self, error: float) -> None:
        self.prediction_errors.append(error)
        if len(self.prediction_errors) > 1000:
            self.prediction_errors = self.prediction_errors[-self.error_window :]

    # ------------------------------------------------------------------ #
    # Core API
    # ------------------------------------------------------------------ #

    def update(self, sensor_reading: Dict[str, float]) -> Dict[str, float]:
        """Incorporate a new sensor reading and update the internal state vector."""
        self.state = self._sensor_to_vector(sensor_reading)
        self._persist_state()
        self.history.append(self.state.tolist())
        if len(self.history) > self.history_limit:
            self.history = self.history[-(self.history_limit // 2) :]
        return self._vector_to_dict(self.state)

    def predict_next_state(
        self, action: Optional[Dict[str, float]] = None
    ) -> Dict[str, float]:
        """
        Predict the next physical state using the learned transition model.

        If *action* is provided, predicted deltas from the action are added.
        Supported action keys are numeric values that map onto state dimensions
        (e.g. ``{"process_count": 5.0}`` adds 5 to the predicted
        ``process_count``).
        """
        current = self.state.copy()
        predicted = current + self.transition_weights @ current + self.transition_bias

        if action is not None:
            action_vec = np.array(
                [float(action.get(k, 0.0)) for k in self.STATE_KEYS], dtype=float
            )
            predicted += self.action_effect_weights @ action_vec

        predicted = self._clip_state(predicted)
        self._last_predicted_state = predicted.copy()
        return self._vector_to_dict(predicted)

    def get_prediction_error(self, actual_state: Dict[str, float]) -> float:
        """
        Compute and record the squared prediction error between the last
        predicted state and the actual state.
        """
        actual = self._sensor_to_vector(actual_state)
        error = float(np.sum((actual - self._last_predicted_state) ** 2))
        self._record_error(error)
        return error

    def learn_transition(self, actual_state: Dict[str, float]) -> None:
        """
        Update internal transition weights using online gradient descent on
        the prediction error of the last predicted state.
        """
        actual = self._sensor_to_vector(actual_state)
        error_vec = actual - self._last_predicted_state

        # Gradient descent for next = current + W @ current + b
        self.transition_weights += self.learning_rate * np.outer(error_vec, self.state)
        self.transition_bias += self.learning_rate * error_vec

        error = float(np.sum(error_vec**2))
        self._record_error(error)

    def get_stability_score(self) -> float:
        """
        Return a stability score in ``[0, 1]``; higher means the environment
        is more predictable (lower recent prediction error).
        """
        if not self.prediction_errors:
            return 1.0
        recent = self.prediction_errors[-self.error_window :]
        mean_error = float(np.mean(recent))
        return 1.0 / (1.0 + mean_error)

    def get_anomaly_score(self) -> float:
        """
        Return the maximum absolute Z-score of the current state against the
        stored history.  Higher means the current state is more unusual.
        """
        if len(self.history) < 2:
            return 0.0
        history_arr = np.array(self.history, dtype=float)
        means = np.mean(history_arr, axis=0)
        stds = np.std(history_arr, axis=0)
        stds = np.where(stds < 1e-6, 1.0, stds)
        z_scores = np.abs((self.state - means) / stds)
        return float(np.max(z_scores))

    def get_state_summary(self) -> str:
        """Human-readable summary of the current physical state."""
        d = self._vector_to_dict(self.state)
        parts = [f"{k}={v:.2f}" for k, v in d.items()]
        return f"PhysicalEnvironmentModel({'; '.join(parts)})"
