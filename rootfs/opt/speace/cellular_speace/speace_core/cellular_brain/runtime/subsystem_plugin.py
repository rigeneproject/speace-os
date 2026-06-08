from abc import ABC, abstractmethod
from typing import Any


class SubsystemPlugin(ABC):
    """Base class for SPEACE subsystem plugins (coordinators)."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    def enabled(self) -> bool:
        return True

    def initialize(self, context: "SubsystemContext") -> None:
        """Called once when the plugin is registered."""
        pass

    def on_tick(self, context: "SubsystemContext") -> Any | None:
        """Called every tick by the scheduler."""
        pass

    def shutdown(self) -> None:
        """Called on graceful shutdown."""
        pass
