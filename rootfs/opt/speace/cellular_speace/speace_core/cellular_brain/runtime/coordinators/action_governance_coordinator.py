from typing import Any

from speace_core.cellular_brain.runtime.subsystem_plugin import SubsystemPlugin


class ActionGovernanceCoordinator(SubsystemPlugin):
    """Coordinates external action governance (T62)."""

    @property
    def name(self) -> str:
        return "action_governance"

    def on_tick(self, context: Any) -> None:
        pass
