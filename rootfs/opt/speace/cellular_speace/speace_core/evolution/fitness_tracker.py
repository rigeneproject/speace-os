from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import time


@dataclass
class FitnessEntry:
    """Singola entry per il fitness tracker."""

    timestamp: float
    cycle: int
    individual_id: str
    fitness: float
    genome_hash: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PopulationStats:
    """Statistiche di una popolazione."""

    cycle: int
    size: int
    mean_fitness: float
    std_fitness: float
    best_fitness: float
    worst_fitness: float
    best_id: str
    diversity_score: float


class FitnessTracker:
    """Traccia il fitness della popolazione nel tempo.

    Calcola statistiche e mantiene la storia per analisi.
    """

    def __init__(self):
        self._history: List[FitnessEntry] = []
        self._best_ever: Optional[FitnessEntry] = None
        self._generation_map: Dict[int, List[FitnessEntry]] = {}

    def record(
        self,
        cycle: int,
        individual_id: str,
        fitness: float,
        genome_hash: str,
        generation: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Registra il fitness di un individuo."""
        entry = FitnessEntry(
            timestamp=time.time(),
            cycle=cycle,
            individual_id=individual_id,
            fitness=fitness,
            genome_hash=genome_hash,
            metadata=metadata or {},
        )

        self._history.append(entry)

        if generation not in self._generation_map:
            self._generation_map[generation] = []
        self._generation_map[generation].append(entry)

        # Aggiorna best ever
        if self._best_ever is None or fitness > self._best_ever.fitness:
            self._best_ever = entry

    def compute_population_stats(
        self, cycle: int, generation: Optional[int] = None
    ) -> PopulationStats:
        """Calcola le statistiche della popolazione.

        Se generation è specificato, usa solo quella generazione.
        Altrimenti usa l'ultimo ciclo.
        """
        if generation is not None:
            entries = self._generation_map.get(generation, [])
        else:
            # Ultimo ciclo
            if not self._history:
                return PopulationStats(
                    cycle=cycle,
                    size=0,
                    mean_fitness=0.0,
                    std_fitness=0.0,
                    best_fitness=0.0,
                    worst_fitness=0.0,
                    best_id="",
                    diversity_score=0.0,
                )
            cycle_to_use = self._history[-1].cycle
            entries = [e for e in self._history if e.cycle == cycle_to_use]

        if not entries:
            return PopulationStats(
                cycle=cycle,
                size=0,
                mean_fitness=0.0,
                std_fitness=0.0,
                best_fitness=0.0,
                worst_fitness=0.0,
                best_id="",
                diversity_score=0.0,
            )

        fitnesses = [e.fitness for e in entries]
        mean = sum(fitnesses) / len(fitnesses)
        variance = sum((f - mean) ** 2 for f in fitnesses) / len(fitnesses)
        std = variance ** 0.5

        best_entry = max(entries, key=lambda e: e.fitness)
        worst_entry = min(entries, key=lambda e: e.fitness)

        # Diversità basata sulla varianza normalizzata
        fitness_range = best_entry.fitness - worst_entry.fitness
        diversity = min(1.0, std / (fitness_range if fitness_range > 0 else 1.0))

        return PopulationStats(
            cycle=cycle,
            size=len(entries),
            mean_fitness=mean,
            std_fitness=std,
            best_fitness=best_entry.fitness,
            worst_fitness=worst_entry.fitness,
            best_id=best_entry.individual_id,
            diversity_score=diversity,
        )

    def get_best_ever(self) -> Optional[FitnessEntry]:
        """Restituisce il miglior individuo di sempre."""
        return self._best_ever

    def get_best_of_cycle(self, cycle: int) -> Optional[FitnessEntry]:
        """Restituisce il miglior individuo di un ciclo specifico."""
        cycle_entries = [e for e in self._history if e.cycle == cycle]
        if not cycle_entries:
            return None
        return max(cycle_entries, key=lambda e: e.fitness)

    def get_history(
        self,
        limit: Optional[int] = None,
        generation: Optional[int] = None,
    ) -> List[FitnessEntry]:
        """Restituisce la storia filtrata."""
        if generation is not None:
            entries = self._generation_map.get(generation, [])
        else:
            entries = list(self._history)

        if limit:
            entries = entries[-limit:]
        return entries

    def get_fitness_trend(self, window: int = 10) -> List[float]:
        """Restituisce il trend del fitness migliore per ciclo."""
        if not self._history:
            return []

        cycles = sorted(set(e.cycle for e in self._history))
        if len(cycles) <= window:
            window_cycles = cycles
        else:
            window_cycles = cycles[-window:]

        trend = []
        for cycle in window_cycles:
            best = self.get_best_of_cycle(cycle)
            if best:
                trend.append(best.fitness)
            else:
                trend.append(0.0)

        return trend

    def get_generation_count(self) -> int:
        """Numero di generazioni tracciate."""
        return len(self._generation_map)

    def clear(self) -> None:
        """Pulisce tutta la storia."""
        self._history.clear()
        self._generation_map.clear()
        self._best_ever = None