import pytest

from speace_core.cellular_brain.base.cell_factory import CellFactory, DifferentiationContext
from speace_core.dna.parser import load_genome


def test_factory_differentiate_neuron():
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    factory = CellFactory(genome)
    cell = factory.differentiate("c1", DifferentiationContext(region="brain", need="memory"))
    assert cell.role == "digital_neuron"
    assert cell._shared_dna is genome


def test_factory_differentiate_astrocyte():
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    factory = CellFactory(genome)
    cell = factory.differentiate("c1", DifferentiationContext(region="brain", need="regulation"))
    assert cell.role == "digital_astrocyte"


def test_factory_immune_on_high_risk():
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    factory = CellFactory(genome)
    cell = factory.differentiate("c1", DifferentiationContext(region="brain", need="memory", risk_level=0.8))
    assert cell.role == "digital_microglia"


def test_factory_unknown_role():
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    factory = CellFactory(genome)
    factory._resolve_role = lambda ctx: "unknown_role"
    with pytest.raises(ValueError):
        factory.differentiate("c1", DifferentiationContext(region="unknown", need="unknown"))


def test_factory_role_not_allowed():
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    factory = CellFactory(genome)
    factory._resolve_role = lambda ctx: "forbidden_role"
    with pytest.raises(ValueError):
        factory.differentiate("c1", DifferentiationContext(region="x", need="y"))
