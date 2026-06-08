import uuid
import time
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class PersistentObject(BaseModel):
    persistent_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    object_type: str = "generic"
    tick: int = 0
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    deleted: bool = False


class CellSnapshot(PersistentObject):
    object_type: str = "cell"
    cell_id: str = ""
    role: str = ""
    energy: float = 1.0
    state: str = "active"
    activation: float = 0.0
    threshold: float = 0.5
    plasticity_rate: float = 0.01
    region_id: str = ""
    epigenome_genes: list[str] = Field(default_factory=list)


class SynapseSnapshot(PersistentObject):
    object_type: str = "synapse"
    source_id: str = ""
    target_id: str = ""
    weight: float = 0.5
    trust: float = 0.5
    state: str = "active"
    plasticity_rate: float = 0.01


class SystemStateSnapshot(PersistentObject):
    object_type: str = "system_state"
    coherence_phi: float = 0.0
    mean_energy: float = 0.0
    active_neurons: int = 0
    synapse_count: int = 0
    pruned_synapses: int = 0
    tick_interval: float = 0.0
    execution_mode: str = ""
