import pytest

from speace_core.cellular_brain.base.digital_cell import DigitalCell
from speace_core.cellular_brain.base.digital_signal import DigitalSignal
from speace_core.dna.parser import load_genome


class DummyCell(DigitalCell):
    async def receive(self, signal: DigitalSignal) -> None:
        self.local_memory.append(signal.strength)

    async def tick(self):
        return []


def test_express_genes():
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    cell = DummyCell(cell_id="d1", role="digital_neuron")
    cell.bind_genome(genome)
    genes = cell.express_genes([])
    assert "signal_processing" in genes


def test_express_genes_no_genome():
    cell = DummyCell(cell_id="d1", role="digital_neuron")
    genes = cell.express_genes([])
    assert genes == []
