from typing import Any

from speace_core.cellular_brain.runtime.subsystem_plugin import SubsystemPlugin


class SubsystemScheduler:
    """Simple phase-based scheduler for subsystem plugins."""

    PHASE_ORDER = [
        "neural_core",
        "homeostasis",
        "regional",
        "defense",
        "memory",
        "evolution",
        "metabolism",
        "persistence",
        "self_improvement",
        "organism",
        "cyber_physical",
        "world_model",
        "action_governance",
        "snapshot",
    ]

    def __init__(self):
        self._plugins: dict[str, SubsystemPlugin] = {}

    def assign(self, phase: str, plugin: SubsystemPlugin) -> None:
        if phase not in self.PHASE_ORDER:
            raise ValueError(f"Unknown phase: {phase}")
        self._plugins[phase] = plugin

    def get(self, phase: str) -> SubsystemPlugin | None:
        return self._plugins.get(phase)

    def run_phase(self, phase: str, context: Any) -> Any | None:
        plugin = self._plugins.get(phase)
        if plugin is not None and plugin.enabled:
            return plugin.on_tick(context)
        return None

    def run_all(self, context: Any) -> dict[str, Any]:
        results = {}
        for phase in self.PHASE_ORDER:
            result = self.run_phase(phase, context)
            if result is not None:
                results[phase] = result
        return results

    def shutdown_all(self) -> None:
        for plugin in self._plugins.values():
            if plugin.enabled:
                plugin.shutdown()
