from typing import List

from speace_core.cellular_brain.cells.digital_oligodendrocyte import DigitalOligodendrocyte, Pathway


class MyelinationEngine:
    def __init__(self, oligodendrocytes: List[DigitalOligodendrocyte]):
        self.oligodendrocytes = oligodendrocytes

    def run(self, pathways: List[Pathway]) -> int:
        count = 0
        for pathway in pathways:
            for oligo in self.oligodendrocytes:
                if pathway.success_rate > 0.8 and pathway.use_frequency > 10:
                    oligo.myelinate(pathway)
                    count += 1
        return count
