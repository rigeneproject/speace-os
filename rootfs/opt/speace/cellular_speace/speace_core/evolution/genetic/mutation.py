from typing import Dict, Any, Callable, List, Optional
import random


class Mutation:
    """Operatore di mutazione per il genoma cognitivo."""

    def __init__(
        self,
        mutation_rate: float = 0.1,
        mutation_strength: float = 0.1,
    ):
        self.mutation_rate = mutation_rate
        self.mutation_strength = mutation_strength

    def mutate(self, genome: Dict[str, Any]) -> Dict[str, Any]:
        """Applica mutazioni al genoma.

        Tipi di mutazione:
        - Gaussian: aggiunge rumore gaussiano ai parametri numerici
        - Random: riassegna valori random
        - Boundary: sposta verso i boundary del range
        """
        if random.random() > self.mutation_rate:
            return genome  # No mutation

        # Scegli tipo di mutazione
        mutation_type = random.choice(["gaussian", "random", "boundary", "scramble"])

        import copy
        result = copy.deepcopy(genome)

        if mutation_type == "gaussian":
            self._gaussian_mutate(result)
        elif mutation_type == "random":
            self._random_mutate(result)
        elif mutation_type == "boundary":
            self._boundary_mutate(result)
        elif mutation_type == "scramble":
            self._scramble_mutate(result)

        return result

    def _gaussian_mutate(self, genome: Dict[str, Any]) -> None:
        """Mutazione gaussiana: aggiunge rumore ai float."""
        for key, value in self._iterate_leaves(genome):
            if isinstance(value, float):
                delta = value * self.mutation_strength * random.gauss(0, 1)
                new_val = value + delta
                self._set_nested(genome, key, max(0.0, min(1.0, new_val)))

    def _random_mutate(self, genome: Dict[str, Any]) -> None:
        """Mutazione random: riassegna valori casuali nel range."""
        for key, value in self._iterate_leaves(genome):
            if isinstance(value, float):
                new_val = random.uniform(0.0, 1.0)
                self._set_nested(genome, key, new_val)
            elif isinstance(value, int):
                if "count" in key or "max" in key:
                    new_val = random.randint(1, 10)
                    self._set_nested(genome, key, new_val)

    def _boundary_mutate(self, genome: Dict[str, Any]) -> None:
        """Mutazione boundary: sposta verso 0 o 1."""
        for key, value in self._iterate_leaves(genome):
            if isinstance(value, float):
                # Verso 0 o verso 1
                direction = random.choice([-1, 1])
                delta = abs(value) * self.mutation_strength * random.uniform(0.5, 1.0)
                new_val = value + direction * delta
                self._set_nested(genome, key, max(0.0, min(1.0, new_val)))

    def _scramble_mutate(self, genome: Dict[str, Any]) -> None:
        """Mutazione scramble: rioridina sottosezioni."""
        # Trova le sezioni commutabili
        if "routing_config" in genome:
            rc = genome["routing_config"]
            if isinstance(rc, dict):
                keys = list(rc.keys())
                if len(keys) >= 2:
                    # Shuffle due chiavi
                    i, j = random.sample(range(len(keys)), 2)
                    rc[keys[i]], rc[keys[j]] = rc[keys[j]], rc[keys[i]]

    def _iterate_leaves(self, d: Dict[str, Any], path: Optional[List[str]] = None):
        """Itera su tutte le foglie del dict."""
        if path is None:
            path = []

        for key, value in d.items():
            current_path = path + [key]
            if isinstance(value, dict):
                yield from self._iterate_leaves(value, current_path)
            else:
                yield current_path, value

    def _set_nested(self, d: Dict[str, Any], path: List[str], value: Any) -> None:
        """Set un valore nested nel dict."""
        for key in path[:-1]:
            d = d[key]
        d[path[-1]] = value


class StructuralMutation:
    """Mutazioni strutturali: aggiungono/rimuovono componenti."""

    def __init__(self, structural_mutation_rate: float = 0.05):
        self.structural_mutation_rate = structural_mutation_rate

    def mutate(self, genome: Dict[str, Any]) -> Dict[str, Any]:
        """Applica mutazioni strutturali."""
        import random

        if random.random() > self.structural_mutation_rate:
            return genome

        mutation_type = random.choice(["add_rule", "remove_rule", "add_agent", "remove_agent"])

        import copy
        result = copy.deepcopy(genome)

        if mutation_type == "add_rule":
            self._add_cognitive_rule(result)
        elif mutation_type == "remove_rule":
            self._remove_cognitive_rule(result)
        elif mutation_type == "add_agent":
            self._add_agent_config(result)
        elif mutation_type == "remove_agent":
            self._remove_agent_config(result)

        return result

    def _add_cognitive_rule(self, genome: Dict[str, Any]) -> None:
        """Aggiunge una regola cognitiva."""
        if "cognitive_parameters" not in genome:
            genome["cognitive_parameters"] = {}

        rules = [
            ("novelty_bonus", lambda: random.uniform(0.01, 0.1)),
            ("familiarity_penalty", lambda: random.uniform(0.01, 0.1)),
            ("complexity_cost", lambda: random.uniform(0.01, 0.05)),
        ]
        key, generator = random.choice(rules)
        genome["cognitive_parameters"][key] = generator()

    def _remove_cognitive_rule(self, genome: Dict[str, Any]) -> None:
        """Rimuove una regola cognitiva."""
        if "cognitive_parameters" not in genome:
            return

        params = genome["cognitive_parameters"]
        if len(params) > 3:  # Mantieni almeno alcune regole
            key = random.choice(list(params.keys()))
            del params[key]

    def _add_agent_config(self, genome: Dict[str, Any]) -> None:
        """Aggiunge configurazione agente."""
        if "agent_config" not in genome:
            genome["agent_config"] = {}

        configs = [
            ("response_timeout", lambda: random.uniform(0.1, 1.0)),
            ("retry_attempts", lambda: random.randint(1, 3)),
            ("confidence_threshold", lambda: random.uniform(0.5, 0.9)),
        ]
        key, generator = random.choice(configs)
        if key not in genome["agent_config"]:
            genome["agent_config"][key] = generator()

    def _remove_agent_config(self, genome: Dict[str, Any]) -> None:
        """Rimuove configurazione agente."""
        if "agent_config" not in genome:
            return

        configs = genome["agent_config"]
        if len(configs) > 2:
            key = random.choice(list(configs.keys()))
            del configs[key]