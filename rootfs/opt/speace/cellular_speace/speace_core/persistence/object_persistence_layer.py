from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

from speace_core.event_bus import EventBus
from speace_core.persistence.persistent_object import (
    CellSnapshot,
    PersistentObject,
    SynapseSnapshot,
    SystemStateSnapshot,
)
from speace_core.persistence.persistent_store import PersistentStore

T = TypeVar("T", bound=PersistentObject)


class ObjectPersistenceLayer:
    """High-level persistence layer managing multiple named stores."""

    def __init__(
        self,
        data_dir: str = "data/persistence",
        event_bus: Optional[EventBus] = None,
    ):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._stores: Dict[str, PersistentStore] = {}
        self._event_bus = event_bus

        self._register_default_stores()

    # ------------------------------------------------------------------ #
    # Store management
    # ------------------------------------------------------------------ #

    def _register_default_stores(self) -> None:
        self.register_store("cells", CellSnapshot)
        self.register_store("synapses", SynapseSnapshot)
        self.register_store("system_state", SystemStateSnapshot)

    def register_store(
        self, name: str, model_class: Type[T]
    ) -> PersistentStore[T]:
        store = PersistentStore(
            model_class=model_class,
            store_name=name,
            data_dir=str(self._data_dir),
        )
        self._stores[name] = store
        return store

    def get_store(self, name: str) -> Optional[PersistentStore]:
        return self._stores.get(name)

    def has_store(self, name: str) -> bool:
        return name in self._stores

    # ------------------------------------------------------------------ #
    # High-level operations
    # ------------------------------------------------------------------ #

    def put(self, store_name: str, obj: T) -> Optional[str]:
        store = self._stores.get(store_name)
        if store is None:
            return None
        result = store.put(obj)
        if self._event_bus is not None:
            import asyncio
            try:
                from speace_core.cellular_brain.base.digital_signal import DigitalSignal
                signal = DigitalSignal(
                    source="persistence_layer",
                    meaning=f"object_persisted:{store_name}",
                    payload={"persistent_id": obj.persistent_id, "object_type": obj.object_type},
                )
                asyncio.ensure_future(self._event_bus.publish("persistence", signal))
            except Exception:
                pass
        return result

    def get(self, store_name: str, persistent_id: str) -> Optional[T]:
        store = self._stores.get(store_name)
        if store is None:
            return None
        return store.get(persistent_id)

    def delete(self, store_name: str, persistent_id: str) -> bool:
        store = self._stores.get(store_name)
        if store is None:
            return False
        return store.delete(persistent_id)

    def query(self, store_name: str, **kwargs) -> List[T]:
        store = self._stores.get(store_name)
        if store is None:
            return []
        return store.query(**kwargs)

    def list_all(self, store_name: str, object_type: Optional[str] = None) -> List[T]:
        store = self._stores.get(store_name)
        if store is None:
            return []
        return store.list_all(object_type=object_type)

    def count(self, store_name: str, object_type: Optional[str] = None) -> int:
        store = self._stores.get(store_name)
        if store is None:
            return 0
        return store.count(object_type=object_type)

    # ------------------------------------------------------------------ #
    # Bulk operations
    # ------------------------------------------------------------------ #

    def snapshot_circuit(
        self,
        neurons: List[Any],
        synapses: List[Any],
        tick: int,
        metrics: Optional[Any] = None,
    ) -> Dict[str, int]:
        counts: Dict[str, int] = {"cells": 0, "synapses": 0}

        cell_snapshots = []
        for n in neurons:
            snap = CellSnapshot(
                cell_id=n.cell_id,
                role=n.role,
                energy=n.energy,
                state=n.state,
                activation=getattr(n, "activation", 0.0),
                threshold=getattr(n, "threshold", 0.5),
                plasticity_rate=getattr(n, "plasticity_rate", 0.01),
                region_id=getattr(n, "region_id", ""),
                epigenome_genes=list(getattr(n, "epigenome", None).active_genes)
                if hasattr(n, "epigenome") and getattr(n, "epigenome", None) is not None
                else [],
                tick=tick,
                object_type=f"cell:{n.role}",
            )
            cell_snapshots.append(snap)

        if cell_snapshots:
            store = self._stores.get("cells")
            if store is not None:
                counts["cells"] = store.snapshot(cell_snapshots)

        syn_snapshots = []
        for s in synapses:
            snap = SynapseSnapshot(
                source_id=s.source_id if hasattr(s, "source_id") else "",
                target_id=s.target_id if hasattr(s, "target_id") else "",
                weight=s.weight if hasattr(s, "weight") else 0.5,
                trust=s.trust if hasattr(s, "trust") else 0.5,
                state=s.state if hasattr(s, "state") else "active",
                plasticity_rate=getattr(s, "plasticity_rate", 0.01),
                tick=tick,
            )
            syn_snapshots.append(snap)

        if syn_snapshots:
            store = self._stores.get("synapses")
            if store is not None:
                counts["synapses"] = store.snapshot(syn_snapshots)

        if metrics is not None:
            state_snap = SystemStateSnapshot(
                coherence_phi=getattr(metrics, "coherence_phi", 0.0),
                mean_energy=getattr(metrics, "mean_energy", 0.0),
                active_neurons=getattr(metrics, "active_neurons", 0),
                synapse_count=len(synapses),
                pruned_synapses=getattr(metrics, "pruned_synapses", 0),
                execution_mode="",
            )
            store = self._stores.get("system_state")
            if store is not None:
                store.put(state_snap)

        return counts

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def load_all(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for name, store in self._stores.items():
            counts[name] = store.load()
        return counts

    def clear_all(self) -> None:
        for store in self._stores.values():
            store.clear()

    def get_stats(self) -> Dict[str, Any]:
        stats: Dict[str, Any] = {}
        for name, store in self._stores.items():
            stats[name] = {
                "total_objects": len(store._objects),
                "alive_count": store.count(),
                "file": str(store._file_path),
            }
        return stats
