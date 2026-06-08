from typing import Optional, Dict, Any, List, Callable
import time
import copy

from speace_core.evolution.genetic.population import Population, Individual
from speace_core.evolution.genetic.mutation import Mutation, StructuralMutation
from speace_core.evolution.genetic.selection import Selection
from speace_core.evolution.genetic.crossover import Crossover
from speace_core.evolution.fitness_tracker import FitnessTracker


class GeneticEngine:
    """Motore genetico per evoluzione incrementale.

    Responsabilità:
    - Gestire popolazione
    - Applicare mutazioni e crossover
    - Valutare fitness
    - Mantenere elitismo
    """

    def __init__(
        self,
        population_size: int = 30,
        elite_count: int = 2,
        mutation_rate: float = 0.1,
        crossover_rate: float = 0.7,
        mutation_strength: float = 0.1,
        structural_mutation_rate: float = 0.05,
    ):
        self.population_size = population_size
        self.elite_count = elite_count
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate

        self._mutation = Mutation(mutation_rate, mutation_strength)
        self._structural = StructuralMutation(structural_mutation_rate)
        self._fitness_tracker = FitnessTracker()
        self._generation = 0
        self._population: Optional[Population] = None

    # ------------------------------------------------------------------ #
    # Initialization
    # ------------------------------------------------------------------ #

    def initialize(
        self,
        seed_genome: Optional[Dict[str, Any]] = None,
        fitness_fn: Optional[Callable[[Dict[str, Any]], float]] = None,
    ) -> None:
        """Inizializza la popolazione."""
        self._generation = 0
        self._population = Population(
            generation=self._generation,
            max_size=self.population_size,
            elitism_count=self.elite_count,
        )

        # Crea individui iniziali
        if seed_genome:
            # Crea variazioni del genoma seed
            for _ in range(self.population_size):
                ind = Individual.create_random(
                    generation=self._generation,
                    genome_template=seed_genome,
                )
                self._population.add(ind)
        else:
            # Crea individui completamente random
            for _ in range(self.population_size):
                ind = Individual.create_random(generation=self._generation)
                self._population.add(ind)

        # Valuta la popolazione iniziale
        if fitness_fn:
            self._evaluate_population(fitness_fn)

    # ------------------------------------------------------------------ #
    # Evolution
    # ------------------------------------------------------------------ #

    def evolve_one_generation(
        self,
        fitness_fn: Callable[[Dict[str, Any]], float],
        ilf_current: float = 0.5,
    ) -> Dict[str, Any]:
        """Esegue una generazione dell'algoritmo genetico.

        Returns:
            Stats sul ciclo evolutivo.
        """
        if self._population is None:
            return {"error": "Population not initialized"}

        start_time = time.time()
        mutations_proposed = 0
        mutations_accepted = 0

        # Valuta individui non valutati
        self._evaluate_population(fitness_fn)

        # Seleziona genitori
        parents = self._select_parents()

        # Crea nuova generazione
        new_individuals: List[Individual] = []

        # Preserva elite
        elite = self._population.get_elite()
        new_individuals.extend(copy.deepcopy(e) for e in elite)

        # Genera offspring
        while len(new_individuals) < self.population_size:
            if len(parents) >= 2:
                p1, p2 = parents[:2]
            elif len(parents) == 1:
                p1 = p2 = parents[0]
            else:
                p1 = p2 = Individual.create_random(self._generation)

            # Crossover
            child1_genome, child2_genome = self._crossover(p1.genome, p2.genome)

            # Mutazione
            child1_genome = self._mutate(child1_genome)
            child2_genome = self._mutate(child2_genome)

            mutations_proposed += 2

            # Crea individui
            child1 = Individual.create_from_genome(
                generation=self._generation + 1,
                genome=child1_genome,
                parent_ids=[p1.id, p2.id],
            )
            child2 = Individual.create_from_genome(
                generation=self._generation + 1,
                genome=child2_genome,
                parent_ids=[p1.id, p2.id],
            )

            new_individuals.extend([child1, child2])

        # Aggiorna popolazione
        self._population = Population(
            generation=self._generation + 1,
            max_size=self.population_size,
            elitism_count=self.elite_count,
        )
        for ind in new_individuals[: self.population_size]:
            self._population.add(ind)

        # Valuta nuova popolazione
        self._evaluate_population(fitness_fn)

        self._generation += 1

        elapsed = (time.time() - start_time) * 1000

        return {
            "generation": self._generation,
            "population_size": len(self._population.individuals),
            "best_fitness": self._population.get_best().fitness if self._population.individuals else 0.0,
            "avg_fitness": self._population.get_average_fitness(),
            "diversity": self._population.get_diversity(),
            "mutations_proposed": mutations_proposed,
            "duration_ms": elapsed,
            "ilf_current": ilf_current,
        }

    def _evaluate_population(
        self, fitness_fn: Callable[[Dict[str, Any]], float]
    ) -> None:
        """Valuta la fitness di tutti gli individui."""
        if self._population is None:
            return

        for ind in self._population.individuals:
            if ind.status != IndividualStatus.EVALUATED or ind.fitness == 0.0:
                ind.fitness = fitness_fn(ind.genome)
                ind.status = IndividualStatus.EVALUATED

                # Traccia nel fitness tracker
                self._fitness_tracker.record(
                    cycle=self._generation,
                    individual_id=ind.id,
                    fitness=ind.fitness,
                    genome_hash=ind.genome_hash,
                    generation=self._generation,
                )

    def _select_parents(self) -> List[Individual]:
        """Seleziona genitori per la prossima generazione."""
        if self._population is None:
            return []

        pop = self._population.individuals

        # Usa tournament selection
        parents = []
        for _ in range(min(10, len(pop))):
            selected = Selection.tournament(
                pop,
                fitness_fn=lambda x: x.fitness,
                tournament_size=3,
                select_count=1,
            )
            if selected:
                parents.append(selected[0])

        return parents

    def _crossover(
        self, genome1: Dict[str, Any], genome2: Dict[str, Any]
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Applica crossover."""
        import random

        if random.random() < self.crossover_rate:
            # Scegli tipo di crossover
            cx_type = random.choice(["single_point", "uniform", "semantic_aware"])
            if cx_type == "single_point":
                return Crossover.single_point(genome1, genome2)
            elif cx_type == "uniform":
                return Crossover.uniform(genome1, genome2)
            else:
                return Crossover.semantic_aware(genome1, genome2)
        else:
            return copy.deepcopy(genome1), copy.deepcopy(genome2)

    def _mutate(self, genome: Dict[str, Any]) -> Dict[str, Any]:
        """Applica mutazioni."""
        genome = self._mutation.mutate(genome)
        genome = self._structural.mutate(genome)
        return genome

    # ------------------------------------------------------------------ #
    # Accessors
    # ------------------------------------------------------------------ #

    def get_best_individual(self) -> Optional[Individual]:
        """Restituisce il miglior individuo."""
        if self._population is None:
            return None
        best = self._population.get_best()
        return best[0] if best else None

    def get_population(self) -> Optional[Population]:
        return self._population

    def get_generation(self) -> int:
        return self._generation

    def get_fitness_tracker(self) -> FitnessTracker:
        return self._fitness_tracker

    def get_statistics(self) -> Dict[str, Any]:
        """Statistiche correnti."""
        if self._population is None:
            return {"error": "Not initialized"}

        best = self.get_best_individual()
        return {
            "generation": self._generation,
            "population_size": len(self._population.individuals),
            "best_fitness": best.fitness if best else 0.0,
            "best_genome_hash": best.genome_hash if best else "",
            "avg_fitness": self._population.get_average_fitness(),
            "diversity": self._population.get_diversity(),
            "fitness_history": self._fitness_tracker.get_fitness_trend(),
        }