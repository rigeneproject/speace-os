from typing import TYPE_CHECKING, List

from pydantic import BaseModel

from speace_core.cellular_brain.base.digital_cell import DigitalCell
from speace_core.cellular_brain.base.digital_signal import DigitalSignal

if TYPE_CHECKING:
    pass


class Pathway(BaseModel):
    path_id: str
    success_rate: float = 0.0
    use_frequency: int = 0
    latency: float = 1.0
    energy_cost: float = 1.0
    priority: float = 0.0


class DigitalOligodendrocyte(DigitalCell):
    async def receive(self, signal: DigitalSignal) -> None:
        pass

    async def tick(self) -> List[DigitalSignal]:
        return []

    def myelinate(self, pathway: "Pathway") -> None:
        if pathway.success_rate > 0.8 and pathway.use_frequency > 10:
            pathway.latency *= 0.7
            pathway.energy_cost *= 0.6
            pathway.priority += 0.2
