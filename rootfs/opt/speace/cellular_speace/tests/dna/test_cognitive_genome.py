import pytest

from speace_core.dna.cognitive_genome import (
    CognitiveGenome,
    EpigeneticMarks,
    GenomeChromosome,
    HeredityParams,
    RegulatoryGene,
    RegulatoryNetwork,
    _deep_merge,
    compose_genome,
)
from speace_core.dna.models import (
    CellDifferentiationRule,
    CellExpressionRules,
    SharedGenome,
)


def test_cognitive_genome_creation():
    cg = CognitiveGenome()
    assert cg.shared is not None
    assert cg.heredity is not None
    assert cg.epigenome is not None
    assert cg.regulatory_network is not None
    assert cg.generation == 0
    assert cg.parent_ids == []


def test_epigenetic_marks_defaults():
    em = EpigeneticMarks()
    assert em.methylation == {}
    assert em.acetylation == {}
    assert em.silencing == {}
    assert em.get_expression_modifier("any_gene") == 1.0


def test_epigenetic_marks_silencing():
    em = EpigeneticMarks()
    em.silencing["gene_x"] = True
    assert em.get_expression_modifier("gene_x") == 0.0


def test_epigenetic_marks_methylation():
    em = EpigeneticMarks()
    em.methylation["gene_x"] = 0.8
    modifier = em.get_expression_modifier("gene_x")
    assert 0.5 < modifier < 0.7


def test_epigenetic_inheritance():
    em = EpigeneticMarks()
    em.methylation["gene_a"] = 0.7
    em.methylation["gene_b"] = 0.3
    em.acetylation["gene_c"] = 0.5
    em.silencing["gene_d"] = True

    child = em.inherit(reset_rate=0.0)
    assert child.methylation.get("gene_a") == 0.7
    assert child.silencing.get("gene_d") is True

    child2 = em.inherit(reset_rate=1.0)
    assert "gene_a" not in child2.methylation
    assert "gene_d" not in child2.silencing


def test_regulatory_network_activation():
    rn = RegulatoryNetwork()
    rn.genes["reg1"] = RegulatoryGene(
        name="reg1", targets=["gene_a", "gene_b"], mode="activate", strength=1.0
    )
    mult = rn.get_expression_multiplier("gene_a", ["reg1"])
    assert mult > 1.0


def test_regulatory_network_inhibition():
    rn = RegulatoryNetwork()
    rn.genes["reg1"] = RegulatoryGene(
        name="reg1", targets=["gene_a"], mode="inhibit", strength=1.0
    )
    mult = rn.get_expression_multiplier("gene_a", ["reg1"])
    assert mult < 1.0


def test_regulatory_network_no_match():
    rn = RegulatoryNetwork()
    assert rn.get_expression_multiplier("gene_x", []) == 1.0


def test_effective_expression_with_epigenome():
    cg = CognitiveGenome()
    cg.shared.expression_rules["sensory"] = CellExpressionRules(
        role="sensory",
        express=["gene_a", "gene_b"],
        threshold_defaults={"gene_a": 0.5, "gene_b": 0.3},
    )
    cg.epigenome.silencing["gene_b"] = True

    genes, thresholds = cg.get_effective_expression("sensory")
    assert "gene_a" in genes
    assert "gene_b" not in genes
    assert thresholds["gene_a"] == 0.5


def test_effective_expression_with_regulatory_network():
    cg = CognitiveGenome()
    cg.shared.expression_rules["motor"] = CellExpressionRules(
        role="motor",
        express=["gene_x"],
        threshold_defaults={"gene_x": 0.5},
    )
    cg.regulatory_network.genes["boost"] = RegulatoryGene(
        name="boost", targets=["gene_x"], mode="activate", strength=1.0
    )

    genes, thresholds = cg.get_effective_expression("motor")
    assert "gene_x" in genes
    assert thresholds["gene_x"] > 0.5


def test_effective_differentiation_rule():
    cg = CognitiveGenome()
    cg.shared.cell_differentiation_rules["pyramidal"] = CellDifferentiationRule(
        regions=["cortex"], role="excitatory", threshold_modifier=0.1, plasticity_modifier=1.0
    )

    rule = cg.get_effective_differentiation_rule("pyramidal")
    assert rule is not None
    assert rule.threshold_modifier > 0.0


def test_effective_differentiation_rule_silenced():
    cg = CognitiveGenome()
    cg.shared.cell_differentiation_rules["pyramidal"] = CellDifferentiationRule(
        regions=["cortex"], role="excitatory"
    )
    cg.epigenome.silencing["pyramidal"] = True

    rule = cg.get_effective_differentiation_rule("pyramidal")
    assert rule is None


def test_effective_differentiation_rule_nonexistent():
    cg = CognitiveGenome()
    assert cg.get_effective_differentiation_rule("nonexistent") is None


def test_produce_offspring_asexual():
    cg = CognitiveGenome()
    cg.generation = 5
    cg.shared.homeostasis.default_threshold = 0.7
    child = cg.produce_offspring(mutation_strength=0.0)
    assert child.generation == 6
    assert len(child.parent_ids) == 1
    assert child.shared.homeostasis.default_threshold == 0.7


def test_produce_offspring_with_mutation():
    cg = CognitiveGenome()
    cg.shared.homeostasis.default_threshold = 0.5
    child = cg.produce_offspring(mutation_strength=0.0)
    assert child.shared.homeostasis.default_threshold == 0.5
    child2 = cg.produce_offspring(mutation_strength=0.5)
    assert child2.generation == 1


def test_produce_offspring_sexual():
    parent_a = CognitiveGenome(generation=3)
    parent_a.shared.homeostasis.default_threshold = 0.8
    parent_b = CognitiveGenome(generation=7)
    parent_b.shared.homeostasis.default_threshold = 0.2
    child = parent_a.produce_offspring(other=parent_b, mutation_strength=0.0)
    assert child.generation == 4
    assert len(child.parent_ids) == 2
    assert "gen_3" in child.parent_ids
    assert "gen_7" in child.parent_ids


def test_heredity_params_defaults():
    hp = HeredityParams()
    assert hp.epigenetic_reset_rate == 0.3
    assert hp.chromosome_crossover_rate == 0.2
    assert hp.structural_mutation_rate == 0.05


def test_genome_chromosome():
    gc = GenomeChromosome(name="test_chrom", mutation_rate=0.2, linkage_group="regulatory")
    assert gc.name == "test_chrom"
    assert gc.mutation_rate == 0.2


def test_deep_merge():
    base = {"a": 1, "b": {"c": 2, "d": 3}}
    override = {"b": {"d": 99, "e": 100}, "f": 200}
    _deep_merge(base, override)
    assert base["a"] == 1
    assert base["b"]["c"] == 2
    assert base["b"]["d"] == 99
    assert base["b"]["e"] == 100
    assert base["f"] == 200


def test_to_dict_roundtrip():
    cg = CognitiveGenome()
    cg.shared.homeostasis.default_threshold = 0.77
    cg.epigenome.methylation["gene_x"] = 0.5
    data = cg.to_dict()
    restored = CognitiveGenome.from_dict(data)
    assert restored.shared.homeostasis.default_threshold == 0.77
    assert restored.epigenome.methylation["gene_x"] == 0.5


def test_regulatory_gene_activation_multiplier():
    rn = RegulatoryNetwork()
    rn.genes["act"] = RegulatoryGene(
        name="act", targets=["g1"], mode="activate", strength=2.0
    )
    mult = rn.get_expression_multiplier("g1", ["act"])
    assert mult == 2.0


def test_regulatory_gene_inhibition_multiplier():
    rn = RegulatoryNetwork()
    rn.genes["inh"] = RegulatoryGene(
        name="inh", targets=["g1"], mode="inhibit", strength=1.0
    )
    mult = rn.get_expression_multiplier("g1", ["inh"])
    assert mult == 0.5


def test_crossover_regulatory_network():
    cg1 = CognitiveGenome()
    cg1.regulatory_network.genes["reg_a"] = RegulatoryGene(
        name="reg_a", targets=["g1"], mode="activate", strength=1.0
    )
    cg2 = CognitiveGenome()
    cg2.regulatory_network.genes["reg_b"] = RegulatoryGene(
        name="reg_b", targets=["g2"], mode="inhibit", strength=0.5
    )
    child = cg1.produce_offspring(other=cg2, mutation_strength=0.0)
    rn = child.regulatory_network
    names = set(rn.genes.keys())
    assert "reg_a" in names or "reg_b" in names
    if "reg_a" in rn.genes:
        assert rn.genes["reg_a"].mode == "activate"


def test_epigenome_methylation_modifier():
    em = EpigeneticMarks()
    em.methylation["g"] = 0.0
    assert em.get_expression_modifier("g") == 1.0
    em.methylation["g"] = 1.0
    assert em.get_expression_modifier("g") == 0.5


def test_expression_rules_empty():
    cg = CognitiveGenome()
    genes, thresholds = cg.get_effective_expression("nonexistent")
    assert genes == []
    assert thresholds == {}


def test_cognitive_genome_serialization():
    cg = CognitiveGenome(generation=42)
    cg.heredity.epigenetic_reset_rate = 0.5
    data = cg.to_dict()
    assert data["generation"] == 42
    assert data["heredity"]["epigenetic_reset_rate"] == 0.5
