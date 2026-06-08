from typing import Dict, Any, List, Tuple, Optional
import random
import copy


class Crossover:
    """Operatori di crossover per il genoma cognitivo."""

    @staticmethod
    def single_point(
        parent1: Dict[str, Any],
        parent2: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Single-point crossover.

        Trova una chiave di primo livello come punto di taglio.
        """
        keys1 = list(parent1.keys())
        keys2 = list(parent2.keys())

        # Trova chiavi comuni per il crossover
        common_keys = [k for k in keys1 if k in keys2]
        if not common_keys:
            return copy.deepcopy(parent1), copy.deepcopy(parent2)

        # Scegli punto di crossover
        cx_point = random.randint(1, len(common_keys) - 1)
        crossover_keys = common_keys[cx_point:]

        child1 = copy.deepcopy(parent1)
        child2 = copy.deepcopy(parent2)

        # Scambia i segmenti
        for key in crossover_keys:
            if key in parent2:
                child1[key] = copy.deepcopy(parent2[key])
            if key in parent1:
                child2[key] = copy.deepcopy(parent1[key])

        return child1, child2

    @staticmethod
    def uniform(
        parent1: Dict[str, Any],
        parent2: Dict[str, Any],
        swap_probability: float = 0.5,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Uniform crossover.

        Per ogni chiave, sceglie casualmente da quale genitore.
        """
        child1 = copy.deepcopy(parent1)
        child2 = copy.deepcopy(parent2)

        all_keys = set(parent1.keys()) | set(parent2.keys())

        for key in all_keys:
            if random.random() < swap_probability:
                # Scambia questa chiave
                if key in parent1 and key in parent2:
                    child1[key] = copy.deepcopy(parent2[key])
                    child2[key] = copy.deepcopy(parent1[key])
                elif key in parent1:
                    child1[key] = copy.deepcopy(parent1[key])
                    if key in parent2:
                        child2[key] = copy.deepcopy(parent2[key])

        return child1, child2

    @staticmethod
    def semantic_aware(
        parent1: Dict[str, Any],
        parent2: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Crossover semantico.

        Scambia blocchi semanticamente correlati.
        """
        child1 = copy.deepcopy(parent1)
        child2 = copy.deepcopy(parent2)

        # Definisci gruppi semantici
        semantic_groups = [
            ["cognitive_parameters", "learning_rate", "plasticity_rate"],
            ["agent_config", "exploration_rate", "exploitation_rate"],
            ["memory_strategy", "consolidation_threshold", "forgetting_rate"],
            ["routing_config", "broadcast_probability", "targeted_routing_weight"],
        ]

        for group in semantic_groups:
            if random.random() < 0.5:  # 50% chance di scambiare l'intero gruppo
                primary_key = group[0]
                if primary_key in parent1 and primary_key in parent2:
                    child1[primary_key] = copy.deepcopy(parent2[primary_key])
                    child2[primary_key] = copy.deepcopy(parent1[primary_key])

        return child1, child2

    @staticmethod
    def arithmetic(
        parent1: Dict[str, Any],
        parent2: Dict[str, Any],
        alpha: float = 0.5,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Crossover aritmetico.

        Combina numericamente i valori.
        """
        child1 = copy.deepcopy(parent1)
        child2 = copy.deepcopy(parent2)

        # Trova foglie numeriche
        leaves1 = list(Crossover._flatten_genome(parent1).items())
        leaves2 = list(Crossover._flatten_genome(parent2).items())

        common_keys = set(leaves1.keys()) & set(leaves2.keys())

        for key in common_keys:
            v1 = leaves1[key]
            v2 = leaves2[key]

            if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                # Calcola figli aritmetici
                child1_val = alpha * v1 + (1 - alpha) * v2
                child2_val = (1 - alpha) * v1 + alpha * v2

                # Trova il path e setta
                Crossover._set_by_path(child1, key, child1_val)
                Crossover._set_by_path(child2, key, child2_val)

        return child1, child2

    @staticmethod
    def _flatten_genome(
        genome: Dict[str, Any], prefix: str = ""
    ) -> Dict[str, Any]:
        """Flatten genome to leaf values with path keys."""
        result = {}
        for key, value in genome.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                result.update(Crossover._flatten_genome(value, path))
            else:
                result[path] = value
        return result

    @staticmethod
    def _set_by_path(genome: Dict[str, Any], path: str, value: Any) -> None:
        """Set a value in nested dict by path."""
        keys = path.split(".")
        current = genome
        for key in keys[:-1]:
            if key not in current:
                return
            current = current[key]
        current[keys[-1]] = value