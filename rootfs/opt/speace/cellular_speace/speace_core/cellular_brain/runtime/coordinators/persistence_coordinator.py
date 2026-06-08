from typing import Any

from speace_core.cellular_brain.runtime.subsystem_plugin import SubsystemPlugin
from speace_core.event_bus import EventBus
from speace_core.persistence.object_persistence_layer import ObjectPersistenceLayer


class PersistenceCoordinator(SubsystemPlugin):
    """Coordinates the Object Persistence Layer in the tick cycle.

    Snapshots circuit state every N ticks and manages load/save lifecycle.
    """

    def __init__(
        self,
        snapshot_interval: int = 50,
        data_dir: str = "data/persistence",
        event_bus: EventBus | None = None,
    ):
        self._snapshot_interval = snapshot_interval
        self._data_dir = data_dir
        self._event_bus = event_bus
        self._layer: ObjectPersistenceLayer | None = None

    @property
    def name(self) -> str:
        return "persistence"

    def initialize(self, context: Any) -> None:
        self._layer = ObjectPersistenceLayer(
            data_dir=self._data_dir,
            event_bus=self._event_bus,
        )
        counts = self._layer.load_all()
        orch = context.orchestrator_ref()
        import logging
        logging.getLogger("speace.persistence").info(
            "Persistence layer loaded: %s", counts
        )

    def on_tick(self, context: Any) -> dict[str, int] | None:
        if self._layer is None:
            return None
        orch = context.orchestrator_ref()
        if orch.current_tick % self._snapshot_interval != 0:
            return None
        neurons = (
            orch.circuit.input_neurons
            + orch.circuit.hidden_neurons
            + orch.circuit.output_neurons
        )
        synapses = orch.circuit.synapses
        metrics = getattr(orch, "_last_metrics", None)
        if metrics is None and orch.metrics_log:
            metrics = orch.metrics_log[-1]
        counts = self._layer.snapshot_circuit(
            neurons=neurons,
            synapses=synapses,
            tick=orch.current_tick,
            metrics=metrics,
        )
        return counts

    def shutdown(self) -> None:
        if self._layer is not None:
            self._layer.clear_all()
            import logging
            logging.getLogger("speace.persistence").info("Persistence layer shut down")
