from typing import List

from pydantic import Field

from speace_core.cellular_brain.base.digital_cell import DigitalCell
from speace_core.cellular_brain.base.digital_signal import DigitalSignal


class DigitalSynapse(DigitalCell):
    source: str = ""
    target: str = ""
    weight: float = 0.5
    use_count: int = 0
    trust: float = 0.5
    decay: float = 0.001
    consolidated: bool = False
    stability: float = 0.0
    recurrence_count: int = 0

    async def receive(self, signal: DigitalSignal) -> None:
        pass

    async def tick(self) -> List[DigitalSignal]:
        return []

    def transmit(self, signal: DigitalSignal) -> DigitalSignal:
        self.use_count += 1
        signal.strength *= self.weight * self.trust
        return signal

    def reinforce(self, success_score: float) -> None:
        self.weight += 0.01 * success_score
        self.trust += 0.005 * success_score
        self.weight = max(0.0, min(1.0, self.weight))
        self.trust = max(0.0, min(1.0, self.trust))

    def weaken(self, error_score: float) -> None:
        self.weight -= 0.01 * error_score
        self.trust -= 0.005 * error_score
        self.weight = max(0.0, min(1.0, self.weight))
        self.trust = max(0.0, min(1.0, self.trust))
