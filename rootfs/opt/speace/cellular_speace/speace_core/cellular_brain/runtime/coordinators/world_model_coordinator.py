from typing import Any

from speace_core.cellular_brain.runtime.subsystem_plugin import SubsystemPlugin


class WorldModelCoordinator(SubsystemPlugin):
    """Coordinates world model and cyber-physical assimilation (T60-T61)."""

    @property
    def name(self) -> str:
        return "world_model"

    def on_tick(self, context: Any) -> None:
        pass
