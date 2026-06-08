"""CheckpointManager — periodic organismic state snapshots (T109).

Saves lightweight context for warm restart. Does NOT serialize the full
neural circuit (too heavy). Saves orchestrator metadata, metrics log
tail, and references to T108 persistent files.
"""

import json
import pathlib
import time
from typing import Any, Dict, List, Optional


class CheckpointManager:
    """Serializes and restores runtime checkpoints."""

    def __init__(
        self,
        checkpoint_dir: str = "data/runtime/checkpoints",
        max_checkpoints: int = 10,
    ) -> None:
        self.checkpoint_dir = pathlib.Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.max_checkpoints = max_checkpoints

    def save(
        self,
        orchestrator: Any,
        runtime_state: str,
        circadian_phase: str,
        emergency: bool = False,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "timestamp": time.time(),
            "emergency": emergency,
            "runtime_state": runtime_state,
            "circadian_phase": circadian_phase,
            "orchestrator": self._extract_orchestrator_state(orchestrator),
            "t108_refs": self._t108_refs(),
        }
        filename = f"checkpoint_{int(payload['timestamp'] * 1000)}.json"
        path = self.checkpoint_dir / filename
        try:
            with path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except OSError:
            pass
        self._trim()
        return payload

    def _extract_orchestrator_state(self, orchestrator: Any) -> Dict[str, Any]:
        metrics_log: List[Any] = getattr(orchestrator, "metrics_log", [])
        # keep only last 1000 metrics
        recent_metrics = [m.model_dump(mode="json") if hasattr(m, "model_dump") else dict(m) for m in metrics_log[-1000:]]
        lifecycle = getattr(orchestrator, "_lifecycle_manager", None)
        brainstem = getattr(orchestrator, "_brainstem", None)
        return {
            "current_tick": getattr(orchestrator, "current_tick", 0),
            "tick_interval": getattr(orchestrator, "tick_interval", 1.0),
            "execution_mode": getattr(orchestrator, "execution_mode", "global_tick"),
            "metrics_tail": recent_metrics,
            "lifecycle_state": lifecycle.current_state if lifecycle else "unknown",
            "brainstem_state": brainstem.last_state.state if (brainstem and hasattr(brainstem, "last_state")) else "unknown",
        }

    def _t108_refs(self) -> Dict[str, str]:
        return {
            "relational_memory": "data/experience/relational_memory.json",
            "narrative_timeline": "data/experience/narrative_timeline.jsonl",
            "session_continuity": "data/experience/session_continuity.json",
            "preference_model": "data/experience/preference_model.json",
            "experiential_snapshots": "data/experience/snapshots",
        }

    def _trim(self) -> None:
        files = sorted(self.checkpoint_dir.glob("checkpoint_*.json"), key=lambda p: p.stat().st_mtime)
        while len(files) > self.max_checkpoints:
            try:
                files.pop(0).unlink()
            except OSError:
                break

    def latest(self) -> Optional[Dict[str, Any]]:
        files = sorted(self.checkpoint_dir.glob("checkpoint_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            return None
        try:
            return json.loads(files[0].read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def list_checkpoints(self, limit: int = 10) -> List[Dict[str, Any]]:
        files = sorted(self.checkpoint_dir.glob("checkpoint_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        checkpoints: List[Dict[str, Any]] = []
        for f in files[:limit]:
            try:
                checkpoints.append(json.loads(f.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        return checkpoints
