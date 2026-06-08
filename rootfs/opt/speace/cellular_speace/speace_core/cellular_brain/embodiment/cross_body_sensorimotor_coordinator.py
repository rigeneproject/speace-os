"""CrossBodySensorimotorCoordinator — coordinates sensorimotor loops across multiple bodies."""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np


@dataclass
class BodyLoop:
    """Per-body sensorimotor loop configuration."""

    body_id: str
    sensor_array: Any  # object with .read() -> Dict[str, Any]
    environment_model: Any  # object with .update() and .predict_next_state()
    actuator: Any  # object with .act()
    history: List[Dict[str, Any]] = field(default_factory=list)
    history_limit: int = 1000


class CrossBodySensorimotorCoordinator:
    """Coordinates sensorimotor loops across multiple embodied bodies.

    Each body maintains its own sensor array, environment model, and actuator.
    The coordinator advances all loops in discrete time steps and produces a
    unified organismic view.
    """

    def __init__(self) -> None:
        self._loops: Dict[str, BodyLoop] = {}
        self._body_baselines: Dict[str, Dict[str, float]] = {}

    # ------------------------------------------------------------------ #
    # Registration
    # ------------------------------------------------------------------ #

    def register_body_loop(
        self,
        body_id: str,
        sensor_array: Any,
        environment_model: Any,
        actuator: Any,
    ) -> None:
        """Register a sensorimotor loop for a body."""
        self._loops[body_id] = BodyLoop(
            body_id=body_id,
            sensor_array=sensor_array,
            environment_model=environment_model,
            actuator=actuator,
        )

    def unregister_body_loop(self, body_id: str) -> bool:
        """Remove a body's sensorimotor loop."""
        if body_id in self._loops:
            del self._loops[body_id]
            return True
        return False

    # ------------------------------------------------------------------ #
    # Stepping
    # ------------------------------------------------------------------ #

    def step_body(self, body_id: str, dt: float = 1.0) -> Dict[str, Any]:
        """Advance the sensorimotor loop for a single body.

        The generic protocol expected is:
          - sensor_array.read()  -> sensor snapshot dict
          - environment_model.update(snapshot)  -> predicted / learned state
          - environment_model.predict_next_state()  -> predicted next state
          - actuator.act(prediction)  -> action outcome dict
        """
        loop = self._loops.get(body_id)
        if loop is None:
            return {
                "status": "error",
                "body_id": body_id,
                "error": "Body loop not registered",
            }

        # Sense
        sensor_snapshot: Dict[str, Any] = {}
        if hasattr(loop.sensor_array, "read"):
            sensor_snapshot = loop.sensor_array.read()
        elif hasattr(loop.sensor_array, "get_cpu_state"):
            # CyberPhysicalSensorArray fallback
            sensor_snapshot = loop.sensor_array.get_cpu_state()
        else:
            sensor_snapshot = {}

        # Update environment model
        predicted_state: Dict[str, Any] = {}
        if hasattr(loop.environment_model, "update"):
            loop.environment_model.update(sensor_snapshot)
        if hasattr(loop.environment_model, "predict_next_state"):
            predicted_state = loop.environment_model.predict_next_state()

        # Act
        action_outcome: Dict[str, Any] = {}
        if hasattr(loop.actuator, "act"):
            action_outcome = loop.actuator.act(predicted_state)
        elif hasattr(loop.actuator, "execute_action"):
            action_outcome = loop.actuator.execute_action("predicted", predicted_state)

        tick_record = {
            "timestamp": time.time(),
            "dt": dt,
            "sensor_snapshot": sensor_snapshot,
            "predicted_state": predicted_state,
            "action_outcome": action_outcome,
        }
        loop.history.append(tick_record)
        if len(loop.history) > loop.history_limit:
            loop.history = loop.history[-loop.history_limit :]

        return {
            "status": "ok",
            "body_id": body_id,
            "sensor_snapshot": sensor_snapshot,
            "predicted_state": predicted_state,
            "action_outcome": action_outcome,
        }

    def step_all(self, dt: float = 1.0) -> Dict[str, Dict[str, Any]]:
        """Advance every registered body's sensorimotor loop."""
        results: Dict[str, Dict[str, Any]] = {}
        for body_id in self._loops:
            results[body_id] = self.step_body(body_id, dt=dt)
        return results

    # ------------------------------------------------------------------ #
    # Global state
    # ------------------------------------------------------------------ #

    def get_global_sensorimotor_state(self) -> Dict[str, Any]:
        """Aggregate all body states into a unified organismic view.

        Computes per-sensor averages, action success rates, and a global
        coherence score.
        """
        total_sensor_readings: List[Dict[str, Any]] = []
        total_action_outcomes: List[bool] = []
        body_summaries: Dict[str, Dict[str, Any]] = {}

        for body_id, loop in self._loops.items():
            if not loop.history:
                continue
            latest = loop.history[-1]
            total_sensor_readings.append(latest["sensor_snapshot"])
            action_ok = bool(latest.get("action_outcome", {}).get("executed", False))
            total_action_outcomes.append(action_ok)
            body_summaries[body_id] = {
                "latest_sensor": latest["sensor_snapshot"],
                "latest_prediction": latest["predicted_state"],
                "tick_count": len(loop.history),
            }

        # Flatten and average numeric sensor values across bodies
        sensor_values: Dict[str, List[float]] = {}
        for reading in total_sensor_readings:
            flat = self._flatten(reading)
            for k, v in flat.items():
                sensor_values.setdefault(k, []).append(v)

        averaged = {k: float(np.mean(v)) for k, v in sensor_values.items()}
        success_rate = (
            float(np.mean(total_action_outcomes)) if total_action_outcomes else 0.0
        )

        return {
            "body_count": len(self._loops),
            "active_bodies": len(body_summaries),
            "global_sensor_average": averaged,
            "global_action_success_rate": success_rate,
            "body_summaries": body_summaries,
        }

    @staticmethod
    def _flatten(d: Dict[str, Any], prefix: str = "") -> Dict[str, float]:
        """Recursively flatten nested dicts to scalar floats."""
        result: Dict[str, float] = {}
        for key, val in d.items():
            full = f"{prefix}.{key}" if prefix else key
            if isinstance(val, (int, float)):
                result[full] = float(val)
            elif isinstance(val, dict):
                result.update(CrossBodySensorimotorCoordinator._flatten(val, full))
        return result

    # ------------------------------------------------------------------ #
    # Stress detection
    # ------------------------------------------------------------------ #

    def detect_body_stress(self, body_id: str) -> Dict[str, Any]:
        """Compare a body's current state to its historical baseline.

        Returns stress metrics: anomaly score, deviation from baseline,
        and a stress flag.
        """
        loop = self._loops.get(body_id)
        if loop is None or not loop.history:
            return {
                "status": "error",
                "body_id": body_id,
                "error": "No history available",
            }

        # Build baseline from first half of history
        history = loop.history
        split = max(1, len(history) // 2)
        baseline_records = history[:split]
        current_records = history[split:]
        if not current_records:
            current_records = history[-1:]

        baseline_flat = [self._flatten(r["sensor_snapshot"]) for r in baseline_records]
        current_flat = [self._flatten(r["sensor_snapshot"]) for r in current_records]

        if not baseline_flat or not current_flat:
            return {
                "status": "ok",
                "body_id": body_id,
                "stress_detected": False,
                "anomaly_score": 0.0,
                "reason": "insufficient_history",
            }

        baseline_arr = np.array(
            [[b.get(k, 0.0) for k in baseline_flat[0]] for b in baseline_flat], dtype=float
        )
        current_arr = np.array(
            [[c.get(k, 0.0) for k in baseline_flat[0]] for c in current_flat], dtype=float
        )

        baseline_mean = np.mean(baseline_arr, axis=0)
        baseline_std = np.std(baseline_arr, axis=0)
        baseline_std = np.where(baseline_std < 1e-6, 1.0, baseline_std)

        current_mean = np.mean(current_arr, axis=0)
        z_scores = np.abs((current_mean - baseline_mean) / baseline_std)
        max_z = float(np.max(z_scores)) if len(z_scores) else 0.0
        stress_threshold = 2.0

        return {
            "status": "ok",
            "body_id": body_id,
            "stress_detected": max_z > stress_threshold,
            "anomaly_score": max_z,
            "z_scores": {k: float(v) for k, v in zip(baseline_flat[0].keys(), z_scores)},
            "baseline_mean": {k: float(v) for k, v in zip(baseline_flat[0].keys(), baseline_mean)},
            "current_mean": {k: float(v) for k, v in zip(baseline_flat[0].keys(), current_mean)},
        }
