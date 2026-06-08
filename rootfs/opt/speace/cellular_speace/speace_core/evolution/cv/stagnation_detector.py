from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
import uuid
import time


class BranchStatus(Enum):
    """Stato di un branch cognitivo."""

    ACTIVE = "active"
    EXPLORING = "exploring"
    EVALUATED = "evaluated"
    MERGED = "merged"
    PRUNED = "pruned"
    PROMOTED = "promoted"


@dataclass
class CognitiveBranch:
    """Branch cognitivo generato dal CV Engine.

    Rappresenta una posible riorganizzazione architetturale.
    """

    id: str
    name: str
    parent_id: Optional[str]
    status: BranchStatus = BranchStatus.ACTIVE
    depth: int = 0

    # Contenuto del branch
    genome_modifications: Dict[str, Any] = field(default_factory=dict)
    architectural_changes: Dict[str, Any] = field(default_factory=dict)
    memory_reorganizations: Dict[str, Any] = field(default_factory=dict)
    learning_modifications: Dict[str, Any] = field(default_factory=dict)

    # Valutazione
    ilf_before: float = 0.0
    ilf_score: float = 0.0
    ilf_delta: float = 0.0
    stability_score: float = 0.0

    # Metadati
    created_at: float = field(default_factory=time.time)
    evaluated_at: Optional[float] = None
    merged_into: Optional[str] = None

    @property
    def age(self) -> float:
        return time.time() - self.created_at

    def is_worth_exploring(self, min_ilf_delta: float = 0.01) -> bool:
        """Il branch vale la pena essere esplorato?"""
        return self.ilf_delta > min_ilf_delta or self.depth < 3

    def mark_evaluated(self, ilf_score: float, ilf_delta: float) -> None:
        """Marca il branch come valutato."""
        self.status = BranchStatus.EVALUATED
        self.ilf_score = ilf_score
        self.ilf_delta = ilf_delta
        self.evaluated_at = time.time()

    def mark_merged(self, target_id: str) -> None:
        self.status = BranchStatus.MERGED
        self.merged_into = target_id

    def mark_pruned(self) -> None:
        self.status = BranchStatus.PRUNED

    def mark_promoted(self) -> None:
        self.status = BranchStatus.PROMOTED

    def to_summary(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "depth": self.depth,
            "ilf_before": self.ilf_before,
            "ilf_score": self.ilf_score,
            "ilf_delta": self.ilf_delta,
            "stability_score": self.stability_score,
            "age_seconds": self.age,
        }


class StagnationDetector:
    """Rileva stagnazione per attivare il CV Engine."""

    def __init__(
        self,
        window_size: int = 5,
        min_delta_threshold: float = 0.01,
        consecutive_cycles: int = 3,
    ):
        self.window_size = window_size
        self.min_delta_threshold = min_delta_threshold
        self.consecutive_cycles = consecutive_cycles
        self._cycle_count = 0

    def is_stagnant(
        self,
        ilf_history: List[float],
        current_ilf: float,
    ) -> tuple[bool, Dict[str, Any]]:
        """Rileva se l'organismo è in stagnazione.

        Returns:
            (is_stagnant, details)
        """
        details = {
            "consecutive_below_threshold": self._cycle_count,
            "window_size": self.window_size,
            "threshold": self.min_delta_threshold,
        }

        # Calcola delta recente
        if len(ilf_history) < self.window_size:
            details["reason"] = "insufficient_history"
            return False, details

        recent = ilf_history[-self.window_size:]
        max_ilf = max(recent)
        min_ilf = min(recent)
        delta = max_ilf - min_ilf

        details["recent_delta"] = delta
        details["recent_max"] = max_ilf
        details["recent_min"] = min_ilf

        # Rileva stagnazione
        if delta < self.min_delta_threshold:
            self._cycle_count += 1
            details["consecutive_below_threshold"] = self._cycle_count

            if self._cycle_count >= self.consecutive_cycles:
                details["reason"] = "consecutive_stagnation"
                return True, details
        else:
            self._cycle_count = 0
            details["reason"] = "improvement_detected"
            return False, details

        details["reason"] = "below_threshold"
        return False, details

    def reset(self) -> None:
        self._cycle_count = 0


@dataclass
class BranchGeneratorConfig:
    """Configurazione per la generazione di branch."""

    max_branch_depth: int = 4
    branch_types: List[str] = None
    min_branch_score: float = 0.3

    def __post_init__(self):
        if self.branch_types is None:
            self.branch_types = ["cognitive", "architectural", "memory", "learning"]


class BranchGenerator:
    """Genera branch cognitivi per il CV Engine."""

    def __init__(self, config: Optional[BranchGeneratorConfig] = None):
        self.config = config or BranchGeneratorConfig()

    def generate_branch(
        self,
        parent: Optional[CognitiveBranch],
        trigger_reason: str,
        current_genome: Dict[str, Any],
    ) -> CognitiveBranch:
        """Genera un nuovo branch.

        Args:
            parent: Branch genitore (None per branch radice)
            trigger_reason: Perché è stato attivato il CV
            current_genome: Genoma corrente
        """
        import random

        branch_id = str(uuid.uuid4())[:8]
        depth = (parent.depth + 1) if parent else 0

        # Scegli tipo di branch
        branch_type = random.choice(self.config.branch_types)

        if branch_type == "cognitive":
            modifications = self._generate_cognitive_modifications(current_genome)
            arch_changes = {}
            mem_reorg = {}
            learn_mods = {}
        elif branch_type == "architectural":
            modifications = {}
            arch_changes = self._generate_architectural_changes(current_genome)
            mem_reorg = {}
            learn_mods = {}
        elif branch_type == "memory":
            modifications = {}
            arch_changes = {}
            mem_reorg = self._generate_memory_reorganizations(current_genome)
            learn_mods = {}
        else:  # learning
            modifications = {}
            arch_changes = {}
            mem_reorg = {}
            learn_mods = self._generate_learning_modifications(current_genome)

        name = self._generate_branch_name(branch_type, parent, depth)

        branch = CognitiveBranch(
            id=branch_id,
            name=name,
            parent_id=parent.id if parent else None,
            depth=depth,
            genome_modifications=modifications,
            architectural_changes=arch_changes,
            memory_reorganizations=mem_reorg,
            learning_modifications=learn_mods,
        )

        return branch

    def _generate_cognitive_modifications(
        self, genome: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Genera modifiche cognitive."""
        import random

        cognitive = genome.get("cognitive_parameters", {})

        modifications = {}

        # Parametri che possono essere modificati
        param_choices = [
            ("attention_spread", lambda: random.uniform(0.1, 0.9)),
            ("memory_persistence", lambda: random.uniform(0.3, 0.9)),
            ("learning_rate", lambda: random.uniform(0.01, 0.3)),
            ("inhibition_strength", lambda: random.uniform(0.1, 0.8)),
            ("plasticity_rate", lambda: random.uniform(0.05, 0.5)),
        ]

        # Scegli 1-3 parametri da modificare
        num_mods = random.randint(1, 3)
        chosen = random.sample(param_choices, min(num_mods, len(param_choices)))

        for param, generator in chosen:
            if param in cognitive:
                old_val = cognitive[param]
                new_val = generator()
                modifications[param] = {
                    "old": old_val,
                    "new": new_val,
                    "change_type": "cognitive_parameter",
                }

        return modifications

    def _generate_architectural_changes(
        self, genome: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Genera cambiamenti architetturali."""
        import random

        changes = {}
        change_types = [
            ("add_bottleneck", self._add_bottleneck),
            ("remove_bottleneck", self._remove_bottleneck),
            ("increase_connectivity", self._increase_connectivity),
            ("decrease_connectivity", self._decrease_connectivity),
            ("add_specialization", self._add_specialization),
        ]

        num_changes = random.randint(1, 2)
        chosen = random.sample(change_types, min(num_changes, len(change_types)))

        for change_type, change_fn in chosen:
            result = change_fn(genome)
            if result:
                changes[change_type] = result

        return changes

    def _generate_memory_reorganizations(
        self, genome: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Genera riorganizzazioni della memoria."""
        import random

        reorgs = {}

        strategies = [
            ("consolidation_threshold", lambda: random.uniform(0.4, 0.95)),
            ("forgetting_rate", lambda: random.uniform(0.005, 0.15)),
            ("semantic_weight", lambda: random.uniform(0.2, 0.9)),
            ("episodic_weight", lambda: random.uniform(0.1, 0.8)),
        ]

        num_reorgs = random.randint(1, 2)
        chosen = random.sample(strategies, min(num_reorgs, len(strategies)))

        for param, generator in chosen:
            old_val = random.uniform(0.3, 0.8)  # Valore attuale stimato
            new_val = generator()
            reorgs[param] = {"old": old_val, "new": new_val}

        return reorgs

    def _generate_learning_modifications(
        self, genome: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Genera modifiche all'apprendimento."""
        import random

        mods = {}

        mod_types = [
            ("novelty_bonus", lambda: random.uniform(0.01, 0.15)),
            ("error_penalty", lambda: random.uniform(0.01, 0.1)),
            ("confidence_decay", lambda: random.uniform(0.9, 0.99)),
            ("learning_window", lambda: random.randint(3, 20)),
        ]

        num_mods = random.randint(1, 2)
        chosen = random.sample(mod_types, min(num_mods, len(mod_types)))

        for param, generator in chosen:
            mods[param] = generator()

        return mods

    def _add_bottleneck(self, genome: Dict[str, Any]) -> Dict[str, Any]:
        return {"action": "add", "target": "routing", "description": "Add bottleneck in routing"}

    def _remove_bottleneck(self, genome: Dict[str, Any]) -> Dict[str, Any]:
        return {"action": "remove", "target": "routing", "description": "Remove routing bottleneck"}

    def _increase_connectivity(self, genome: Dict[str, Any]) -> Dict[str, Any]:
        return {"action": "increase", "target": "connectivity", "factor": 1.2}

    def _decrease_connectivity(self, genome: Dict[str, Any]) -> Dict[str, Any]:
        return {"action": "decrease", "target": "connectivity", "factor": 0.8}

    def _add_specialization(self, genome: Dict[str, Any]) -> Dict[str, Any]:
        return {"action": "add", "target": "region", "type": "specialized"}

    def _generate_branch_name(
        self, branch_type: str, parent: Optional[CognitiveBranch], depth: int
    ) -> str:
        """Genera un nome descrittivo per il branch."""
        import random

        prefixes = {
            "cognitive": ["Focus", "Filter", "Integrate", "Balance", "Optimize"],
            "architectural": ["Restructure", "Expand", "Contract", "Rebalance", "Rebuild"],
            "memory": ["Consolidate", "Forget", "Reweight", "Reorganize", "Link"],
            "learning": ["Adapt", "Learn", "Explore", "Exploit", "Adjust"],
        }

        prefix = random.choice(prefixes.get(branch_type, ["Branch"]))
        suffix = f"D{depth}"

        if parent:
            return f"{prefix}_{parent.name}_{suffix}"
        return f"{prefix}_{suffix}"


@dataclass
class BranchEvaluationResult:
    """Risultato della valutazione di un branch."""

    branch_id: str
    ilf_score: float
    ilf_delta: float
    stability_delta: float
    accepted: bool
    reason: str
    metadata: Dict[str, Any]