"""AlertEngine — read-only organism stability telemetry and alerting layer (T102).

Evaluates organism state against configurable thresholds, generates alerts
with severity levels, persists them to data/monitoring/alerts.jsonl, and
computes a global health score.  No automatic actions are taken.
"""

import json
import pathlib
import time
from typing import Any, Dict, List, Optional


class AlertEngine:
    """Generates alerts and health scores from organismic state."""

    def __init__(
        self,
        thresholds: Optional[Dict[str, Any]] = None,
        alerts_path: str = "data/monitoring/alerts.jsonl",
        max_history: int = 10000,
    ) -> None:
        defaults = self._default_thresholds()
        if thresholds:
            defaults.update(thresholds)
        self.thresholds = defaults
        self.alerts_path = pathlib.Path(alerts_path)
        self.alerts_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_history = max_history

    @staticmethod
    def _default_thresholds() -> Dict[str, Any]:
        return {
            "chaos_warning": 0.4,
            "chaos_critical": 0.8,
            "rigidity_warning": 0.3,
            "rigidity_critical": 0.7,
            "drift_warning": 0.2,
            "drift_critical": 0.5,
            "prediction_error_warning": 5.0,
            "prediction_error_critical": 20.0,
            "coherence_phi_warning": 0.2,
            "coherence_phi_critical": 0.1,
            "branching_deviation_warning": 0.2,
            "branching_deviation_critical": 0.4,
            "safety_risk_warning": 1,
            "safety_risk_critical": 2,
            "identity_divergence_warning": 1.0,
            "drive_instability_warning": 0.5,
            "drive_instability_critical": 0.8,
        }

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _persist(self, alert: Dict[str, Any]) -> None:
        try:
            with self.alerts_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(alert, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _read_alerts(self, limit: int = 100) -> List[Dict[str, Any]]:
        if not self.alerts_path.exists():
            return []
        alerts: List[Dict[str, Any]] = []
        try:
            with self.alerts_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        alerts.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            return []
        # trim if oversized (simple line-count heuristic)
        if len(alerts) > self.max_history:
            alerts = alerts[-self.max_history:]
            try:
                with self.alerts_path.open("w", encoding="utf-8") as f:
                    for a in alerts:
                        f.write(json.dumps(a, ensure_ascii=False) + "\n")
            except OSError:
                pass
        return alerts[-limit:] if limit else alerts

    # ------------------------------------------------------------------ #
    # Evaluation
    # ------------------------------------------------------------------ #

    def evaluate(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Evaluate state and return new alerts for this tick."""
        alerts: List[Dict[str, Any]] = []
        ts = time.time()

        body = state.get("body", {})
        cognition = state.get("cognition", {})
        dynamics = state.get("dynamics", {})
        embodiment = state.get("embodiment", {})
        safety = state.get("safety", {})
        identity = state.get("identity", {})
        drives = state.get("drives", {})

        phi = cognition.get("self_model", {}).get("coherence_phi", 0.0)
        chaos = dynamics.get("chaos_score", 0.0)
        rigidity = dynamics.get("rigidity_score", 0.0)
        drift = dynamics.get("drift", 0.0)
        pred_err = embodiment.get("prediction_error", 0.0)
        branching = dynamics.get("criticality", {}).get("branching_ratio", 0.0)

        t = self.thresholds

        # Safety risk (mapped from string to numeric)
        risk_map = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        safety_risk = risk_map.get(safety.get("risk_level", "low"), 0)

        # Identity divergence
        divergence_detected = identity.get("divergence_detected", False)
        divergence_score = 1.0 if divergence_detected else 0.0

        # Drive instability (max urgency across drives)
        drives_list = drives.get("drives", [])
        drive_instability = max((d.get("urgency", 0.0) for d in drives_list), default=0.0)

        # Chaos
        if chaos >= t["chaos_critical"]:
            alerts.append(self._alert("chaos_critical", "critical", f"chaos_score={fmt(chaos)}", ts, state))
        elif chaos >= t["chaos_warning"]:
            alerts.append(self._alert("chaos_warning", "warning", f"chaos_score={fmt(chaos)}", ts, state))

        # Rigidity
        if rigidity >= t["rigidity_critical"]:
            alerts.append(self._alert("rigidity_critical", "critical", f"rigidity_score={fmt(rigidity)}", ts, state))
        elif rigidity >= t["rigidity_warning"]:
            alerts.append(self._alert("rigidity_warning", "warning", f"rigidity_score={fmt(rigidity)}", ts, state))

        # Drift
        if abs(drift) >= t["drift_critical"]:
            alerts.append(self._alert("drift_critical", "critical", f"drift={fmt(drift)}", ts, state))
        elif abs(drift) >= t["drift_warning"]:
            alerts.append(self._alert("drift_warning", "warning", f"drift={fmt(drift)}", ts, state))

        # Prediction error
        if pred_err >= t["prediction_error_critical"]:
            alerts.append(self._alert("prediction_error_critical", "critical", f"prediction_error={fmt(pred_err)}", ts, state))
        elif pred_err >= t["prediction_error_warning"]:
            alerts.append(self._alert("prediction_error_warning", "warning", f"prediction_error={fmt(pred_err)}", ts, state))

        # Coherence phi
        if phi <= t["coherence_phi_critical"]:
            alerts.append(self._alert("coherence_phi_critical", "critical", f"coherence_phi={fmt(phi)}", ts, state))
        elif phi <= t["coherence_phi_warning"]:
            alerts.append(self._alert("coherence_phi_warning", "warning", f"coherence_phi={fmt(phi)}", ts, state))

        # Branching ratio deviation
        if branching > 0:
            dev = abs(branching - 1.0)
            if dev >= t["branching_deviation_critical"]:
                alerts.append(self._alert("branching_critical", "critical", f"branching_ratio={fmt(branching)}", ts, state))
            elif dev >= t["branching_deviation_warning"]:
                alerts.append(self._alert("branching_warning", "warning", f"branching_ratio={fmt(branching)}", ts, state))

        # Safety risk
        if safety_risk >= t["safety_risk_critical"]:
            alerts.append(self._alert("safety_risk_critical", "critical", f"safety_risk={safety_risk}", ts, state))
        elif safety_risk >= t["safety_risk_warning"]:
            alerts.append(self._alert("safety_risk_warning", "warning", f"safety_risk={safety_risk}", ts, state))

        # Identity divergence
        if divergence_score >= t["identity_divergence_warning"]:
            alerts.append(self._alert("identity_divergence_warning", "warning", f"divergence_detected={divergence_detected}", ts, state))

        # Drive instability
        if drive_instability >= t["drive_instability_critical"]:
            alerts.append(self._alert("drive_instability_critical", "critical", f"drive_instability={fmt(drive_instability)}", ts, state))
        elif drive_instability >= t["drive_instability_warning"]:
            alerts.append(self._alert("drive_instability_warning", "warning", f"drive_instability={fmt(drive_instability)}", ts, state))

        # Persist
        for a in alerts:
            self._persist(a)

        return alerts

    def health_score(self, state: Dict[str, Any]) -> float:
        """Compute a global health score in [0, 1] using Φ/ΔD heuristic.

        Higher is healthier.
        """
        cognition = state.get("cognition", {})
        dynamics = state.get("dynamics", {})
        embodiment = state.get("embodiment", {})

        phi = cognition.get("self_model", {}).get("coherence_phi", 0.0)
        chaos = dynamics.get("chaos_score", 0.0)
        rigidity = dynamics.get("rigidity_score", 0.0)
        drift = abs(dynamics.get("drift", 0.0))
        pred_err = embodiment.get("prediction_error", 0.0)

        # Base from coherence (Φ)
        score = phi

        # Penalties
        score *= max(0.0, 1.0 - chaos)
        score *= max(0.0, 1.0 - rigidity)
        score *= max(0.0, 1.0 - min(drift, 1.0))
        score *= max(0.0, 1.0 - min(pred_err / 100.0, 1.0))

        # Safety risk penalty
        risk_map = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        safety_risk = risk_map.get(state.get("safety", {}).get("risk_level", "low"), 0)
        score *= max(0.0, 1.0 - safety_risk / 3.0)

        # Identity divergence penalty
        if state.get("identity", {}).get("divergence_detected", False):
            score *= 0.7

        # Drive instability penalty
        drives_list = state.get("drives", {}).get("drives", [])
        drive_instability = max((d.get("urgency", 0.0) for d in drives_list), default=0.0)
        score *= max(0.0, 1.0 - min(drive_instability, 1.0))

        # Clamp
        return max(0.0, min(1.0, score))

    def recent_alerts(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._read_alerts(limit=limit)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _alert(
        self,
        alert_type: str,
        severity: str,
        message: str,
        timestamp: float,
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        alert = {
            "alert_id": f"{alert_type}-{int(timestamp * 1000)}",
            "alert_type": alert_type,
            "severity": severity,
            "message": message,
            "timestamp": timestamp,
            "read_only": True,
            "source_state": {
                "coherence_phi": state.get("cognition", {}).get("self_model", {}).get("coherence_phi", 0.0),
                "chaos_score": state.get("dynamics", {}).get("chaos_score", 0.0),
                "rigidity_score": state.get("dynamics", {}).get("rigidity_score", 0.0),
                "drift": state.get("dynamics", {}).get("drift", 0.0),
                "prediction_error": state.get("embodiment", {}).get("prediction_error", 0.0),
                "safety_risk": state.get("safety", {}).get("risk_level", "low"),
                "divergence_detected": state.get("identity", {}).get("divergence_detected", False),
                "drive_instability": max(
                    (d.get("urgency", 0.0) for d in state.get("drives", {}).get("drives", [])), default=0.0
                ),
            },
        }
        return alert


def fmt(n: float) -> str:
    return f"{n:.4f}"
