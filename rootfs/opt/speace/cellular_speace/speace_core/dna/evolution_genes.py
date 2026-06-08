from typing import Any, Dict, Optional, List, Callable
from pydantic import BaseModel, Field
from enum import Enum
import time
import json


class GeneType(Enum):
    """Tipi di gene nel sistema."""
    COGNITIVE = "cognitive"
    PLASTICITY = "plasticity"
    MEMORY = "memory"
    ARCHITECTURE = "architecture"
    REGULATORY = "regulatory"


class GeneStatus(Enum):
    """Stato di espressione di un gene."""
    ACTIVE = "active"
    SILENCED = "silenced"
    MUTATED = "mutated"
    DERIVED = "derived"  # Da epigenetica


class EvolutionGene(BaseModel):
    """Gene base per l'evoluzione.

    Ogni gene è:
    - Serializzabile: può essere salvato/caricato
    - Versionabile: traccia la propria storia
    - Mutabile: può essere alterato
    - Reversibile: può tornare a uno stato precedente
    """

    name: str
    gene_type: GeneType
    value: Any
    version: int = 1
    created_at: float = Field(default_factory=time.time)
    modified_at: float = Field(default_factory=time.time)
    status: GeneStatus = GeneStatus.ACTIVE

    # Per reversibilità
    _previous_values: List[Any] = []

    def mutate(self, mutation_fn: Callable[[Any], Any]) -> "EvolutionGene":
        """Applica una mutazione al gene.

        Args:
            mutation_fn: Funzione che prende il valore attuale e restituisce il nuovo valore

        Returns:
            Nuovo gene con valore mutato
        """
        import copy

        new_gene = copy.deepcopy(self)
        new_gene._previous_values.append(copy.deepcopy(self.value))

        # Limita la storia
        if len(new_gene._previous_values) > 10:
            new_gene._previous_values = new_gene._previous_values[-10:]

        new_gene.value = mutation_fn(self.value)
        new_gene.version += 1
        new_gene.modified_at = time.time()
        new_gene.status = GeneStatus.MUTATED

        return new_gene

    def revert(self, steps: int = 1) -> Optional["EvolutionGene"]:
        """Ripristina il gene a uno stato precedente.

        Args:
            steps: Numero di passi indietro

        Returns:
            Gene ripristinato o None se non possibile
        """
        if len(self._previous_values) < steps:
            return None

        import copy
        new_gene = copy.deepcopy(self)

        # Recupera il valore
        for _ in range(steps):
            if new_gene._previous_values:
                new_gene._previous_values.pop()

        if new_gene._previous_values:
            new_gene.value = copy.deepcopy(new_gene._previous_values[-1])
        else:
            # Torna al valore base (primordiale)
            # Il valore base è il primo valore mai avuto
            pass

        new_gene.modified_at = time.time()
        new_gene.status = GeneStatus.ACTIVE

        return new_gene

    def silence(self) -> "EvolutionGene":
        """Silenzia il gene (non viene espresso)."""
        import copy
        new_gene = copy.deepcopy(self)
        new_gene.status = GeneStatus.SILENCED
        new_gene.modified_at = time.time()
        return new_gene

    def activate(self) -> "EvolutionGene":
        """Attiva il gene."""
        import copy
        new_gene = copy.deepcopy(self)
        new_gene.status = GeneStatus.ACTIVE
        new_gene.modified_at = time.time()
        return new_gene

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "gene_type": self.gene_type.value,
            "value": self.value,
            "version": self.version,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvolutionGene":
        return cls(
            name=data["name"],
            gene_type=GeneType(data["gene_type"]),
            value=data["value"],
            version=data.get("version", 1),
            created_at=data.get("created_at", time.time()),
            modified_at=data.get("modified_at", time.time()),
            status=GeneStatus(data.get("status", "active")),
        )


class CognitiveGene(EvolutionGene):
    """Gene per parametri cognitivi.

    Controlla: attenzione, memoria, apprendimento, inibizione.
    """

    def __init__(self, **data):
        if "gene_type" not in data:
            data["gene_type"] = GeneType.COGNITIVE
        super().__init__(**data)

    @classmethod
    def create_attention_gene(
        cls,
        name: str,
        spread: float = 0.5,
    ) -> "CognitiveGene":
        return cls(
            name=name,
            value={"spread": spread, "focus": 1.0 - spread},
        )

    @classmethod
    def create_learning_gene(
        cls,
        name: str,
        rate: float = 0.1,
    ) -> "CognitiveGene":
        return cls(
            name=name,
            value={"rate": rate, "momentum": 0.9, "decay": 0.01},
        )


class PlasticityGene(EvolutionGene):
    """Gene per la neuroplasticità.

    Controlla quanto rapidamente e in quale direzione
    cambiano le connessioni neurali.
    """

    def __init__(self, **data):
        if "gene_type" not in data:
            data["gene_type"] = GeneType.PLASTICITY
        super().__init__(**data)

    @classmethod
    def create_plasticity_gene(
        cls,
        name: str,
        rate: float = 0.05,
        threshold: float = 0.5,
    ) -> "PlasticityGene":
        return cls(
            name=name,
            value={
                "rate": rate,
                "threshold": threshold,
                "type": "hebbian",
            },
        )


class MemoryGene(EvolutionGene):
    """Gene per strategie di memoria.

    Controlla consolidazione, recupero, dimenticanza.
    """

    def __init__(self, **data):
        if "gene_type" not in data:
            data["gene_type"] = GeneType.MEMORY
        super().__init__(**data)

    @classmethod
    def create_memory_gene(
        cls,
        name: str,
        persistence: float = 0.7,
        consolidation_threshold: float = 0.6,
    ) -> "MemoryGene":
        return cls(
            name=name,
            value={
                "persistence": persistence,
                "consolidation_threshold": consolidation_threshold,
                "forgetting_rate": 1.0 - persistence,
            },
        )


class ArchitectureGene(EvolutionGene):
    """Gene per parametri architetturali.

    Controlla la struttura dell'organismo: connettività,
    specializzazione regionale, routing.
    """

    def __init__(self, **data):
        if "gene_type" not in data:
            data["gene_type"] = GeneType.ARCHITECTURE
        super().__init__(**data)

    @classmethod
    def create_connectivity_gene(
        cls,
        name: str,
        density: float = 0.5,
        fan_in: int = 10,
        fan_out: int = 10,
    ) -> "ArchitectureGene":
        return cls(
            name=name,
            value={
                "density": density,
                "fan_in": fan_in,
                "fan_out": fan_out,
            },
        )


class GeneFactory:
    """Factory per creare geni preconfigurati."""

    @staticmethod
    def create_gene(
        gene_type: GeneType,
        name: str,
        **kwargs,
    ) -> EvolutionGene:
        """Crea un gene del tipo specificato."""
        if gene_type == GeneType.COGNITIVE:
            return CognitiveGene(name=name, value=kwargs)
        elif gene_type == GeneType.PLASTICITY:
            return PlasticityGene(name=name, value=kwargs)
        elif gene_type == GeneType.MEMORY:
            return MemoryGene(name=name, value=kwargs)
        elif gene_type == GeneType.ARCHITECTURE:
            return ArchitectureGene(name=name, value=kwargs)
        else:
            return EvolutionGene(name=name, gene_type=gene_type, value=kwargs)

    @staticmethod
    def create_default_genome() -> Dict[str, EvolutionGene]:
        """Crea un genoma di default con i geni base."""
        return {
            "attention": CognitiveGene.create_attention_gene("attention"),
            "learning": CognitiveGene.create_learning_gene("learning"),
            "plasticity": PlasticityGene.create_plasticity_gene("plasticity"),
            "memory_persistence": MemoryGene.create_memory_gene("memory_persistence"),
            "connectivity": ArchitectureGene.create_connectivity_gene("connectivity"),
        }


class GeneRegistry:
    """Registro centrale dei geni dell'organismo.

    Permette lookup, versioning e tracking.
    """

    def __init__(self):
        self._genes: Dict[str, EvolutionGene] = {}
        self._history: List[Dict[str, Any]] = []

    def register(self, gene: EvolutionGene) -> None:
        """Registra un gene."""
        import copy
        self._genes[gene.name] = gene
        self._history.append({
            "timestamp": time.time(),
            "action": "register",
            "gene": gene.to_dict(),
        })

    def get(self, name: str) -> Optional[EvolutionGene]:
        return self._genes.get(name)

    def get_all(self) -> Dict[str, EvolutionGene]:
        return dict(self._genes)

    def get_by_type(self, gene_type: GeneType) -> List[EvolutionGene]:
        return [g for g in self._genes.values() if g.gene_type == gene_type]

    def update(self, gene: EvolutionGene) -> None:
        """Aggiorna un gene esistente."""
        self.register(gene)

    def mutate_gene(
        self,
        name: str,
        mutation_fn: Callable[[Any], Any],
    ) -> Optional[EvolutionGene]:
        """Muta un gene specifico."""
        gene = self._genes.get(name)
        if gene is None:
            return None

        mutated = gene.mutate(mutation_fn)
        self.register(mutated)
        return mutated

    def revert_gene(self, name: str, steps: int = 1) -> Optional[EvolutionGene]:
        """Ripristina un gene."""
        gene = self._genes.get(name)
        if gene is None:
            return None

        reverted = gene.revert(steps)
        if reverted:
            self.register(reverted)
        return reverted

    def get_history(self, gene_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Restituisce la storia dei geni."""
        if gene_name:
            return [h for h in self._history if h["gene"]["name"] == gene_name]
        return list(self._history)

    def export_genome(self) -> str:
        """Esporta il genoma come JSON."""
        return json.dumps(
            {name: gene.to_dict() for name, gene in self._genes.items()},
            indent=2,
        )

    def import_genome(self, json_str: str) -> None:
        """Importa un genoma da JSON."""
        data = json.loads(json_str)
        for name, gene_data in data.items():
            gene = EvolutionGene.from_dict(gene_data)
            self.register(gene)