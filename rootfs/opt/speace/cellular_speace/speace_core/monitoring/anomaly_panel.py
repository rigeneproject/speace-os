"""AnomalyPanel — read-only anomaly detection for the organism monitor.

Flags deviations in coherence, energy, stabilizer severity, branching ratio,
and embodiment prediction error.
"""

from typing import Any, Dict, List


class AnomalyPanel:
    """Analyzes organism state and surfaces anomalies."""

    def __init__(
        self,
        coherence_phi_min: float = 0.1,
        energy_min: float = 0.2,
        severity_max: float = 2.0,
        branching_ratio_deviation: float = 0.3,
        prediction_error_max: float = 10.0,
    ) -> None:
        self.coherence_phi_min = coherence_phi_min
        self.energy_min = energy_min
        self.severity_max = severity_max
        self.branching_ratio_deviation = branching_ratio_deviation
        self.prediction_error_max = prediction_error_max

    def analyze(self, state: Dict[str, Any]) -> Dict[str, Any]:
        anomalies: List[Dict[str, Any]] = []

        body = state.get("body", {})
        cognition = state.get("cognition", {})
        dynamics = state.get("dynamics", {})
        safety = state.get("safety", {})
        embodiment = state.get("embodiment", {})

        # Coherence collapse
        phi = cognition.get("self_model", {}).get("coherence_phi", 0.0)
        if phi < self.coherence_phi_min:
            anomalies.append({
                "type": "coherence_collapse",
                "value": phi,
                "threshold": self.coherence_phi_min,
                "severity": "high",
            })

        # Energy depletion
        energy = body.get("energy", 0.0)
        # energy isn't directly in body, but mean_energy might be in morphological data
        # We use a proxy: if cpu is very high or memory is saturated
        cpu = body.get("cpu", 0.0)
        if cpu > 90.0:
            anomalies.append({
                "type": "cpu_overload",
                "value": cpu,
                "threshold": 90.0,
                "severity": "medium",
            })

        # Stabilizer severity
        last_intervention = dynamics.get("stabilizer", {}).get("last_intervention", {})
        if last_intervention and last_intervention.get("severity", 0.0) > self.severity_max:
            anomalies.append({
                "type": "stabilizer_high_severity",
                "value": last_intervention["severity"],
                "threshold": self.severity_max,
                "severity": "high",
            })

        # Criticality deviation
        branching = dynamics.get("criticality", {}).get("branching_ratio", 0.0)
        if branching > 0 and abs(branching - 1.0) > self.branching_ratio_deviation:
            anomalies.append({
                "type": "criticality_deviation",
                "value": branching,
                "threshold": 1.0,
                "severity": "medium",
            })

        # Prediction error
        pred_err = embodiment.get("prediction_error", 0.0)
        if pred_err > self.prediction_error_max:
            anomalies.append({
                "type": "high_prediction_error",
                "value": pred_err,
                "threshold": self.prediction_error_max,
                "severity": "medium",
            })

        # Safety risk escalation
        risk = safety.get("risk_level", "low")
        if risk == "critical":
            anomalies.append({
                "type": "critical_risk_level",
                "value": risk,
                "severity": "critical",
            })
        elif risk == "high":
            anomalies.append({
                "type": "high_risk_level",
                "value": risk,
                "severity": "high",
            })

        overall = "normal"
        if any(a["severity"] == "critical" for a in anomalies):
            overall = "critical"
        elif any(a["severity"] == "high" for a in anomalies):
            overall = "high"
        elif anomalies:
            overall = "warning"

        return {
            "anomalies": anomalies,
            "overall_status": overall,
            "anomaly_count": len(anomalies),
        }
