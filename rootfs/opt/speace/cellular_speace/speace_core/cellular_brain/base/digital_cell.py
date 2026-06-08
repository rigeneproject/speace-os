from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List

from pydantic import BaseModel, ConfigDict, Field

from speace_core.cellular_brain.base.digital_signal import DigitalSignal, EpigeneticState

if TYPE_CHECKING:
    from speace_core.dna.models import SharedGenome


class DigitalCell(ABC, BaseModel):
    cell_id: str
    role: str
    energy: float = Field(default=1.0, ge=0.0, le=1.0)
    state: str = "active"
    local_memory: List[Any] = []
    epigenome: EpigeneticState = Field(default_factory=EpigeneticState)

    _shared_dna: "SharedGenome" = None  # type: ignore[assignment]

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def bind_genome(self, genome: "SharedGenome") -> None:
        self._shared_dna = genome

    @abstractmethod
    async def receive(self, signal: DigitalSignal) -> None:
        ...

    @abstractmethod
    async def tick(self) -> List[DigitalSignal]:
        """Execute one simulation step; return outbound signals."""
        ...

    def express_genes(self, context_signals: List[DigitalSignal]) -> List[str]:
        if self._shared_dna is None:
            return []
        active = self._shared_dna.get_genes_for_role(self.role)
        for sig in context_signals:
            active = self._apply_epigenetic_modulation(active, sig)
        self.epigenome.active_genes = active
        return active

    def _apply_epigenetic_modulation(
        self, active_genes: List[str], signal: DigitalSignal
    ) -> List[str]:
        modulation = self.epigenome.modulation_factors.get(signal.meaning, 0.0)
        if modulation > 0.5 and signal.meaning not in active_genes:
            active_genes = active_genes + [signal.meaning]
        return active_genes
