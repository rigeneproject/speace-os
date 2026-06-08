"""SimulatedEnvironmentEngine — Phase 2: sandboxed causal simulation.

Runs small "what-if" experiments inside a digital twin of the local machine.
No physical actions are taken. All experiments are read-only simulations.
Results feed the TemporalNarrativeEngine and CausalGraphEngine.
"""

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional


class SimulatedEnvironmentEngine:
    """Orchestrates sandboxed experiments in a DigitalTwinModel.

    Experiment types:
    - "pressure": simulate increased load on a resource
    - "scarcity": simulate reduced availability
    - "contention": simulate competing resource demands
    - "perturbation": small random perturbation to observe ripple effects
    """

    EXPERIMENT_TYPES = ("pressure", "scarcity", "contention", "perturbation")

    def __init__(
        self,
        digital_twin: Any,
        data_root: str = "data/simulated_embodiment",
    ) -> None:
        self._twin = digital_twin
        self._data_root = Path(data_root)
        self._data_root.mkdir(parents=True, exist_ok=True)
        self._experiments_path = self._data_root / "experiments.jsonl"
        self._results_path = self._data_root / "results.jsonl"

    # ------------------------------------------------------------------ #
    # Experiment lifecycle
    # ------------------------------------------------------------------ #

    def run_experiment(
        self,
        experiment_type: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run a single sandboxed experiment and return the result."""
        if experiment_type not in self.EXPERIMENT_TYPES:
            return {"error": "unknown_experiment_type", "allowed": list(self.EXPERIMENT_TYPES)}

        params = params or {}
        experiment_id = f"SIM-{uuid.uuid4().hex[:12]}"

        # Build action vector based on experiment type
        action = self._build_action(experiment_type, params)

        # Run simulation in digital twin
        simulation = self._twin.simulate_action(action, horizon_ticks=params.get("horizon_ticks", 5))

        # Evaluate causal consequences
        consequences = self._evaluate_consequences(simulation)

        result: Dict[str, Any] = {
            "experiment_id": experiment_id,
            "experiment_type": experiment_type,
            "timestamp": time.time(),
            "action": action,
            "simulation": simulation,
            "consequences": consequences,
            "safe": consequences.get("max_risk_score", 0.0) < 0.7,
        }

        # Persist
        self._persist_experiment(result)

        # Record hypotheses in twin
        for effect in consequences.get("effects", []):
            self._twin.record_hypothesis(
                cause=experiment_type,
                effect=effect["variable"],
                confidence=effect["confidence"],
            )

        return result

    def run_batch(
        self,
        count: int = 3,
        experiment_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Run multiple random experiments."""
        types = experiment_types or list(self.EXPERIMENT_TYPES)
        results: List[Dict[str, Any]] = []
        for _ in range(count):
            et = types[len(results) % len(types)]
            result = self.run_experiment(et)
            if "error" not in result:
                results.append(result)
        return results

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def list_experiments(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return recent experiment results."""
        if not self._experiments_path.exists():
            return []
        lines = self._experiments_path.read_text(encoding="utf-8").strip().split("\n")
        experiments = []
        for line in lines[-limit:]:
            try:
                experiments.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return experiments

    def summary(self) -> Dict[str, Any]:
        experiments = self.list_experiments(limit=10000)
        safe_count = sum(1 for e in experiments if e.get("safe"))
        total = len(experiments)
        by_type: Dict[str, int] = {}
        for e in experiments:
            t = e.get("experiment_type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1
        return {
            "total_experiments": total,
            "safe_experiments": safe_count,
            "unsafe_experiments": total - safe_count,
            "by_type": by_type,
            "latest_risk": experiments[-1]["consequences"]["max_risk_score"] if experiments else None,
        }

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    def _build_action(self, experiment_type: str, params: Dict[str, Any]) -> Dict[str, float]:
        action: Dict[str, float] = {}
        if experiment_type == "pressure":
            target = params.get("target", "cpu_avg")
            magnitude = params.get("magnitude", 20.0)
            action[target] = magnitude
        elif experiment_type == "scarcity":
            target = params.get("target", "mem_used")
            magnitude = params.get("magnitude", -15.0)
            action[target] = magnitude
        elif experiment_type == "contention":
            action["cpu_avg"] = params.get("cpu_magnitude", 15.0)
            action["mem_used"] = params.get("mem_magnitude", 15.0)
        elif experiment_type == "perturbation":
            import random
            keys = ["cpu_avg", "mem_used", "disk_used", "temp_avg"]
            target = random.choice(keys)
            action[target] = random.uniform(-10.0, 10.0)
        return action

    def _evaluate_consequences(self, simulation: Dict[str, Any]) -> Dict[str, Any]:
        effects: List[Dict[str, Any]] = []
        max_risk = 0.0
        changes = simulation.get("changes", {})
        for var, delta in changes.items():
            if abs(delta) > 0.01:
                risk = min(1.0, abs(delta) / 100.0)
                max_risk = max(max_risk, risk)
                effects.append({
                    "variable": var,
                    "delta": delta,
                    "risk_score": round(risk, 4),
                    "confidence": 0.7,
                })
        return {
            "effects": effects,
            "effect_count": len(effects),
            "max_risk_score": round(max_risk, 4),
            "significant": len(effects) > 0,
        }

    def _persist_experiment(self, result: Dict[str, Any]) -> None:
        with self._experiments_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")
