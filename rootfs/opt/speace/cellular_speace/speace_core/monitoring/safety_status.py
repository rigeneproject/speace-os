"""SafetyStatus — read-only safety and governance evaluator.

Analyzes governance logs, blocked actions, pending proposals,
and computes an overall risk level without modifying anything.
"""

import pathlib
from typing import Any, Dict, List, Optional


class SafetyStatus:
    """Evaluates the current safety posture of SPEACE."""

    def __init__(self, data_root: str = "data") -> None:
        self.data_root = pathlib.Path(data_root)

    @staticmethod
    def _read_jsonl(path: pathlib.Path, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if not path.exists():
            return []
        entries: List[Dict[str, Any]] = []
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(__import__("json").loads(line))
                    except Exception:
                        continue
                    if limit and len(entries) >= limit:
                        break
        except OSError:
            return []
        return entries

    def evaluate(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "blocked_actions": [],
            "allowed_actions": [],
            "revert_available": False,
            "risk_level": "low",
            "pending_patches": 0,
            "pending_proposals": 0,
            "flags": [],
            "governance_mode": "observation_only",
        }

        # Stabilizer interventions
        stab = self._read_jsonl(self.data_root / "regulation" / "stabilizer_interventions.jsonl")
        high_sev = [i for i in stab if i.get("severity", 0.0) > 2.0]
        if high_sev:
            result["flags"].append({
                "type": "high_severity_interventions",
                "count": len(high_sev),
                "latest_tick": high_sev[-1].get("tick"),
            })

        # Self-improvement proposals
        proposals = self._read_jsonl(self.data_root / "self_improvement" / "proposals.jsonl")
        pending_props = [p for p in proposals if p.get("status") in ("pending", "proposed")]
        result["pending_proposals"] = len(pending_props)
        if pending_props:
            result["flags"].append({
                "type": "pending_proposals",
                "count": len(pending_props),
            })

        # Architecture patches
        patch_dir = self.data_root / "architecture_patches"
        if patch_dir.exists():
            patch_files = [p for p in patch_dir.iterdir() if p.is_file() and p.suffix in (".json", ".jsonl", ".yaml")]
            result["pending_patches"] = len(patch_files)
            if patch_files:
                result["flags"].append({
                    "type": "pending_patches",
                    "count": len(patch_files),
                })

        # Action governance logs (if any)
        gov = self._read_jsonl(self.data_root / "action_governance" / "blocked_actions.jsonl")
        result["blocked_actions"] = [
            {
                "action_id": g.get("action_id", "?"),
                "reason": g.get("reason", "unknown"),
                "timestamp": g.get("timestamp"),
            }
            for g in gov[-10:]
        ]

        # Risk synthesis
        risk_score = 0
        if result["pending_patches"] > 3:
            risk_score += 2
        elif result["pending_patches"] > 0:
            risk_score += 1
        if result["pending_proposals"] > 3:
            risk_score += 2
        elif result["pending_proposals"] > 0:
            risk_score += 1
        risk_score += len(high_sev)

        if risk_score >= 4:
            result["risk_level"] = "critical"
        elif risk_score >= 2:
            result["risk_level"] = "high"
        elif risk_score >= 1:
            result["risk_level"] = "medium"
        else:
            result["risk_level"] = "low"

        return result
