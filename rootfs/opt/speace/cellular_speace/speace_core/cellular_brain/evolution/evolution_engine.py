import copy
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import (
    BenchmarkResult,
    NeuroFunctionalBenchmark,
)
from speace_core.cellular_brain.evolution.genome_database import (
    EvolutionRunRecord,
    GenomeDatabase,
    GenomeRecord,
)
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.dna.models import SharedGenome
from speace_core.dna.parser import load_genome
from speace_core.orchestrator import CellularBrainOrchestrator


class FitnessResult(BaseModel):
    genome_id: str
    fitness_score: float
    accuracy_score: float = 0.0
    coherence_phi: float = 0.0
    cognitive_score: float = 0.0
    energy_efficiency: float = 0.0
    modularity_proxy: float = 0.0
    morphological_stability: float = 0.0
    functional_improvement: float = 0.0
    safety_score: float = 0.0
    raw_metrics: Dict[str, Any] = Field(default_factory=dict)


class EvolutionEngine:
    """Evolutionary loop engine: fitness, mutation, crossover, selection."""

    # Genes that are safe to mutate (numeric, structural)
    MUTABLE_GENE_PATHS: List[str] = [
        "homeostasis.default_threshold",
        "homeostasis.default_plasticity_rate",
        "homeostasis.overload_threshold",
        "homeostasis.noise_suppression_rate",
        "homeostasis.energy_recovery_rate",
        "immune.prune_threshold",
        "immune.quarantine_error_limit",
        "immune.myelination_success_threshold",
        "immune.latency_reduction",
    ]

    # Protected top-level keys — never mutated
    PROTECTED_TOP_KEYS: set = {
        "identity",
        "purpose",
        "safety",
        "version",
        "protected_genes",
    }

    def __init__(
        self,
        genome_database: GenomeDatabase,
        mutation_rate: float = 0.10,
        mutation_strength: float = 0.10,
        crossover_rate: float = 0.30,
        elite_fraction: float = 0.20,
    ):
        self.db = genome_database
        self.mutation_rate = mutation_rate
        self.mutation_strength = mutation_strength
        self.crossover_rate = crossover_rate
        self.elite_fraction = elite_fraction

    # ------------------------------------------------------------------ #
    # Fitness
    # ------------------------------------------------------------------ #

    def compute_fitness(self, benchmark_result: BenchmarkResult) -> FitnessResult:
        """Compute fitness from a completed benchmark run."""
        m = benchmark_result.metrics
        accuracy = m.accuracy_score
        phi = m.coherence_phi
        functional_improvement = max(0.0, m.functional_improvement)
        energy_efficiency = max(0.0, min(1.0, m.energy_efficiency))
        modularity = max(0.0, min(1.0, m.modularity_proxy))
        morphological_stability = max(0.0, min(1.0, m.morphological_stability))
        safety = 1.0 if m.speace_cognitive_score > 0.0 else 0.0

        fitness = (
            0.20 * m.speace_cognitive_score
            + 0.20 * phi
            + 0.15 * functional_improvement
            + 0.15 * energy_efficiency
            + 0.10 * modularity
            + 0.10 * morphological_stability
            + 0.10 * safety
        )
        fitness = max(0.0, min(1.0, fitness))

        return FitnessResult(
            genome_id="",
            fitness_score=fitness,
            accuracy_score=accuracy,
            coherence_phi=phi,
            cognitive_score=m.speace_cognitive_score,
            energy_efficiency=energy_efficiency,
            modularity_proxy=modularity,
            morphological_stability=morphological_stability,
            functional_improvement=functional_improvement,
            safety_score=safety,
            raw_metrics=m.model_dump(),
        )

    # ------------------------------------------------------------------ #
    # Selection
    # ------------------------------------------------------------------ #

    def select_parents(
        self,
        records: List[GenomeRecord],
        strategy: str = "top_k",
        k: int = 3,
    ) -> List[GenomeRecord]:
        """Select parent genomes for the next generation."""
        scored = [r for r in records if r.fitness_score is not None]
        if not scored:
            return records[:k]
        scored.sort(key=lambda r: r.fitness_score, reverse=True)  # type: ignore[arg-type]
        if strategy == "top_k":
            return scored[:k]
        if strategy == "elite":
            n_elite = max(1, int(self.elite_fraction * len(scored)))
            return scored[:n_elite]
        return scored[:k]

    # ------------------------------------------------------------------ #
    # Mutation
    # ------------------------------------------------------------------ #

    def mutate_genome(
        self,
        genome: Dict[str, Any],
        strength: float | None = None,
    ) -> Dict[str, Any]:
        """Produce a mutated copy of a genome dict."""
        if strength is None:
            strength = self.mutation_strength
        clone = copy.deepcopy(genome)
        mutated = False
        for path in self.MUTABLE_GENE_PATHS:
            if random.random() > self.mutation_rate:
                continue
            keys = path.split(".")
            target = clone
            for key in keys[:-1]:
                if key not in target or not isinstance(target[key], dict):
                    break
                target = target[key]
            else:
                leaf_key = keys[-1]
                if leaf_key in target:
                    old_val = target[leaf_key]
                    new_val = self._apply_mutation(old_val, strength, leaf_key)
                    if new_val is not None:
                        target[leaf_key] = new_val
                        mutated = True
        if mutated:
            clone["_mutation_timestamp"] = datetime.now(timezone.utc).isoformat()
        return clone

    @staticmethod
    def _apply_mutation(value: Any, strength: float, key_name: str = "") -> Any:
        """Apply bounded mutation to a scalar value."""
        if isinstance(value, (int, float)):
            factor = random.uniform(1.0 - strength, 1.0 + strength)
            new_val = value * factor
            # Clamp by semantic type inferred from key name
            key_lower = key_name.lower()
            if "rate" in key_lower or "threshold" in key_lower or "plasticity" in key_lower:
                return max(0.0, min(1.0, float(new_val)))
            if "count" in key_lower or "limit" in key_lower or "size" in key_lower:
                return max(1, int(round(float(new_val))))
            if "window" in key_lower:
                return max(1, min(10, int(round(float(new_val)))))
            return float(new_val)
        return None

    def adaptive_strength(self, fitness: float) -> float:
        """Return mutation strength based on fitness."""
        if fitness >= 0.80:
            return 0.05
        if fitness >= 0.50:
            return 0.10
        return 0.30

    # ------------------------------------------------------------------ #
    # Crossover
    # ------------------------------------------------------------------ #

    def crossover_genomes(
        self,
        parent_a: Dict[str, Any],
        parent_b: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Combine two parent genomes by averaging mutable numeric genes."""
        child = copy.deepcopy(parent_a)
        for path in self.MUTABLE_GENE_PATHS:
            keys = path.split(".")
            node_a = parent_a
            node_b = parent_b
            node_c = child
            for key in keys[:-1]:
                if key not in node_a or key not in node_b:
                    break
                node_a = node_a[key]
                node_b = node_b[key]
                node_c = node_c[key]
            else:
                leaf_key = keys[-1]
                if leaf_key in node_a and leaf_key in node_b:
                    val_a = node_a[leaf_key]
                    val_b = node_b[leaf_key]
                    if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
                        if isinstance(val_a, int) and isinstance(val_b, int):
                            node_c[leaf_key] = random.choice([val_a, val_b])
                        else:
                            node_c[leaf_key] = (float(val_a) + float(val_b)) / 2.0
        child["_crossover_timestamp"] = datetime.now(timezone.utc).isoformat()
        return child

    # ------------------------------------------------------------------ #
    # Safety validation
    # ------------------------------------------------------------------ #

    def validate_genome_safety(self, genome: Dict[str, Any]) -> bool:
        """Check structural safety invariants."""
        # Neuron-like counts
        neuron_count = genome.get("neuron_count")
        if neuron_count is not None and neuron_count <= 0:
            return False

        # Synapse density
        synapse_density = genome.get("synapse_density")
        if synapse_density is not None and synapse_density < 0:
            return False

        # Homeostasis invariants
        homeostasis = genome.get("homeostasis", {})
        if homeostasis.get("default_threshold", 0.5) <= 0:
            return False
        if homeostasis.get("default_plasticity_rate", 0.05) < 0:
            return False
        overload = homeostasis.get("overload_threshold", 0.85)
        max_energy = homeostasis.get("max_energy", 1.0)
        if overload > max_energy:
            return False

        # Immune invariants
        immune = genome.get("immune", {})
        prune = immune.get("prune_threshold", 0.1)
        if prune < 0 or prune > 1:
            return False

        # Protected keys
        for key in self.PROTECTED_TOP_KEYS:
            if key in genome and genome[key] is None:
                return False

        return True

    # ------------------------------------------------------------------ #
    # Candidate generation
    # ------------------------------------------------------------------ #

    def create_candidate_generation(
        self,
        parent_records: List[GenomeRecord],
        n_candidates: int = 5,
        generation: int = 0,
        benchmark_case: str = "morphological_memory_trace",
        memory: MorphologicalMemory | None = None,
    ) -> List[GenomeRecord]:
        """Produce a new generation of candidate genomes from parents."""
        candidates: List[GenomeRecord] = []
        parents = self.select_parents(parent_records, strategy="top_k", k=max(2, len(parent_records)))
        if len(parents) < 2:
            # If only one parent, clone with mutation
            parent = parents[0] if parents else None
            for _ in range(n_candidates):
                if parent is None:
                    continue
                fitness = parent.fitness_score or 0.0
                strength = self.adaptive_strength(fitness)
                mutated = self.mutate_genome(parent.genome, strength=strength)
                if not self.validate_genome_safety(mutated):
                    mutated = parent.genome  # fallback
                record = GenomeRecord(
                    genome_id=f"gen_{str(uuid.uuid4())[:8]}",
                    parent_ids=[parent.genome_id],
                    generation=generation,
                    genome=mutated,
                    created_at=datetime.now(timezone.utc).isoformat(),
                    mutation_operator="adaptive_mutation",
                    benchmark_case=benchmark_case,
                    lineage_notes=f"mutated from {parent.genome_id} with strength {strength}",
                )
                candidates.append(record)
                if memory is not None:
                    memory.create_event(
                        event_type=MorphologyEventType.GENOME_MUTATED,
                        source_id=parent.genome_id,
                        target_id=record.genome_id,
                        metadata={"strength": strength, "generation": generation},
                    )
            return candidates

        # Multiple parents: mutation + crossover
        for i in range(n_candidates):
            op = random.random()
            parent_a, parent_b = random.sample(parents, 2)
            fitness_a = parent_a.fitness_score or 0.0
            if op < self.crossover_rate:
                child = self.crossover_genomes(parent_a.genome, parent_b.genome)
                operator = "crossover"
                parent_ids = [parent_a.genome_id, parent_b.genome_id]
            else:
                strength = self.adaptive_strength(fitness_a)
                child = self.mutate_genome(parent_a.genome, strength=strength)
                operator = "adaptive_mutation"
                parent_ids = [parent_a.genome_id]

            if not self.validate_genome_safety(child):
                child = parent_a.genome  # fallback to safe parent

            record = GenomeRecord(
                genome_id=f"gen_{str(uuid.uuid4())[:8]}",
                parent_ids=parent_ids,
                generation=generation,
                genome=child,
                created_at=datetime.now(timezone.utc).isoformat(),
                mutation_operator=operator if operator == "adaptive_mutation" else None,
                crossover_operator=operator if operator == "crossover" else None,
                benchmark_case=benchmark_case,
                lineage_notes=f"{operator} from {','.join(parent_ids)}",
            )
            candidates.append(record)
            if memory is not None:
                event_type = (
                    MorphologyEventType.GENOME_CROSSED
                    if operator == "crossover"
                    else MorphologyEventType.GENOME_MUTATED
                )
                memory.create_event(
                    event_type=event_type,
                    source_id=",".join(parent_ids),
                    target_id=record.genome_id,
                    metadata={"operator": operator, "generation": generation},
                )

        return candidates

    # ------------------------------------------------------------------ #
    # Evaluation
    # ------------------------------------------------------------------ #

    async def evaluate_genome(
        self,
        genome_record: GenomeRecord,
        benchmark_case: str = "morphological_memory_trace",
        n_ticks: int = 3,
    ) -> BenchmarkResult:
        """Build an orchestrator from a genome and run a benchmark case."""
        # Load genome dict into SharedGenome
        genome = SharedGenome(**genome_record.genome)
        orch = CellularBrainOrchestrator.build_mvp(genome)
        benchmark = NeuroFunctionalBenchmark(orch)
        pattern = [1.0 if i % 2 == 0 else 0.0 for i in range(10)]
        result = await benchmark.run_case(
            benchmark_case,
            execution_mode="event_driven_burst",
            stdp_enabled=True,
            inhibition_enabled=True,
            energy_control_enabled=True,
            community_detection_enabled=True,
            input_pattern=pattern,
            target_output=pattern,
            n_ticks=n_ticks,
        )
        return result

    # ------------------------------------------------------------------ #
    # Full evolution step
    # ------------------------------------------------------------------ #

    def run_evolution_step(
        self,
        parent_records: List[GenomeRecord],
        benchmark_results: Optional[Dict[str, BenchmarkResult]] = None,
        generation: int = 0,
        n_candidates: int = 5,
        candidate_records: Optional[List[GenomeRecord]] = None,
    ) -> EvolutionRunRecord:
        """Run one evolution generation: create, evaluate (if data provided), select."""
        if candidate_records is not None:
            candidates = candidate_records
        else:
            candidates = self.create_candidate_generation(
                parent_records,
                n_candidates=n_candidates,
                generation=generation,
            )

        # Persist candidates
        for cand in candidates:
            self.db.save_genome(cand)
            self.db.record_lineage(cand.genome_id, cand.parent_ids, generation)

        # Evaluate if benchmark results provided
        best_genome_id: Optional[str] = None
        best_fitness: Optional[float] = None
        if benchmark_results:
            for cand in candidates:
                bres = benchmark_results.get(cand.genome_id)
                if bres is None:
                    continue
                fitness = self.compute_fitness(bres)
                cand.fitness_score = fitness.fitness_score
                cand.metrics = fitness.raw_metrics
                # Re-save with fitness
                self.db.save_genome(cand)
                if best_fitness is None or fitness.fitness_score > best_fitness:
                    best_fitness = fitness.fitness_score
                    best_genome_id = cand.genome_id

        selected = self.select_parents(candidates, strategy="top_k", k=3)
        selected_ids = [s.genome_id for s in selected]

        run = EvolutionRunRecord(
            run_id=f"run_{str(uuid.uuid4())[:8]}",
            generation=generation,
            candidate_genome_ids=[c.genome_id for c in candidates],
            selected_genome_ids=selected_ids,
            best_genome_id=best_genome_id,
            best_fitness=best_fitness,
            created_at=datetime.now(timezone.utc).isoformat(),
            notes=f"Generation {generation}: {len(candidates)} candidates, {len(selected_ids)} selected",
        )
        self.db.save_evolution_run(run)
        return run
