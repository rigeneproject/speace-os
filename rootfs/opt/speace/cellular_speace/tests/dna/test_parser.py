import pathlib

import pytest

from speace_core.dna.parser import load_genome


def test_load_default_genome():
    path = pathlib.Path("speace_core/dna/genome/default_genome.yaml")
    genome = load_genome(path)
    assert genome.identity.entity_name == "SPEACE"
    assert "digital_neuron" in genome.morphology.allowed_cell_types
    assert "digital_neuron" in genome.expression_rules
    assert genome.homeostasis.max_energy == 1.0
    assert genome.immune.prune_threshold == 0.1


def test_load_genome_missing_file():
    with pytest.raises(FileNotFoundError):
        load_genome("/nonexistent/genome.yaml")
