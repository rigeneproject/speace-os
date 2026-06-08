from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
import uuid
import hashlib
import json


class IndividualStatus(Enum):
    ACTIVE = "active"
    EVALUATED = "evaluated"
    SELECTED = "selected"
    REJECTED = "rejected"
    PARENT = "parent"


@dataclass
class Individual:
    """Un individuo nella popolazione genetica.

    NON sono pesi neurali - sono parametri cognitivi,
    configurazioni di agenti, strategie di memoria,
    routing cognitivo.
    """

    id: str
    generation: int
    genome: Dict[str, Any]
    fitness: float = 0.0
    status: IndividualStatus = IndividualStatus.ACTIVE
    parent_ids: List[str] = field(default_factory=list)
    age: int = 0  # Cicli dall'ultima selezione
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def genome_hash(self) -> str:
        s = json.dumps(self.genome, sort_keys=True)
        return hashlib.sha256(s.encode()).hexdigest()[:16]

    def age_one_cycle(self) -> None:
        self.age += 1

    def reset_age(self) -> None:
        self.age = 0

    @classmethod
    def create_random(
        cls,
        generation: int,
        genome_template: Optional[Dict[str, Any]] = None,
    ) -> "Individual":
        """Crea un individuo random."""
        import random

        if genome_template:
            genome = cls._mutate_structure(genome_template, strength=1.0)
        else:
            genome = cls._random_genome()

        return cls(
            id=str(uuid.uuid4())[:8],
            generation=generation,
            genome=genome,
        )

    @classmethod
    def create_from_genome(
        cls,
        generation: int,
        genome: Dict[str, Any],
        parent_ids: Optional[List[str]] = None,
    ) -> "Individual":
        """Crea un individuo da un genoma specifico."""
        return cls(
            id=str(uuid.uuid4())[:8],
            generation=generation,
            genome=genome,
            parent_ids=parent_ids or [],
        )

    @staticmethod
    def _random_genome() -> Dict[str, Any]:
        """Genera un genoma random."""
        import random

        return {
            "cognitive_parameters": {
                "attention_spread": random.uniform(0.1, 0.9),
                "memory_persistence": random.uniform(0.3, 0.9),
                "learning_rate": random.uniform(0.01, 0.2),
                "inhibition_strength": random.uniform(0.1, 0.8),
                "plasticity_rate": random.uniform(0.05, 0.5),
            },
            "agent_config": {
                "max_concurrent_goals": random.randint(1, 5),
                "exploration_rate": random.uniform(0.1, 0.5),
                "exploitation_rate": random.uniform(0.5, 0.9),
                "goal_priority_decay": random.uniform(0.8, 0.99),
            },
            "memory_strategy": {
                "consolidation_threshold": random.uniform(0.5, 0.9),
                "forgetting_rate": random.uniform(0.01, 0.1),
                "semantic_weight": random.uniform(0.3, 0.8),
                "episodic_weight": random.uniform(0.2, 0.7),
            },
            "routing_config": {
                "broadcast_probability": random.uniform(0.05, 0.3),
                "targeted_routing_weight": random.uniform(0.5, 0.9),
                "regional_inhibition": random.uniform(0.1, 0.5),
            },
        }

    @staticmethod
    def _mutate_structure(
        template: Dict[str, Any], strength: float
    ) -> Dict[str, Any]:
        """Crea una variante del template."""
        import random
        import copy

        result = copy.deepcopy(template)

        def mutate_dict(d: Dict[str, Any], path: str = "") -> None:
            for key in list(d.keys()):
                if isinstance(d[key], dict):
                    mutate_dict(d[key], f"{path}.{key}")
                elif isinstance(d[key], float):
                    delta = d[key] * strength * random.uniform(-1, 1)
                    d[key] = max(0.0, min(1.0, d[key] + delta))
                elif isinstance(d[key], int):
                    delta = int(d[key] * strength * random.uniform(-0.5, 0.5))
                    d[key] = max(1, d[key] + delta)

        mutate_dict(result)
        return result


@dataclass
class Population:
    """Popolazione di individui."""

    generation: int
    individuals: List[Individual] = field(default_factory=list)
    max_size: int = 50
    elitism_count: int = 2

    def add(self, individual: Individual) -> None:
        """Aggiunge un individuo alla popolazione."""
        self.individuals.append(individual)

        # Trim se necessario
        if len(self.individuals) > self.max_size:
            # Rimuovi i peggiori (non elitism)
            sorted_ind = sorted(
                self.individuals, key=lambda x: x.fitness, reverse=True
            )
            self.individuals = sorted_ind[: self.max_size]

    def get_best(self, n: int = 1) -> List[Individual]:
        """Restituisce i migliori N individui."""
        sorted_ind = sorted(
            self.individuals, key=lambda x: x.fitness, reverse=True
        )
        return sorted_ind[:n]

    def get_elite(self) -> List[Individual]:
        """Restituisce gli individui elite."""
        return self.get_best(self.elitism_count)

    def get_average_fitness(self) -> float:
        if not self.individuals:
            return 0.0
        return sum(i.fitness for i in self.individuals) / len(self.individuals)

    def get_diversity(self) -> float:
        """Misura la diversità della popolazione basata sui genomi."""
        if len(self.individuals) < 2:
            return 0.0

        # Calcola distanza media tra genomi
        total_distance = 0.0
        count = 0

        for i in range(len(self.individuals)):
            for j in range(i + 1, len(self.individuals)):
                dist = self._genome_distance(
                    self.individuals[i].genome,
                    self.individuals[j].genome,
                )
                total_distance += dist
                count += 1

        return total_distance / count if count > 0 else 0.0

    @staticmethod
    def _genome_distance(g1: Dict[str, Any], g2: Dict[str, Any]) -> float:
        """Calcola distanza normalizzata tra due genomi."""
        import math

        def flatten_and_compare(d1: Dict, d2: Dict, path: str = "") -> List[float]:
            diffs = []
            all_keys = set(d1.keys()) | set(d2.keys())
            for key in all_keys:
                p = f"{path}.{key}"
                v1 = d1.get(key)
                v2 = d2.get(key)
                if isinstance(v1, dict) and isinstance(v2, dict):
                    diffs.extend(flatten_and_compare(v1, v2, p))
                elif v1 is None or v2 is None:
                    diffs.append(1.0)
                elif isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                    max_val = max(abs(v1), abs(v2), 0.001)
                    diffs.append(abs(v1 - v2) / max_val)
                else:
                    diffs.append(1.0 if v1 != v2 else 0.0)
            return diffs

        diffs = flatten_and_compare(g1, g2)
        return sum(diffs) / len(diffs) if diffs else 0.0

    def cull(self, keep_count: int) -> List[Individual]:
        """Rimuove individui, tenendo solo i migliori."""
        sorted_ind = sorted(
            self.individuals, key=lambda x: x.fitness, reverse=True
        )
        removed = sorted_ind[keep_count:]
        self.individuals = sorted_ind[:keep_count]
        return removed