import time
from typing import Any, Dict, List, Optional

import numpy as np

from speace_core.cellular_brain.embodiment.embodied_action_actuator import (
    ActionOutcome,
)


class EmbodimentMonitor:
    """T72 — Tracks sensorimotor loop closure quality.

    Metrics:
      - loop_closure_latency_ms: time from action to sensor detection
      - prediction_accuracy: how well the model predicts real outcomes
      - action_success_rate: % of actions that achieved intended effect
      - sensorimotor_coherence: correlation between predicted and observed changes
      - embodiment_depth: 0.0 (no sensors) to 1.0 (full closed loop)
    """

    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self._latencies: List[float] = []
        self._prediction_accuracies: List[float] = []
        self._action_outcomes: List[bool] = []
        self._coherence_values: List[float] = []
        self._embodiment_depths: List[float] = []
        self._last_action_time: Optional[float] = None
        self._tick_count: int = 0

    @staticmethod
    def _flatten_snapshot(snapshot: Dict[str, Any]) -> Dict[str, float]:
        """Flatten a nested sensor snapshot to scalar values."""
        flat: Dict[str, float] = {}
        for key, val in snapshot.items():
            if isinstance(val, (int, float)):
                flat[key] = float(val)
            elif isinstance(val, dict):
                for sub_key, sub_val in val.items():
                    if isinstance(sub_val, (int, float)):
                        flat[f"{key}.{sub_key}"] = float(sub_val)
        return flat

    def evaluate_tick(
        self,
        sensor_before: Dict[str, Any],
        action: Optional[Dict[str, Any]],
        sensor_after: Dict[str, Any],
        prediction: Optional[Dict[str, float]] = None,
    ) -> Dict[str, float]:
        """Evaluate one complete sensorimotor tick."""
        self._tick_count += 1

        before_values = self._flatten_snapshot(sensor_before)
        after_values = self._flatten_snapshot(sensor_after)

        # 1. Loop closure latency
        latency_ms = 0.0
        if action and self._last_action_time is not None:
            latency_ms = (time.time() - self._last_action_time) * 1000.0
            self._latencies.append(latency_ms)
            if len(self._latencies) > self.window_size:
                self._latencies.pop(0)

        # 2. Prediction accuracy
        pred_acc = 0.0
        if prediction:
            errors = []
            for sid, predicted_value in prediction.items():
                actual = after_values.get(sid)
                if actual is not None:
                    if abs(predicted_value) > 1e-9 or abs(actual) > 1e-9:
                        rel_error = abs(actual - predicted_value) / max(abs(actual), abs(predicted_value), 1.0)
                        errors.append(1.0 - rel_error)
            if errors:
                pred_acc = float(np.mean(errors))
            else:
                pred_acc = 1.0
        self._prediction_accuracies.append(pred_acc)
        if len(self._prediction_accuracies) > self.window_size:
            self._prediction_accuracies.pop(0)

        # 3. Action success rate
        action_success = False
        if action:
            # Heuristic: if sensor values changed after action, assume success
            changes = [
                abs(after_values.get(sid, 0.0) - before_values.get(sid, 0.0))
                for sid in set(before_values) | set(after_values)
            ]
            action_success = any(c > 1e-6 for c in changes)
            self._action_outcomes.append(action_success)
            if len(self._action_outcomes) > self.window_size:
                self._action_outcomes.pop(0)
            self._last_action_time = time.time()

        # 4. Sensorimotor coherence
        coherence = 0.0
        if prediction and before_values and after_values:
            predicted_changes = []
            observed_changes = []
            for sid in set(prediction.keys()) & set(before_values.keys()) & set(after_values.keys()):
                predicted_changes.append(prediction[sid] - before_values.get(sid, 0.0))
                observed_changes.append(after_values.get(sid, 0.0) - before_values.get(sid, 0.0))
            if len(predicted_changes) >= 2 and len(observed_changes) >= 2:
                try:
                    corr = np.corrcoef(predicted_changes, observed_changes)[0, 1]
                    coherence = max(-1.0, min(1.0, float(corr))) if not np.isnan(corr) else 0.0
                except Exception:
                    coherence = 0.0
        self._coherence_values.append(coherence)
        if len(self._coherence_values) > self.window_size:
            self._coherence_values.pop(0)

        # 5. Embodiment depth
        sensor_count = len(after_values)
        has_action = bool(action)
        has_prediction = prediction is not None
        depth = 0.0
        if sensor_count > 0:
            depth += 0.2
        if has_action:
            depth += 0.4
        if has_prediction:
            depth += 0.4
        depth = min(1.0, depth)
        self._embodiment_depths.append(depth)
        if len(self._embodiment_depths) > self.window_size:
            self._embodiment_depths.pop(0)

        return {
            "loop_closure_latency_ms": latency_ms,
            "prediction_accuracy": pred_acc,
            "action_success": action_success,
            "sensorimotor_coherence": coherence,
            "embodiment_depth": depth,
        }

    def get_embodiment_report(self) -> Dict[str, Any]:
        """Return all embodiment metrics."""
        return {
            "loop_closure_latency_ms": self._average(self._latencies),
            "prediction_accuracy": self._average(self._prediction_accuracies),
            "action_success_rate": self._average_bool(self._action_outcomes),
            "sensorimotor_coherence": self._average(self._coherence_values),
            "embodiment_depth": self._average(self._embodiment_depths),
            "tick_count": self._tick_count,
            "window_size": self.window_size,
        }

    @staticmethod
    def _average(values: List[float]) -> float:
        return float(np.mean(values)) if values else 0.0

    @staticmethod
    def _average_bool(values: List[bool]) -> float:
        return float(np.mean(values)) if values else 0.0
