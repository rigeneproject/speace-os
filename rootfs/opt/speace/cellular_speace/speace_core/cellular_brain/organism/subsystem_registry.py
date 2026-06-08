from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.organism.organism_models import SubsystemStatus


class SubsystemRegistry:
    """T59 — Registro dei sottosistemi organismici."""

    def __init__(self):
        self._statuses: Dict[str, SubsystemStatus] = {}

    def register_subsystem(self, name: str, status: Optional[SubsystemStatus] = None) -> SubsystemStatus:
        if status is None:
            status = SubsystemStatus(subsystem_name=name)
        else:
            status.subsystem_name = name
        self._statuses[name] = status
        return status

    def update_status(self, name: str, status: SubsystemStatus) -> bool:
        if name not in self._statuses:
            return False
        self._statuses[name] = status
        return True

    def get_status(self, name: str) -> Optional[SubsystemStatus]:
        return self._statuses.get(name)

    def list_active(self) -> List[str]:
        return [name for name, s in self._statuses.items() if s.enabled and not s.degraded]

    def list_degraded(self) -> List[str]:
        return [name for name, s in self._statuses.items() if s.degraded]

    def mark_degraded(self, name: str, reason: str = "") -> bool:
        if name not in self._statuses:
            return False
        self._statuses[name].degraded = True
        self._statuses[name].health_score = max(0.0, self._statuses[name].health_score - 0.3)
        if reason:
            self._statuses[name].metadata["degraded_reason"] = reason
        return True

    def snapshot(self) -> Dict[str, Any]:
        return {
            "subsystems": {name: s.model_dump() for name, s in self._statuses.items()},
            "active_count": len(self.list_active()),
            "degraded_count": len(self.list_degraded()),
        }
