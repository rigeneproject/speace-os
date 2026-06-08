import json
import math
import os
import random
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np


@dataclass
class StabilizerIntervention:
    tick: int
    pattern_detected: str
    modulation: str
    severity: float
    details: Dict[str, Any] = field(default_factory=dict)


class EmergentDynamicsStabilizer:
    """Immune system of SPEACE's cognitive dynamics.

    Monitors the interaction of oscillations, prediction, workspace,
    homeostasis, self-model, energy, and embodiment for dangerous emergent
    patterns, then applies targeted modulations.
    """

    def __init__(
        self,
        chaos_threshold: float = 0.35,
        rigidity_threshold: float = 0.02,
        drift_threshold: float = 0.3,
        loop_intensity_threshold: float = 2.5,
        criticality_drift_threshold: float = 0.2,
        embodiment_stress_threshold: float = 0.7,
        history_window: int = 100,
        seed: int = 42,
        persistence_log_path: Optional[str] = None,
    ):
        self.chaos_threshold = chaos_threshold
        self.rigidity_threshold = rigidity_threshold
        self.drift_threshold = drift_threshold
        self.loop_intensity_threshold = loop_intensity_threshold
        self.criticality_drift_threshold = criticality_drift_threshold
        self.embodiment_stress_threshold = embodiment_stress_threshold
        self.history_window = history_window
        self._rng = random.Random(seed)
        self._np_rng = np.random.default_rng(seed)

        self._state_history: deque = deque(maxlen=history_window)
        self._lyapunov_history: deque = deque(maxlen=history_window)
        self._drive_history: deque = deque(maxlen=history_window)
        self._pattern_history: deque = deque(maxlen=history_window)
        self._intervention_log: List[StabilizerIntervention] = []
        self._tick: int = 0
        self._last_diagnostic: Optional[Dict[str, Any]] = None
        self._adjusted_setpoints: Dict[str, float] = {}

        self._persistence_log_path = persistence_log_path or os.path.join(
            "data", "regulation", "stabilizer_interventions.jsonl"
        )

    # ------------------------------------------------------------------ #
    # Detection methods
    # ------------------------------------------------------------------ #

    def detect_chaos(self, system_state: Dict[str, Any]) -> Dict[str, Any]:
        """High Lyapunov exponent (divergence of nearby trajectories) indicates chaos."""
        activations = system_state.get("activations", [])
        if len(activations) < 2:
            return {"detected": False, "lyapunov_exponent": 0.0, "severity": 0.0}

        current = np.array(activations, dtype=np.float64)
        self._state_history.append(current.copy())

        if len(self._state_history) < 10:
            return {"detected": False, "lyapunov_exponent": 0.0, "severity": 0.0}

        # Approximate largest Lyapunov exponent via divergence of nearby trajectories
        # Compare current state with recent states within a small neighborhood
        window = list(self._state_history)[:-1]
        divergences = []
        for past in window[-20:]:
            d0 = float(np.linalg.norm(current - past))
            if 1e-6 < d0 < 0.5:  # small initial separation
                # Estimate divergence after a few steps using stored history
                divergences.append(d0)

        if not divergences:
            return {"detected": False, "lyapunov_exponent": 0.0, "severity": 0.0}

        # Simple estimator: average log divergence rate
        avg_div = float(np.mean(divergences))
        lyap = math.log1p(avg_div) if avg_div > 0 else 0.0
        self._lyapunov_history.append(lyap)

        # Smooth over recent estimates
        if len(self._lyapunov_history) >= 5:
            lyap = float(np.mean(list(self._lyapunov_history)[-5:]))

        severity = max(0.0, (lyap - self.chaos_threshold * 0.5) / max(self.chaos_threshold, 1e-12))
        detected = lyap > self.chaos_threshold
        return {"detected": detected, "lyapunov_exponent": round(lyap, 6), "severity": round(severity, 6)}

    def detect_rigidity(self, system_state: Dict[str, Any]) -> Dict[str, Any]:
        """Low variance in state over time = stuck in attractor."""
        if len(self._state_history) < 20:
            return {"detected": False, "variance": 0.0, "severity": 0.0}

        recent = np.array(list(self._state_history)[-20:])
        per_dim_var = float(np.mean(np.var(recent, axis=0)))

        severity = max(0.0, 1.0 - (per_dim_var / max(self.rigidity_threshold * 5, 1e-12)))
        detected = per_dim_var < self.rigidity_threshold
        return {"detected": detected, "variance": round(per_dim_var, 6), "severity": round(severity, 6)}

    def detect_motivational_drift(self, system_state: Dict[str, Any]) -> Dict[str, Any]:
        """Drives drifting from setpoints without correction."""
        drives = system_state.get("drive_levels", {})
        if not drives:
            return {"detected": False, "drift_score": 0.0, "severity": 0.0}

        self._drive_history.append(dict(drives))
        if len(self._drive_history) < 10:
            return {"detected": False, "drift_score": 0.0, "severity": 0.0}

        # Measure cumulative deviation from setpoints over recent history
        recent_drives = list(self._drive_history)[-10:]
        total_deviation = 0.0
        for d in recent_drives:
            for name, value in d.items():
                setpoint = self._adjusted_setpoints.get(name, 0.5)
                total_deviation += abs(value - setpoint)

        avg_deviation = total_deviation / (len(recent_drives) * max(len(drives), 1))
        severity = avg_deviation / max(self.drift_threshold, 1e-12)
        detected = avg_deviation > self.drift_threshold
        return {"detected": detected, "drift_score": round(avg_deviation, 6), "severity": round(severity, 6)}

    def detect_self_referential_loop(self, system_state: Dict[str, Any]) -> Dict[str, Any]:
        """Activity patterns repeating with increasing intensity."""
        activations = system_state.get("activations", [])
        if len(activations) < 2:
            return {"detected": False, "loop_score": 0.0, "severity": 0.0}

        current = tuple(np.round(activations, 3).tolist())
        self._pattern_history.append(current)
        if len(self._pattern_history) < 20:
            return {"detected": False, "loop_score": 0.0, "severity": 0.0}

        recent = list(self._pattern_history)[-20:]
        # Count exact repeats in recent window
        repeat_counts = {}
        for p in recent:
            repeat_counts[p] = repeat_counts.get(p, 0) + 1
        max_repeats = max(repeat_counts.values())
        repeat_ratio = max_repeats / len(recent)

        # Intensity trend: is activation magnitude increasing?
        recent_vecs = list(self._state_history)[-20:]
        if len(recent_vecs) >= 10:
            first_magnitude = float(np.linalg.norm(recent_vecs[0]))
            last_magnitude = float(np.linalg.norm(recent_vecs[-1]))
            intensity_ratio = last_magnitude / max(first_magnitude, 1e-12)
        else:
            intensity_ratio = 1.0

        loop_score = repeat_ratio * intensity_ratio
        severity = loop_score / max(self.loop_intensity_threshold, 1e-12)
        detected = loop_score > self.loop_intensity_threshold and intensity_ratio > 1.2
        return {"detected": detected, "loop_score": round(loop_score, 6), "severity": round(severity, 6)}

    def detect_criticality_drift(self, system_state: Dict[str, Any]) -> Dict[str, Any]:
        """System moving away from critical point (too ordered or too chaotic)."""
        branching_ratio = system_state.get("branching_ratio", None)
        if branching_ratio is None:
            # Estimate from chaos and rigidity signals
            chaos = self.detect_chaos(system_state)
            rigidity = self.detect_rigidity(system_state)
            # If both chaos and rigidity are absent, assume near critical
            estimated_br = 1.0 + (0.5 - rigidity["severity"]) * 0.5 - chaos["severity"] * 0.5
            branching_ratio = estimated_br

        distance_from_critical = abs(branching_ratio - 1.0)
        severity = distance_from_critical / max(self.criticality_drift_threshold, 1e-12)
        detected = distance_from_critical > self.criticality_drift_threshold
        return {
            "detected": detected,
            "branching_ratio": round(float(branching_ratio), 6) if branching_ratio is not None else None,
            "distance_from_critical": round(distance_from_critical, 6),
            "severity": round(severity, 6),
        }

    def detect_embodiment_stress(self, system_state: Dict[str, Any]) -> Dict[str, Any]:
        """Physical body showing signs of overload."""
        embodiment = system_state.get("embodiment_depth", 0.0)
        energy_levels = system_state.get("energy_levels", {})
        mean_energy = float(np.mean(list(energy_levels.values()))) if energy_levels else 1.0

        # Stress increases when embodiment is high but energy is low
        stress = 0.0
        if embodiment > 0.5:
            stress += (1.0 - mean_energy) * embodiment

        # Also consider sensor overload signals if present
        sensor_overload = system_state.get("sensor_overload_signals", 0.0)
        stress += sensor_overload * 0.5

        severity = stress / max(self.embodiment_stress_threshold, 1e-12)
        detected = stress > self.embodiment_stress_threshold
        return {"detected": detected, "stress_score": round(stress, 6), "severity": round(severity, 6)}

    # ------------------------------------------------------------------ #
    # Modulation methods
    # ------------------------------------------------------------------ #

    def inject_noise(self, amount: float, system_state: Dict[str, Any]) -> Dict[str, Any]:
        """Add controlled noise to break rigidity."""
        activations = system_state.get("activations", [])
        noisy = []
        for a in activations:
            noise = self._np_rng.normal(0.0, amount)
            noisy.append(float(np.clip(a + noise, 0.0, 1.0)))
        return {"modulation": "inject_noise", "amount": amount, "new_activations": noisy}

    def dampen_feedback(self, factor: float, system_state: Dict[str, Any]) -> Dict[str, Any]:
        """Reduce recurrent coupling strength to prevent runaway loops."""
        activations = system_state.get("activations", [])
        dampened = [float(np.clip(a * factor, 0.0, 1.0)) for a in activations]
        return {"modulation": "dampen_feedback", "factor": factor, "new_activations": dampened}

    def reset_attractor(self, system_state: Dict[str, Any]) -> Dict[str, Any]:
        """Temporarily perturb system state to escape local minima."""
        activations = system_state.get("activations", [])
        perturbation = self._np_rng.normal(0.0, 0.2, size=len(activations))
        reset = [float(np.clip(a + p, 0.0, 1.0)) for a, p in zip(activations, perturbation)]
        return {"modulation": "reset_attractor", "perturbation_std": 0.2, "new_activations": reset}

    def adjust_homeostatic_setpoint(self, drive_name: str, new_setpoint: float) -> Dict[str, Any]:
        """Adapt setpoints based on long-term averages."""
        self._adjusted_setpoints[drive_name] = float(np.clip(new_setpoint, 0.0, 1.0))
        return {
            "modulation": "adjust_homeostatic_setpoint",
            "drive_name": drive_name,
            "new_setpoint": self._adjusted_setpoints[drive_name],
        }

    def enforce_balance(self, system_state: Dict[str, Any]) -> Dict[str, Any]:
        """Redistribute energy across modules to prevent starvation."""
        energy_levels = system_state.get("energy_levels", {})
        if not energy_levels:
            return {"modulation": "enforce_balance", "redistributed": False}

        values = np.array(list(energy_levels.values()), dtype=np.float64)
        mean_energy = float(np.mean(values))
        redistributed = {}
        for mod, val in energy_levels.items():
            # Pull outliers toward mean
            delta = (mean_energy - val) * 0.3
            redistributed[mod] = float(np.clip(val + delta, 0.0, 1.0))
        return {
            "modulation": "enforce_balance",
            "redistributed": True,
            "new_energy_levels": redistributed,
        }

    # ------------------------------------------------------------------ #
    # Monitor / stabilize / step
    # ------------------------------------------------------------------ #

    def monitor(self, system_state: Dict[str, Any]) -> Dict[str, Any]:
        """Take snapshot of all subsystems and return diagnostic report."""
        self._tick += 1
        report = {
            "tick": self._tick,
            "chaos": self.detect_chaos(system_state),
            "rigidity": self.detect_rigidity(system_state),
            "motivational_drift": self.detect_motivational_drift(system_state),
            "self_referential_loop": self.detect_self_referential_loop(system_state),
            "criticality_drift": self.detect_criticality_drift(system_state),
            "embodiment_stress": self.detect_embodiment_stress(system_state),
        }
        # Overall danger score: max of all severities
        severities = [
            v["severity"] for v in report.values() if isinstance(v, dict) and "severity" in v
        ]
        report["overall_danger_score"] = round(max(severities) if severities else 0.0, 6)
        report["any_detected"] = any(
            v.get("detected", False) for v in report.values() if isinstance(v, dict)
        )
        self._last_diagnostic = report
        return report

    def stabilize(self, diagnostic_report: Dict[str, Any], system_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Apply appropriate modulation based on detected pattern."""
        interventions: List[Dict[str, Any]] = []
        if not diagnostic_report.get("any_detected", False):
            return interventions

        # Priority order: most dangerous patterns first
        if diagnostic_report.get("chaos", {}).get("detected", False):
            amount = min(0.5, 0.05 + diagnostic_report["chaos"]["severity"] * 0.1)
            result = self.inject_noise(amount=amount, system_state=system_state)
            interventions.append(result)
            self._log_intervention("chaos", "inject_noise", diagnostic_report["chaos"]["severity"], result)

        if diagnostic_report.get("rigidity", {}).get("detected", False):
            result = self.reset_attractor(system_state=system_state)
            interventions.append(result)
            self._log_intervention("rigidity", "reset_attractor", diagnostic_report["rigidity"]["severity"], result)

        if diagnostic_report.get("self_referential_loop", {}).get("detected", False):
            factor = max(0.3, 1.0 - diagnostic_report["self_referential_loop"]["severity"] * 0.2)
            result = self.dampen_feedback(factor=factor, system_state=system_state)
            interventions.append(result)
            self._log_intervention(
                "self_referential_loop", "dampen_feedback", diagnostic_report["self_referential_loop"]["severity"], result
            )

        if diagnostic_report.get("motivational_drift", {}).get("detected", False):
            # Find the most drifting drive and adjust its setpoint toward current value
            drives = system_state.get("drive_levels", {})
            if drives:
                worst_drive = max(drives, key=lambda k: abs(drives[k] - self._adjusted_setpoints.get(k, 0.5)))
                new_setpoint = np.clip(drives[worst_drive], 0.0, 1.0)
                result = self.adjust_homeostatic_setpoint(worst_drive, new_setpoint)
                interventions.append(result)
                self._log_intervention(
                    "motivational_drift", "adjust_homeostatic_setpoint",
                    diagnostic_report["motivational_drift"]["severity"], result
                )

        if diagnostic_report.get("criticality_drift", {}).get("detected", False):
            # If too ordered, inject noise; if too chaotic, dampen feedback
            br = diagnostic_report["criticality_drift"].get("branching_ratio", 1.0)
            if isinstance(br, (int, float)) and br < 1.0:
                result = self.inject_noise(amount=0.05, system_state=system_state)
                interventions.append(result)
                self._log_intervention("criticality_drift", "inject_noise", diagnostic_report["criticality_drift"]["severity"], result)
            elif isinstance(br, (int, float)) and br > 1.0:
                result = self.dampen_feedback(factor=0.8, system_state=system_state)
                interventions.append(result)
                self._log_intervention("criticality_drift", "dampen_feedback", diagnostic_report["criticality_drift"]["severity"], result)

        if diagnostic_report.get("embodiment_stress", {}).get("detected", False):
            result = self.enforce_balance(system_state=system_state)
            interventions.append(result)
            self._log_intervention(
                "embodiment_stress", "enforce_balance", diagnostic_report["embodiment_stress"]["severity"], result
            )

        return interventions

    def step(self, system_state: Dict[str, Any]) -> Dict[str, Any]:
        """Run monitor + stabilize in one tick."""
        diagnostic = self.monitor(system_state)
        interventions = self.stabilize(diagnostic, system_state)
        return {
            "tick": self._tick,
            "diagnostic": diagnostic,
            "interventions": interventions,
            "intervention_count": len(interventions),
        }

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _log_intervention(
        self,
        pattern: str,
        modulation: str,
        severity: float,
        details: Dict[str, Any],
    ) -> None:
        intervention = StabilizerIntervention(
            tick=self._tick,
            pattern_detected=pattern,
            modulation=modulation,
            severity=severity,
            details=details,
        )
        self._intervention_log.append(intervention)
        self._persist_intervention(intervention)

    def _persist_intervention(self, intervention: StabilizerIntervention) -> None:
        os.makedirs(os.path.dirname(self._persistence_log_path), exist_ok=True)
        record = {
            "tick": intervention.tick,
            "pattern_detected": intervention.pattern_detected,
            "modulation": intervention.modulation,
            "severity": round(intervention.severity, 6),
            "details": intervention.details,
        }
        with open(self._persistence_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def get_intervention_log(self) -> List[Dict[str, Any]]:
        return [
            {
                "tick": i.tick,
                "pattern_detected": i.pattern_detected,
                "modulation": i.modulation,
                "severity": round(i.severity, 6),
                "details": i.details,
            }
            for i in self._intervention_log
        ]

    def get_adjusted_setpoints(self) -> Dict[str, float]:
        return dict(self._adjusted_setpoints)

    def clear_history(self) -> None:
        """Reset internal history buffers."""
        self._state_history.clear()
        self._lyapunov_history.clear()
        self._drive_history.clear()
        self._pattern_history.clear()
        self._intervention_log.clear()
        self._tick = 0
        self._last_diagnostic = None
