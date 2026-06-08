"""CausalLearningAuditor — T150 Embodiment Safety & Causal Learning Audit.

Bridges embodied actions with the DigitalTwinModel to produce structured
causal reports: "action X produced effect Y with confidence Z".

Every micro-action follows the loop:
    prediction → action → observation → causal hypothesis
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional


class CausalLearningAuditor:
    """Audits embodied actions against the digital twin to learn causality.

    The auditor is intentionally conservative:
    - it NEVER performs actions itself;
    - it ONLY observes and reports;
    - every physical event is written to a persistent JSONL audit trail.
    """

    def __init__(
        self,
        digital_twin: Any,
        data_root: str = "data/embodiment/causal_learning",
    ) -> None:
        self._twin = digital_twin
        self._data_root = Path(data_root)
        self._data_root.mkdir(parents=True, exist_ok=True)
        self._audit_path = self._data_root / "causal_audit.jsonl"
        self._reports_path = self._data_root / "causal_reports.jsonl"

        self._history: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------ #
    # Core audit loop
    # ------------------------------------------------------------------ #

    def audit_action(
        self,
        action_name: str,
        action_params: Dict[str, Any],
        execute_fn: Any,
        simulate_only: bool = False,
    ) -> Dict[str, Any]:
        """Run the full prediction-action-observation-hypothesis loop.

        Args:
            action_name: human-readable action identifier.
            action_params: parameters passed to the action.
            execute_fn: callable that performs the action and returns a dict
                        with at least {"success": bool, "result": Any}.
            simulate_only: if True, the action is marked as simulated;
                             no real physical side-effects are assumed.

        Returns:
            Structured causal report.
        """
        run_id = f"causal_{uuid.uuid4().hex[:8]}"

        # 1. Prediction — observe twin before action
        pre_state = self._twin.observe() if self._twin else None
        pre_snapshot = pre_state.get("sensor_snapshot") if pre_state else None

        # 2. Action
        action_result = execute_fn()
        action_success = action_result.get("success", False) if isinstance(action_result, dict) else False

        # 3. Observation — observe twin after action
        post_state = self._twin.observe() if self._twin else None
        post_snapshot = post_state.get("sensor_snapshot") if post_state else None

        # 4. Causal hypothesis — compare pre vs post
        hypotheses: List[Dict[str, Any]] = []
        confidence = 0.0
        if pre_snapshot and post_snapshot:
            hypotheses, confidence = self._infer_hypotheses(
                action_name, action_params, pre_snapshot, post_snapshot
            )

        report: Dict[str, Any] = {
            "run_id": run_id,
            "timestamp": time.time(),
            "action": {
                "name": action_name,
                "params": action_params,
                "simulated_only": simulate_only,
                "success": action_success,
            },
            "pre_state_summary": self._summarise_state(pre_snapshot),
            "post_state_summary": self._summarise_state(post_snapshot),
            "hypotheses": hypotheses,
            "aggregate_confidence": round(confidence, 4),
        }

        self._persist_report(report)
        self._history.append(report)
        return report

    # ------------------------------------------------------------------ #
    # Hypothesis generation
    # ------------------------------------------------------------------ #

    def _infer_hypotheses(
        self,
        action_name: str,
        action_params: Dict[str, Any],
        pre: Dict[str, Any],
        post: Dict[str, Any],
    ):
        """Generate simple causal hypotheses by comparing sensor snapshots."""
        hypotheses: List[Dict[str, Any]] = []
        total_confidence = 0.0
        count = 0

        for sensor_key in ("cpu", "memory", "disk", "network", "power", "temperature"):
            pre_sub = pre.get(sensor_key, {})
            post_sub = post.get(sensor_key, {})
            for sub_key in pre_sub:
                if sub_key.endswith("_normalized"):
                    continue  # skip derived normalised values
                pre_val = pre_sub.get(sub_key)
                post_val = post_sub.get(sub_key)
                if isinstance(pre_val, (int, float)) and isinstance(post_val, (int, float)):
                    delta = post_val - pre_val
                    if abs(delta) > 0.01:
                        confidence = min(1.0, abs(delta) / max(abs(pre_val), 1.0))
                        hypothesis = {
                            "cause": f"{action_name}({action_params})",
                            "effect": f"{sensor_key}.{sub_key} changed by {delta:.4f}",
                            "confidence": round(confidence, 4),
                            "pre": pre_val,
                            "post": post_val,
                        }
                        hypotheses.append(hypothesis)
                        total_confidence += confidence
                        count += 1

        if self._twin:
            # Also leverage twin's own delta/hypothesis engine
            twin_delta = self._twin.observe_delta()
            if twin_delta:
                for key in ("cpu", "memory", "temperature"):
                    sub = twin_delta.get(key, {})
                    for sub_key, delta_val in sub.items():
                        if isinstance(delta_val, (int, float)) and abs(delta_val) > 0.1:
                            conf = min(1.0, abs(delta_val) / 50.0)
                            hypotheses.append({
                                "cause": action_name,
                                "effect": f"{key}.{sub_key}_delta({delta_val})",
                                "confidence": round(conf, 4),
                                "source": "twin_delta",
                            })
                            total_confidence += conf
                            count += 1

        aggregate_confidence = (total_confidence / count) if count > 0 else 0.0
        return hypotheses, aggregate_confidence

    @staticmethod
    def _summarise_state(snapshot: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if snapshot is None:
            return None
        return {
            "cpu_usage": snapshot.get("cpu", {}).get("usage_percent"),
            "memory_percent": snapshot.get("memory", {}).get("percent"),
            "process_count": snapshot.get("process", {}).get("process_count"),
            "timestamp": snapshot.get("timestamp"),
        }

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _persist_report(self, report: Dict[str, Any]) -> None:
        try:
            with self._reports_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(report, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def get_reports(self, limit: int = 100) -> List[Dict[str, Any]]:
        if not self._reports_path.exists():
            return []
        lines = self._reports_path.read_text(encoding="utf-8").strip().split("\n")
        reports = []
        for line in lines[-limit:]:
            try:
                reports.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return reports

    def summary(self) -> Dict[str, Any]:
        total = len(self._history)
        successful_audits = sum(1 for r in self._history if r["action"]["success"])
        simulated = sum(1 for r in self._history if r["action"]["simulated_only"])
        return {
            "total_audits": total,
            "successful_audits": successful_audits,
            "simulated_only": simulated,
            "real_actions": total - simulated,
            "avg_confidence": round(
                sum(r["aggregate_confidence"] for r in self._history) / max(total, 1), 4
            ),
        }
