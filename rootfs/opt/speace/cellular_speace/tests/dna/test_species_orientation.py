import pathlib

import yaml

from speace_core.dna.parser import load_genome


def test_species_orientation_yaml_exists_and_is_valid():
    path = pathlib.Path("speace_core/dna/genome/core/species_orientation.yaml")
    assert path.exists(), "species_orientation.yaml must exist"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data is not None, "species_orientation.yaml must be valid YAML and non-empty"
    assert "species_orientation" in data, "species_orientation.yaml must contain a species_orientation top-level key"


def test_default_genome_contains_species_orientation():
    path = pathlib.Path("speace_core/dna/genome/default_genome.yaml")
    # Must be parseable by load_genome without raising
    genome = load_genome(path)
    assert genome is not None
    # Must contain the species_orientation top-level key in raw YAML
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert "species_orientation" in raw, "default_genome.yaml must contain a species_orientation top-level key"


def test_species_orientation_mandatory_fields():
    path = pathlib.Path("speace_core/dna/genome/core/species_orientation.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    so = data["species_orientation"]

    # core_principle: non-empty string
    assert "core_principle" in so, "Missing core_principle"
    assert isinstance(so["core_principle"], str) and so["core_principle"].strip(), "core_principle must be a non-empty string"

    # morphogenesis_goal: non-empty string
    assert "morphogenesis_goal" in so, "Missing morphogenesis_goal"
    assert isinstance(so["morphogenesis_goal"], str) and so["morphogenesis_goal"].strip(), "morphogenesis_goal must be a non-empty string"

    # organismic_identity: dict with required keys
    assert "organismic_identity" in so, "Missing organismic_identity"
    oi = so["organismic_identity"]
    assert isinstance(oi, dict), "organismic_identity must be a dict"
    for key in ("identity_model", "local_instances_are", "global_entity_is"):
        assert key in oi, f"organismic_identity missing key: {key}"

    # invariants: list with at least 2 entries
    assert "invariants" in so, "Missing invariants"
    invariants = so["invariants"]
    assert isinstance(invariants, list), "invariants must be a list"
    assert len(invariants) >= 2, "invariants must have at least 2 entries"

    # developmental_direction: dict with stage_0 through stage_7
    assert "developmental_direction" in so, "Missing developmental_direction"
    dd = so["developmental_direction"]
    assert isinstance(dd, dict), "developmental_direction must be a dict"
    for i in range(8):
        key = f"stage_{i}"
        assert key in dd, f"developmental_direction missing key: {key}"


def test_species_orientation_invariant_substrings():
    path = pathlib.Path("speace_core/dna/genome/core/species_orientation.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    invariants = data["species_orientation"]["invariants"]

    invariant_texts = [str(inv) for inv in invariants]
    flat = " ".join(invariant_texts)

    assert "No expansion into external systems without authorization" in flat, (
        "Invariants must include 'No expansion into external systems without authorization'"
    )
    assert "gradual, audited, reversible" in flat, (
        "Invariants must include 'gradual, audited, reversible'"
    )
