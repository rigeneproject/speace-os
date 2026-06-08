"""DigitalTwinModel — lightweight model of SPEACE's local machine body.

Combines CyberPhysicalSensorArray and PhysicalEnvironmentModel into a coherent
observable body that can be simulated in a sandbox.
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


class DigitalTwinModel:
    """A persistent digital twin of the machine SPEACE runs on.

    Maintains:
    - current sensor snapshot
    - predicted next state from PhysicalEnvironmentModel
    - anomaly / stability scores
    - causal hypotheses (what changed → what happened)
    """

    def __init__(
        self,
        sensor_array: Any,
        environment_model: Any,
        data_root: str = "data/embodiment",
    ) -> None:
        self._sensor_array = sensor_array
        self._environment_model = environment_model
        self._data_root = Path(data_root)
        self._data_root.mkdir(parents=True, exist_ok=True)
        self._hypotheses_path = self._data_root / "causal_hypotheses.jsonl"

        self._last_snapshot: Optional[Dict[str, Any]] = None
        self._last_delta: Optional[Dict[str, Any]] = None
        self._anomaly_history: List[float] = []
        self._stability_history: List[float] = []

    # ------------------------------------------------------------------ #
    # Observation
    # ------------------------------------------------------------------ #

    def observe(self) -> Dict[str, Any]:
        """Read current sensors, update environment model, return twin state."""
        snapshot = self._sensor_array.read_all()
        self._last_snapshot = snapshot

        # Flatten for PhysicalEnvironmentModel
        flat = self._flatten_snapshot(snapshot)
        self._environment_model.update(flat)
        predicted = self._environment_model.predict_next_state()
        error = self._environment_model.get_prediction_error(flat)
        self._environment_model.learn_transition(flat)

        stability = self._environment_model.get_stability_score()
        anomaly = self._environment_model.get_anomaly_score()
        self._stability_history.append(stability)
        self._anomaly_history.append(anomaly)
        if len(self._stability_history) > 1000:
            self._stability_history = self._stability_history[-500:]
            self._anomaly_history = self._anomaly_history[-500:]

        return {
            "timestamp": time.time(),
            "sensor_snapshot": snapshot,
            "environment_state": flat,
            "predicted_next": predicted,
            "prediction_error": error,
            "stability_score": stability,
            "anomaly_score": anomaly,
            "summary": self._environment_model.get_state_summary(),
        }

    def observe_delta(self) -> Optional[Dict[str, Any]]:
        """Return the delta between current and previous sensor reading."""
        delta = self._sensor_array.get_sensor_delta()
        self._last_delta = delta
        return delta

    # ------------------------------------------------------------------ #
    # Simulation
    # ------------------------------------------------------------------ #

    def simulate_action(
        self,
        action: Dict[str, float],
        horizon_ticks: int = 5,
    ) -> Dict[str, Any]:
        """Run a simulated action in the digital twin and observe consequences.

        Args:
            action: dict of state deltas (e.g. {"cpu_avg": 20.0})
            horizon_ticks: how many simulated steps forward

        Returns:
            Simulation trace with predicted states and detected causal links.
        """
        trace: List[Dict[str, Any]] = []
        current = self._environment_model._vector_to_dict(self._environment_model.state.copy())
        # Copy action so caller's dict is not mutated
        working_action = dict(action)

        for tick in range(1, horizon_ticks + 1):
            predicted = self._environment_model.predict_next_state(working_action)
            trace.append({"tick": tick, "state": predicted})
            # Simulate drift: decay action effect over time
            for k in working_action:
                working_action[k] *= 0.9

        # Detect which state variables changed most
        changes = {}
        if trace:
            final = trace[-1]["state"]
            for k in current:
                changes[k] = round(final.get(k, 0.0) - current.get(k, 0.0), 4)

        return {
            "action": action,
            "horizon_ticks": horizon_ticks,
            "initial_state": current,
            "trace": trace,
            "changes": changes,
            "primary_effects": sorted(changes.items(), key=lambda x: abs(x[1]), reverse=True)[:3],
        }

    # ------------------------------------------------------------------ #
    # Causal hypotheses
    # ------------------------------------------------------------------ #

    def record_hypothesis(
        self,
        cause: str,
        effect: str,
        confidence: float,
        evidence_count: int = 1,
    ) -> None:
        """Append a causal hypothesis to persistent storage."""
        entry = {
            "timestamp": time.time(),
            "cause": cause,
            "effect": effect,
            "confidence": round(confidence, 4),
            "evidence_count": evidence_count,
        }
        with self._hypotheses_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_hypotheses(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Read recent causal hypotheses."""
        if not self._hypotheses_path.exists():
            return []
        lines = self._hypotheses_path.read_text(encoding="utf-8").strip().split("\n")
        hypotheses = []
        for line in lines[-limit:]:
            try:
                hypotheses.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return hypotheses

    def infer_hypotheses_from_delta(self) -> List[Dict[str, Any]]:
        """Look at the latest sensor delta and generate simple causal hypotheses."""
        if self._last_delta is None:
            return []
        hypotheses = []
        for key in ("cpu", "memory", "temperature"):
            sub = self._last_delta.get(key, {})
            for sub_key, delta_val in sub.items():
                if isinstance(delta_val, (int, float)) and abs(delta_val) > 0.1:
                    # Simple heuristic: correlate with process_count_delta
                    proc_delta = self._last_delta.get("process", {}).get("process_count_delta", 0)
                    if abs(proc_delta) > 0:
                        confidence = min(1.0, abs(delta_val) / 50.0)
                        hypotheses.append({
                            "cause": f"process_count_change({proc_delta})",
                            "effect": f"{key}.{sub_key}_delta({delta_val})",
                            "confidence": round(confidence, 4),
                        })
                        self.record_hypothesis(
                            cause=f"process_count_change",
                            effect=f"{key}.{sub_key}",
                            confidence=confidence,
                        )
        return hypotheses

    # ------------------------------------------------------------------ #
    # Summary
    # ------------------------------------------------------------------ #

    def summary(self) -> Dict[str, Any]:
        return {
            "has_snapshot": self._last_snapshot is not None,
            "has_delta": self._last_delta is not None,
            "stability_latest": round(self._stability_history[-1], 4) if self._stability_history else None,
            "anomaly_latest": round(self._anomaly_history[-1], 4) if self._anomaly_history else None,
            "hypothesis_count": len(self.get_hypotheses(limit=10000)),
            "environment_summary": self._environment_model.get_state_summary() if self._environment_model else None,
        }

    # ------------------------------------------------------------------ #
    # Static helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _flatten_snapshot(snapshot: Dict[str, Any]) -> Dict[str, float]:
        """Flatten a CyberPhysicalSensorArray snapshot into PhysicalEnvironmentModel keys."""
        cpu = snapshot.get("cpu", {})
        mem = snapshot.get("memory", {})
        disk = snapshot.get("disk", {})
        net = snapshot.get("network", {})
        temp = snapshot.get("temperature", {})
        proc = snapshot.get("process", {})
        power = snapshot.get("power", {})

        drives = disk.get("drives", [{}])
        drive = drives[0] if drives else {}

        return {
            "cpu_avg": float(cpu.get("usage_percent_normalized", 0.0) or 0.0) * 100.0,
            "mem_used": float(mem.get("percent_normalized", 0.0) or 0.0) * 100.0,
            "disk_used": float(drive.get("percent_normalized", 0.0) or 0.0) * 100.0,
            "net_in": float(net.get("bytes_received", 0.0) or 0.0) / 1e6,
            "net_out": float(net.get("bytes_sent", 0.0) or 0.0) / 1e6,
            "temp_avg": float(temp.get("cpu_celsius_normalized", 0.0) or 0.0) * 100.0,
            "process_count": float(proc.get("process_count", 0.0) or 0.0),
            "battery_level": float(power.get("battery_percent_normalized", 0.0) or 0.0) * 100.0,
        }
