import copy
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from speace_core.dna.models import (
    CellDifferentiationRule,
    CellExpressionRules,
    GenomeMorphology,
    HomeostasisParams,
    ImmuneParams,
    SharedGenome,
)


# ------------------------------------------------------------------ #
# Chromosome — independently inheritable genome segment
# ------------------------------------------------------------------ #


class GenomeChromosome(BaseModel):
    """A chromosome is a named segment with its own mutation rate and linkage group."""

    name: str = "default"
    mutation_rate: float = 0.1
    linkage_group: str = "core"
    fields: Dict[str, Any] = Field(default_factory=dict)


# ------------------------------------------------------------------ #
# Epigenetic marks — modulate expression without DNA change
# ------------------------------------------------------------------ #


class EpigeneticMarks(BaseModel):
    """Epigenetic marks that modulate gene expression across generations."""

    methylation: Dict[str, float] = Field(default_factory=dict)
    acetylation: Dict[str, float] = Field(default_factory=dict)
    silencing: Dict[str, bool] = Field(default_factory=dict)

    def inherit(self, reset_rate: float = 0.3) -> "EpigeneticMarks":
        """Produce child marks with partial reset."""
        child = EpigeneticMarks()
        for gene, level in self.methylation.items():
            if random.random() > reset_rate:
                child.methylation[gene] = level
        for gene, level in self.acetylation.items():
            if random.random() > reset_rate:
                child.acetylation[gene] = level
        for gene, silenced in self.silencing.items():
            if random.random() > reset_rate:
                child.silencing[gene] = silenced
        return child

    def get_expression_modifier(self, gene: str) -> float:
        """Combined effect of marks on expression (0.0 = fully silenced, 1.0 = normal)."""
        if self.silencing.get(gene, False):
            return 0.0
        mod = 1.0
        mod -= self.methylation.get(gene, 0.0) * 0.5
        mod += self.acetylation.get(gene, 0.0) * 0.3
        return max(0.0, min(1.0, mod))


# ------------------------------------------------------------------ #
# Regulatory network — gene regulatory network
# ------------------------------------------------------------------ #


class RegulatoryGene(BaseModel):
    """A regulatory gene that controls expression of target genes."""

    name: str
    targets: List[str] = Field(default_factory=list)
    mode: str = "activate"
    strength: float = 1.0


class RegulatoryNetwork(BaseModel):
    """Network of regulatory genes controlling cell-type-specific expression."""

    genes: Dict[str, RegulatoryGene] = Field(default_factory=dict)

    def get_expression_multiplier(
        self, target_gene: str, active_regulators: List[str]
    ) -> float:
        multiplier = 1.0
        for reg_name in active_regulators:
            gene = self.genes.get(reg_name)
            if gene is None:
                continue
            if target_gene in gene.targets:
                if gene.mode == "activate":
                    multiplier *= 1.0 + gene.strength * 0.5
                elif gene.mode == "inhibit":
                    multiplier *= 1.0 - gene.strength * 0.5
        return multiplier


# ------------------------------------------------------------------ #
# Heredity parameters
# ------------------------------------------------------------------ #


class HeredityParams(BaseModel):
    """Controls how the genome is inherited and expressed across generations."""

    chromosomes: Dict[str, GenomeChromosome] = Field(default_factory=dict)
    epigenetic_reset_rate: float = 0.3
    imprinting: Dict[str, str] = Field(default_factory=dict)
    chromosome_crossover_rate: float = 0.2
    structural_mutation_rate: float = 0.05


# ------------------------------------------------------------------ #
# Cognitive Genome — wraps SharedGenome with heredity
# ------------------------------------------------------------------ #


class CognitiveGenome(BaseModel):
    """Evolutionary genome with heredity, epigenetics, and regulatory networks.

    Extends SharedGenome with:
    - Chromosome-based independent inheritance
    - Epigenetic marks that partially reset each generation
    - Regulatory network for gene expression control
    - Structural mutation (add/remove cell types, rules)
    - Genomic imprinting (parent-of-origin effects)
    """

    shared: SharedGenome = Field(default_factory=SharedGenome)
    heredity: HeredityParams = Field(default_factory=HeredityParams)
    epigenome: EpigeneticMarks = Field(default_factory=EpigeneticMarks)
    regulatory_network: RegulatoryNetwork = Field(default_factory=RegulatoryNetwork)
    generation: int = 0
    parent_ids: List[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)

    # ------------------------------------------------------------------ #
    # Expression — apply epigenome + regulatory network to shared genome
    # ------------------------------------------------------------------ #

    def get_effective_expression(
        self, role: str
    ) -> Tuple[List[str], Dict[str, float]]:
        """Get expressed genes and threshold defaults, modulated by epigenome and regulatory network."""
        rules = self.shared.expression_rules.get(role)
        if rules is None:
            return [], {}
        genes = list(rules.express)
        thresholds = dict(rules.threshold_defaults)
        for gene in list(genes):
            mod = self.epigenome.get_expression_modifier(gene)
            if mod < 0.1:
                genes.remove(gene)
        active_regulators = [
            name for name, g in self.regulatory_network.genes.items()
            if self.epigenome.get_expression_modifier(name) > 0.5
        ]
        for gene in genes:
            mult = self.regulatory_network.get_expression_multiplier(
                gene, active_regulators
            )
            if gene in thresholds:
                thresholds[gene] = max(0.0, min(1.0, thresholds[gene] * mult))
        return genes, thresholds

    def get_effective_differentiation_rule(
        self, cell_type: str
    ) -> Optional[CellDifferentiationRule]:
        rule = self.shared.get_differentiation_rule(cell_type)
        if rule is None:
            return None
        mod = self.epigenome.get_expression_modifier(cell_type)
        if mod < 0.1:
            return None
        rule_copy = rule.model_copy()
        rule_copy.threshold_modifier *= mod
        rule_copy.plasticity_modifier *= mod
        return rule_copy

    # ------------------------------------------------------------------ #
    # Heredity — produce child genome
    # ------------------------------------------------------------------ #

    def produce_offspring(
        self,
        other: Optional["CognitiveGenome"] = None,
        mutation_strength: float = 0.1,
    ) -> "CognitiveGenome":
        """Produce a child genome, optionally crossing with another parent."""
        child_shared = self.shared.model_copy(deep=True)
        child_heredity = self.heredity.model_copy(deep=True)
        child_regulatory = self.regulatory_network.model_copy(deep=True)
        child_epigenome = self.epigenome.inherit(self.heredity.epigenetic_reset_rate)
        parent_ids = [f"gen_{self.generation}"]

        if other is not None:
            parent_ids.append(f"gen_{other.generation}")
            child_shared = self._crossover(child_shared, other.shared)
            child_regulatory = self._crossover_regulatory(
                child_regulatory, other.regulatory_network
            )
            child_epigenome = self._crossover_epigenome(
                child_epigenome, other.epigenome
            )

        child_shared = self._mutate_shared(child_shared, mutation_strength)
        child_heredity = self._mutate_heredity_params(child_heredity, mutation_strength)
        child_regulatory = self._mutate_regulatory(child_regulatory, mutation_strength)

        child = CognitiveGenome(
            shared=child_shared,
            heredity=child_heredity,
            epigenome=child_epigenome,
            regulatory_network=child_regulatory,
            generation=self.generation + 1,
            parent_ids=parent_ids,
        )
        return child

    # ------------------------------------------------------------------ #
    # Crossover
    # ------------------------------------------------------------------ #

    def _crossover(self, a: SharedGenome, b: SharedGenome) -> SharedGenome:
        child = a.model_copy(deep=True)
        if random.random() < self.heredity.chromosome_crossover_rate:
            for key in type(a).model_fields:
                if key in ("identity",):
                    continue
                if random.random() < 0.5:
                    setattr(child, key, copy.deepcopy(getattr(b, key)))
        return child

    def _crossover_regulatory(
        self, a: RegulatoryNetwork, b: RegulatoryNetwork
    ) -> RegulatoryNetwork:
        child = a.model_copy(deep=True)
        for gene_name, gene_b in b.genes.items():
            if gene_name not in child.genes:
                child.genes[gene_name] = gene_b.model_copy(deep=True)
            elif random.random() < 0.5:
                child.genes[gene_name] = gene_b.model_copy(deep=True)
        return child

    def _crossover_epigenome(
        self, a: EpigeneticMarks, b: EpigeneticMarks
    ) -> EpigeneticMarks:
        child = a.model_copy(deep=True)
        for k in b.methylation:
            if random.random() < 0.3:
                child.methylation[k] = b.methylation[k]
        for k in b.acetylation:
            if random.random() < 0.3:
                child.acetylation[k] = b.acetylation[k]
        for k in b.silencing:
            if random.random() < 0.3:
                child.silencing[k] = b.silencing[k]
        return child

    # ------------------------------------------------------------------ #
    # Structural mutation
    # ------------------------------------------------------------------ #

    def _mutate_shared(
        self, genome: SharedGenome, strength: float
    ) -> SharedGenome:
        g = genome.model_copy(deep=True)

        g.homeostasis.default_threshold = self._mutate_float(
            g.homeostasis.default_threshold, strength, 0.1, 0.9
        )
        g.homeostasis.default_plasticity_rate = self._mutate_float(
            g.homeostasis.default_plasticity_rate, strength, 0.01, 0.5
        )
        g.homeostasis.overload_threshold = self._mutate_float(
            g.homeostasis.overload_threshold, strength, 0.5, 1.0
        )
        g.homeostasis.noise_suppression_rate = self._mutate_float(
            g.homeostasis.noise_suppression_rate, strength, 0.0, 0.5
        )
        g.homeostasis.energy_recovery_rate = self._mutate_float(
            g.homeostasis.energy_recovery_rate, strength, 0.001, 0.1
        )
        g.immune.prune_threshold = self._mutate_float(
            g.immune.prune_threshold, strength, 0.01, 0.5
        )

        if random.random() < self.heredity.structural_mutation_rate:
            self._mutate_expression_rules(g, strength)
        if random.random() < self.heredity.structural_mutation_rate:
            self._mutate_differentiation_rules(g, strength)

        return g

    def _mutate_float(
        self, value: float, strength: float, lo: float, hi: float
    ) -> float:
        delta = value * strength * random.uniform(-1.0, 1.0)
        return max(lo, min(hi, value + delta))

    def _mutate_expression_rules(
        self, genome: SharedGenome, strength: float
    ) -> None:
        if not genome.expression_rules:
            return
        rule_name = random.choice(list(genome.expression_rules.keys()))
        rule = genome.expression_rules[rule_name]
        if random.random() < 0.5 and rule.express:
            gene = random.choice(rule.express)
            rule.express.remove(gene)
        elif random.random() < 0.3:
            new_gene = f"gene_{random.randint(100, 999)}"
            if new_gene not in rule.express:
                rule.express.append(new_gene)
        if random.random() < 0.3 and rule.threshold_defaults:
            param = random.choice(list(rule.threshold_defaults.keys()))
            rule.threshold_defaults[param] = self._mutate_float(
                rule.threshold_defaults[param], strength, 0.0, 1.0
            )

    def _mutate_differentiation_rules(
        self, genome: SharedGenome, strength: float
    ) -> None:
        if not genome.cell_differentiation_rules:
            return
        rule_name = random.choice(list(genome.cell_differentiation_rules.keys()))
        rule = genome.cell_differentiation_rules[rule_name]
        rule.threshold_modifier += random.uniform(-strength, strength)
        rule.plasticity_modifier += random.uniform(-strength * 0.5, strength * 0.5)

    def _mutate_heredity_params(
        self, h: HeredityParams, strength: float
    ) -> HeredityParams:
        h.epigenetic_reset_rate = self._mutate_float(
            h.epigenetic_reset_rate, strength * 0.5, 0.1, 0.9
        )
        h.chromosome_crossover_rate = self._mutate_float(
            h.chromosome_crossover_rate, strength * 0.5, 0.05, 0.8
        )
        h.structural_mutation_rate = self._mutate_float(
            h.structural_mutation_rate, strength * 0.5, 0.01, 0.3
        )
        return h

    def _mutate_regulatory(
        self, rn: RegulatoryNetwork, strength: float
    ) -> RegulatoryNetwork:
        if not rn.genes:
            return rn
        if random.random() < 0.2:
            gene_name = random.choice(list(rn.genes.keys()))
            gene = rn.genes[gene_name]
            gene.strength = self._mutate_float(gene.strength, strength, 0.1, 2.0)
        if random.random() < 0.1:
            gene_name = random.choice(list(rn.genes.keys()))
            gene = rn.genes[gene_name]
            if rn.genes[gene_name].targets:
                t = random.choice(gene.targets)
                gene.targets.remove(t)
        return rn

    # ------------------------------------------------------------------ #
    # Serialization
    # ------------------------------------------------------------------ #

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CognitiveGenome":
        return cls.model_validate(data)


# ------------------------------------------------------------------ #
# Genome composition — layered YAML loading
# ------------------------------------------------------------------ #


def compose_genome(
    base_path: str,
    override_paths: Optional[List[str]] = None,
    delta_path: Optional[str] = None,
) -> CognitiveGenome:
    """Load and compose genome from layered YAML files.

    Layers apply in order: base → overrides → delta → defaults.
    """
    import yaml

    def _load_yaml(path: str) -> Dict[str, Any]:
        p = Path(path)
        if not p.exists():
            return {}
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}

    merged: Dict[str, Any] = _load_yaml(base_path)

    if override_paths:
        for op in override_paths:
            override = _load_yaml(op)
            _deep_merge(merged, override)

    if delta_path:
        delta = _load_yaml(delta_path)
        _deep_merge(merged, delta)

    return CognitiveGenome.from_dict(merged)


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> None:
    """Recursive dict merge."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = copy.deepcopy(value)
