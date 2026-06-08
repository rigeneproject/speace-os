from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Callable
from enum import Enum
import time


class EpigeneticTagType(Enum):
    """Tipi di tag epigenetici."""
    METHYLATION = "methylation"
    ACETYLATION = "acetylation"
    HISTONE_MODIFICATION = "histone_modification"
    SILENCING = "silencing"
    ACTIVATION = "activation"


@dataclass
class EpigeneticTag:
    """Singolo tag epigenetico.

    Modula l'espressione genica senza modificare il DNA.
    """
    gene_name: str
    tag_type: EpigeneticTagType
    level: float  # 0.0 = no effect, 1.0 = max effect
    applied_at: float
    expires_at: Optional[float] = None
    source: str = "system"  # "system", "evolution", "experience"

    def is_active(self, current_time: Optional[float] = None) -> bool:
        """Il tag è ancora attivo?"""
        if self.expires_at is None:
            return True
        t = current_time or time.time()
        return t < self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gene_name": self.gene_name,
            "tag_type": self.tag_type.value,
            "level": self.level,
            "applied_at": self.applied_at,
            "expires_at": self.expires_at,
            "source": self.source,
        }


@dataclass
class ContextModulation:
    """Modulazione contestuale dell'espressione genica.

    Applicata in base al contesto当前 (stato interno/esterno).
    """
    context_key: str  # e.g., "stress_level", "energy_available"
    condition: str  # e.g., "greater_than", "less_than", "equals"
    threshold: float
    modulation: float  # Fattore moltiplicativo applicato al gene

    def evaluate(self, context_state: Dict[str, float]) -> bool:
        """Valuta se la modulazione si applica."""
        value = context_state.get(self.context_key, 0.0)
        if self.condition == "greater_than":
            return value > self.threshold
        elif self.condition == "less_than":
            return value < self.threshold
        elif self.condition == "equals":
            return abs(value - self.threshold) < 0.01
        return False


class EpigeneticTagsManager:
    """Gestisce i tag epigenetici dell'organismo.

    Responsabilità:
    - Applicare tag di metilazione/acetilazione
    - Rimuovere tag scaduti
    - Calcolare l'effetto combinato dei tag su ogni gene
    """

    def __init__(
        self,
        default_methylation_rate: float = 0.3,
        default_acetylation_rate: float = 0.2,
    ):
        self.default_methylation_rate = default_methylation_rate
        self.default_acetylation_rate = default_acetylation_rate

        self._tags: Dict[str, List[EpigeneticTag]] = {}  # gene_name -> tags
        self._context_modulations: List[ContextModulation] = []

        # Storia per audit
        self._history: List[Dict[str, Any]] = []

    def apply_methylation(
        self,
        gene_name: str,
        level: float,
        duration: Optional[float] = None,
        source: str = "system",
    ) -> EpigeneticTag:
        """Applica metilazione a un gene (sopprime espressione)."""
        tag = EpigeneticTag(
            gene_name=gene_name,
            tag_type=EpigeneticTagType.METHYLATION,
            level=min(1.0, max(0.0, level)),
            applied_at=time.time(),
            expires_at=time.time() + duration if duration else None,
            source=source,
        )

        self._add_tag(tag)
        return tag

    def apply_acetylation(
        self,
        gene_name: str,
        level: float,
        duration: Optional[float] = None,
        source: str = "system",
    ) -> EpigeneticTag:
        """Applica acetilazione a un gene (aumenta espressione)."""
        tag = EpigeneticTag(
            gene_name=gene_name,
            tag_type=EpigeneticTagType.ACETYLATION,
            level=min(1.0, max(0.0, level)),
            applied_at=time.time(),
            expires_at=time.time() + duration if duration else None,
            source=source,
        )

        self._add_tag(tag)
        return tag

    def silence_gene(
        self,
        gene_name: str,
        duration: Optional[float] = None,
    ) -> EpigeneticTag:
        """Silenzia completamente un gene."""
        tag = EpigeneticTag(
            gene_name=gene_name,
            tag_type=EpigeneticTagType.SILENCING,
            level=1.0,
            applied_at=time.time(),
            expires_at=time.time() + duration if duration else None,
            source="system",
        )

        self._add_tag(tag)
        return tag

    def activate_gene(
        self,
        gene_name: str,
        duration: Optional[float] = None,
    ) -> EpigeneticTag:
        """Attiva un gene silenziato."""
        tag = EpigeneticTag(
            gene_name=gene_name,
            tag_type=EpigeneticTagType.ACTIVATION,
            level=1.0,
            applied_at=time.time(),
            expires_at=time.time() + duration if duration else None,
            source="system",
        )

        self._add_tag(tag)
        return tag

    def add_context_modulation(self, modulation: ContextModulation) -> None:
        """Aggiunge una modulazione contestuale."""
        self._context_modulations.append(modulation)

    def _add_tag(self, tag: EpigeneticTag) -> None:
        """Aggiunge un tag alla lista."""
        if tag.gene_name not in self._tags:
            self._tags[tag.gene_name] = []
        self._tags[tag.gene_name].append(tag)

        self._history.append({
            "timestamp": time.time(),
            "action": "apply_tag",
            "tag": tag.to_dict(),
        })

    def get_expression_modifier(
        self,
        gene_name: str,
        context_state: Optional[Dict[str, float]] = None,
    ) -> float:
        """Calcola il modificatore di espressione per un gene.

        0.0 = gene completamente silenziato
        1.0 = espressione normale
        >1.0 = espressione amplificata
        """
        tags = self._tags.get(gene_name, [])
        current_time = time.time()

        # Filtra tag attivi
        active_tags = [t for t in tags if t.is_active(current_time)]

        if not active_tags:
            return 1.0

        modifier = 1.0

        for tag in active_tags:
            if tag.tag_type == EpigeneticTagType.SILENCING:
                return 0.0  # Silenziamento totale
            elif tag.tag_type == EpigeneticTagType.METHYLATION:
                modifier -= tag.level * 0.5  # Riduce espressione
            elif tag.tag_type == EpigeneticTagType.ACETYLATION:
                modifier += tag.level * 0.3  # Aumenta espressione
            elif tag.tag_type == EpigeneticTagType.ACTIVATION:
                modifier += tag.level * 0.2

        # Applica modulazioni contestuali
        if context_state:
            for mod in self._context_modulations:
                if mod.evaluate(context_state):
                    modifier *= mod.modulation

        return max(0.0, min(2.0, modifier))

    def cleanup_expired_tags(self) -> int:
        """Rimuove i tag scaduti. Returns count of removed."""
        current_time = time.time()
        removed = 0

        for gene_name in list(self._tags.keys()):
            before = len(self._tags[gene_name])
            self._tags[gene_name] = [
                t for t in self._tags[gene_name] if t.is_active(current_time)
            ]
            removed += before - len(self._tags[gene_name])

            if not self._tags[gene_name]:
                del self._tags[gene_name]

        return removed

    def get_active_tags(self, gene_name: Optional[str] = None) -> List[EpigeneticTag]:
        """Restituisce i tag attivi per un gene o tutti."""
        current_time = time.time()

        if gene_name:
            return [t for t in self._tags.get(gene_name, []) if t.is_active(current_time)]

        result = []
        for tags in self._tags.values():
            result.extend([t for t in tags if t.is_active(current_time)])
        return result

    def get_tag_summary(self) -> Dict[str, Any]:
        """Restituisce un riepilogo dei tag."""
        return {
            "total_genes_tagged": len(self._tags),
            "total_active_tags": len(self.get_active_tags()),
            "by_type": {
                "methylation": len([t for t in self.get_active_tags() if t.tag_type == EpigeneticTagType.METHYLATION]),
                "acetylation": len([t for t in self.get_active_tags() if t.tag_type == EpigeneticTagType.ACETYLATION]),
                "silencing": len([t for t in self.get_active_tags() if t.tag_type == EpigeneticTagType.SILENCING]),
                "activation": len([t for t in self.get_active_tags() if t.tag_type == EpigeneticTagType.ACTIVATION]),
            },
            "context_modulations": len(self._context_modulations),
        }

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._history[-limit:]

    def clear_all_tags(self) -> None:
        """Rimuove tutti i tag. Usare con cautela."""
        self._tags.clear()
        self._history.append({
            "timestamp": time.time(),
            "action": "clear_all",
        })


class AdaptiveExpressionEngine:
    """Motore per l'espressione adattiva dei geni.

    Modifica dinamicamente l'espressione in base a:
    - Stato interno (energia, stress, etc.)
    - Segnali ambientali
    - Memoria e esperienza
    """

    def __init__(self, tags_manager: EpigeneticTagsManager):
        self.tags = tags_manager

        # Regole di espressione adattiva
        self._expression_rules: Dict[str, Callable[[Dict[str, float]], float]] = {}

        # Stato corrente
        self._current_context: Dict[str, float] = {}

    def register_expression_rule(
        self,
        gene_name: str,
        rule_fn: Callable[[Dict[str, float]], float],
    ) -> None:
        """Registra una regola di espressione per un gene.

        La funzione prinde lo stato del contesto e restituisce
        un modificatore di espressione.
        """
        self._expression_rules[gene_name] = rule_fn

    def update_context(self, context: Dict[str, float]) -> None:
        """Aggiorna il contesto corrente."""
        self._current_context.update(context)

    def apply_adaptive_expression(self, gene_name: str) -> float:
        """Applica espressione adattiva a un gene.

        Returns:
            Modificatore di espressione
        """
        if gene_name not in self._expression_rules:
            return 1.0

        rule = self._expression_rules[gene_name]
        modifier = rule(self._current_context)

        # Se il modificatore è > 1, aumenta espressione
        if modifier > 1.0:
            self.tags.apply_acetylation(gene_name, modifier - 1.0)
        elif modifier < 1.0:
            self.tags.apply_methylation(gene_name, 1.0 - modifier)

        return modifier

    def apply_all_adaptive_expressions(self) -> Dict[str, float]:
        """Applica espressione adattiva a tutti i geni con regole."""
        results = {}
        for gene_name in self._expression_rules:
            results[gene_name] = self.apply_adaptive_expression(gene_name)
        return results

    def create_default_rules(self) -> None:
        """Crea regole di default basate su stati comuni."""

        # Alta energia = più plasticità
        self.register_expression_rule(
            "plasticity",
            lambda ctx: 1.5 if ctx.get("energy", 0.5) > 0.7 else 0.8,
        )

        # Basso stress = più apprendimento
        self.register_expression_rule(
            "learning",
            lambda ctx: 1.3 if ctx.get("stress", 0.5) < 0.3 else 0.7,
        )

        # Alta attività = più attenzione
        self.register_expression_rule(
            "attention",
            lambda ctx: 1.2 if ctx.get("activity", 0.5) > 0.6 else 1.0,
        )