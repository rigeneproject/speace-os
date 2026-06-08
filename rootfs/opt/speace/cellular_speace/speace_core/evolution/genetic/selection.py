from typing import List, Callable, Optional
import random


class Selection:
    """Operatori di selezione per l'algoritmo genetico."""

    @staticmethod
    def tournament(
        population: List,
        fitness_fn: Callable[[any], float],
        tournament_size: int = 3,
        select_count: int = 1,
    ) -> List:
        """Selezione a torneo.

        Sceglie i migliori da sottogruppi random.
        """
        selected = []

        for _ in range(select_count):
            # Scegli candidati per il torneo
            if len(population) <= tournament_size:
                candidates = list(population)
            else:
                candidates = random.sample(population, tournament_size)

            # Trova il migliore
            best = max(candidates, key=fitness_fn)
            selected.append(best)

            # Rimuovi per evitare selezione multipla (se servono individui diversi)
            if len(selected) < select_count and best in population:
                # Non rimuovere per selezione con riempimento
                pass

        return selected

    @staticmethod
    def fitness_proportional(
        population: List,
        fitness_fn: Callable[[any], float],
        select_count: int = 1,
    ) -> List:
        """Selezione proporzionale al fitness.

        Roulette wheel selection.
        """
        if not population:
            return []

        # Calcola fitness totali
        fitnesses = [fitness_fn(ind) for ind in population]
        total_fitness = sum(fitnesses)

        if total_fitness <= 0:
            # Selezione uniforme se nessun fitness positivo
            return random.sample(population, min(select_count, len(population)))

        # Costruisci la roulette
        selected = []
        for _ in range(select_count):
            pick = random.uniform(0, total_fitness)
            cumulative = 0.0

            for i, ind in enumerate(population):
                cumulative += fitnesses[i]
                if cumulative >= pick:
                    selected.append(ind)
                    break
            else:
                # Fallback: ultimo individuo
                selected.append(population[-1])

        return selected

    @staticmethod
    def rank_based(
        population: List,
        fitness_fn: Callable[[any], float],
        select_count: int = 1,
    ) -> List:
        """Selezione basata sul rank.

        Più stabile della fitness proporzionale.
        """
        if not population:
            return []

        # Ordina per fitness
        sorted_pop = sorted(population, key=fitness_fn, reverse=True)

        # Assegna rank
        n = len(sorted_pop)
        ranks = [(ind, n - i) for i, ind in enumerate(sorted_pop)]

        # Seleziona basandosi sul rank
        total_rank = sum(r for _, r in ranks)
        selected = []

        for _ in range(select_count):
            pick = random.uniform(0, total_rank)
            cumulative = 0.0

            for ind, rank in ranks:
                cumulative += rank
                if cumulative >= pick:
                    selected.append(ind)
                    break
            else:
                selected.append(ranks[-1][0])

        return selected

    @staticmethod
    def elitism(
        population: List,
        fitness_fn: Callable[[any], float],
        elite_count: int = 2,
    ) -> List:
        """Seleziona i migliori N individui.

        Usato per preservare le soluzioni migliori.
        """
        if not population:
            return []

        sorted_pop = sorted(population, key=fitness_fn, reverse=True)
        return sorted_pop[:elite_count]

    @staticmethod
    def truncation(
        population: List,
        fitness_fn: Callable[[any], float],
        proportion: float = 0.5,
    ) -> List:
        """Selezione per troncamento.

        Seleziona la metà migliore.
        """
        if not population:
            return []

        sorted_pop = sorted(population, key=fitness_fn, reverse=True)
        keep_count = max(1, int(len(sorted_pop) * proportion))
        return sorted_pop[:keep_count]