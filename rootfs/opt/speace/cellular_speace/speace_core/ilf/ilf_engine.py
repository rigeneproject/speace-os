from typing import Optional, Dict, Any, List, TYPE_CHECKING
from dataclasses import dataclass, field

from speace_core.ilf.ilf_state import ILFState
from speace_core.ilf.coherence_metrics import CoherenceMetrics

if TYPE_CHECKING:
    from speace_core.dna.cognitive_genome import CognitiveGenome


@dataclass
class ILFMetrics:
    """Container per tutte le metriche di input all'ILF."""

    # Stato interno dell'organismo
    region_outputs: Dict[str, float] = field(default_factory=dict)
    cell_states: Dict[str, float] = field(default_factory=dict)
    cell_types: Dict[str, str] = field(default_factory=dict)
    energy_levels: Dict[str, float] = field(default_factory=dict)
    connectivity_matrix: Dict[str, List[str]] = field(default_factory=dict)
    signal_trains: Dict[str, List[float]] = field(default_factory=dict)

    # Memoria e apprendimento
    memory_utilization: float = 0.0
    memory_retention: float = 0.0
    learning_rate: float = 0.0
    error_rate: float = 0.0

    # Obiettivi
    goal_activations: Dict[str, float] = field(default_factory=dict)
    goal_progress: Dict[str, float] = field(default_factory=dict)

    # Storia per stabilità
    ilf_history: List[float] = field(default_factory=list)

    # Metadati
    metadata: Dict[str, Any] = field(default_factory=dict)


class ILFEngine:
    """Informational Logical Field Engine.

    Funzione globale di valutazione della coerenza dell'organismo.
    Fornisce un gradiente evolutivo per guidare apprendimento ed evoluzione.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._metrics_history: List[ILFMetrics] = []
        self._cycle: int = 0

    # ------------------------------------------------------------------ #
    # Compute Methods
    # ------------------------------------------------------------------ #

    def compute_coherence(self, metrics: ILFMetrics) -> float:
        """Misura la coerenza funzionale dell'organismo.

        Combina:
        - Functional integration: quanto le regioni lavorano insieme
        - Internal diversity: quanto i tipi cellulari sono diversificati
        - Cognitive stability: quanto l'ILF è stabile nel tempo
        """
        cm = CoherenceMetrics()

        integration = cm.compute_functional_integration(
            metrics.region_outputs,
            metrics.connectivity_matrix if metrics.connectivity_matrix else None,
        )

        diversity = cm.compute_internal_diversity(
            metrics.cell_states,
            metrics.cell_types if metrics.cell_types else None,
        )

        stability = cm.compute_cognitive_stability(
            metrics.ilf_history,
            window=self.config.get("stability_window", 10),
        )

        homeostatic = cm.compute_homeostatic_balance(
            metrics.energy_levels,
            target_energy=self.config.get("target_energy", 0.7),
        )

        # Pesi configurabili
        weights = self.config.get(
            "coherence_weights",
            {
                "integration": 0.35,
                "diversity": 0.20,
                "stability": 0.25,
                "homeostatic": 0.20,
            },
        )

        coherence = (
            weights["integration"] * integration
            + weights["diversity"] * diversity
            + weights["stability"] * stability
            + weights["homeostatic"] * homeostatic
        )

        return max(0.0, min(1.0, coherence))

    def compute_goal_alignment(self, metrics: ILFMetrics) -> float:
        """Misura quanto l'attivazione delle regioni è allineata agli obiettivi.

        Un organismo ben allineato:
        - Ha regioni attive proporzionali al progresso degli obiettivi
        - Non spreca risorse su obiettivi già raggiunti o non rilevanti
        """
        if not metrics.goal_activations:
            return 0.5  # Neutral se nessun obiettivo

        activations = list(metrics.goal_activations.values())
        progress_values = list(metrics.goal_progress.values())

        if not activations or not progress_values:
            return 0.5

        # Calcola allineamento: alta attivazione per alto progresso
        # Bassa attivazione per obiettivi stagnanti o completati

        alignment_scores = []
        for goal_id in metrics.goal_activations:
            activation = metrics.goal_activations.get(goal_id, 0.0)
            progress = metrics.goal_progress.get(goal_id, 0.0)

            # Idealmente: attivazione proporzionale a (1 - progress)
            # cioè più un obiettivo è lontano, più risorse richiede
            ideal_activation = (1.0 - progress) * 0.8 + 0.1
            deviation = abs(activation - ideal_activation)
            score = max(0.0, 1.0 - deviation * 2)
            alignment_scores.append(score)

        return sum(alignment_scores) / len(alignment_scores) if alignment_scores else 0.5

    def compute_memory_continuity(self, metrics: ILFMetrics) -> float:
        """Misura la continuità e qualità della memoria.

        Tiene conto di:
        - Utilizzo della memoria (non troppo piena, non troppo vuota)
        - Retention (quanto viene conservato)
        - Learning rate (apprendimento in corso)
        """
        # Utilizzo ottimale: né troppo alto né troppo basso
        utilization = metrics.memory_utilization
        optimal_util = self.config.get("optimal_memory_utilization", 0.6)
        util_score = 1.0 - abs(utilization - optimal_util)

        # Retention
        retention = metrics.memory_retention

        # Learning rate (normalizzato)
        learning = min(1.0, metrics.learning_rate * 10)

        # Error rate (invertito)
        error_score = max(0.0, 1.0 - metrics.error_rate * 5)

        weights = self.config.get(
            "continuity_weights",
            {"utilization": 0.25, "retention": 0.35, "learning": 0.20, "error": 0.20},
        )

        continuity = (
            weights["utilization"] * util_score
            + weights["retention"] * retention
            + weights["learning"] * learning
            + weights["error"] * error_score
        )

        return max(0.0, min(1.0, continuity))

    def compute_adaptation_score(self, metrics: ILFMetrics) -> float:
        """Misura la capacità di adattamento dell'organismo.

        Basato su:
        - Learning rate recente
        - Error rate (basso è meglio)
        - Diversità delle risposte (plasticità)
        """
        # Learning speed
        lr = min(1.0, metrics.learning_rate * 10)

        # Error handling
        err = max(0.0, 1.0 - metrics.error_rate * 5)

        # Response diversity (dalla varianza delle uscite regionali)
        outputs = list(metrics.region_outputs.values())
        if len(outputs) >= 2:
            mean = sum(outputs) / len(outputs)
            variance = sum((o - mean) ** 2 for o in outputs) / len(outputs)
            diversity = min(1.0, math.sqrt(variance) * 3)
        else:
            diversity = 0.5

        weights = self.config.get(
            "adaptation_weights",
            {"learning": 0.40, "error_handling": 0.35, "diversity": 0.25},
        )

        adaptation = (
            weights["learning"] * lr
            + weights["error_handling"] * err
            + weights["diversity"] * diversity
        )

        return max(0.0, min(1.0, adaptation))

    def compute_ilf(self, metrics: ILFMetrics) -> ILFState:
        """Calcola l'ILF completo.

        Combina tutte le componenti in un singolo score.
        """
        coherence = self.compute_coherence(metrics)
        goal_alignment = self.compute_goal_alignment(metrics)
        continuity = self.compute_memory_continuity(metrics)
        adaptation = self.compute_adaptation_score(metrics)

        # Pesi principali per l'ILF finale
        weights = self.config.get(
            "ilf_weights",
            {
                "coherence": 0.35,
                "adaptation": 0.25,
                "continuity": 0.25,
                "goal_alignment": 0.15,
            },
        )

        ilf_value = (
            weights["coherence"] * coherence
            + weights["adaptation"] * adaptation
            + weights["continuity"] * continuity
            + weights["goal_alignment"] * goal_alignment
        )

        # Calcola metriche dettagliate
        cm = CoherenceMetrics()
        detailed_integration = cm.compute_functional_integration(
            metrics.region_outputs,
            metrics.connectivity_matrix if metrics.connectivity_matrix else None,
        )
        detailed_diversity = cm.compute_internal_diversity(
            metrics.cell_states,
            metrics.cell_types if metrics.cell_types else None,
        )
        detailed_stability = cm.compute_cognitive_stability(
            metrics.ilf_history,
            window=self.config.get("stability_window", 10),
        )

        state = ILFState(
            timestamp=metrics.metadata.get("timestamp", 0.0),
            cycle=self._cycle,
            coherence=coherence,
            adaptation=adaptation,
            continuity=continuity,
            goal_alignment=goal_alignment,
            value=max(0.0, min(1.0, ilf_value)),
            internal_diversity=detailed_diversity,
            functional_integration=detailed_integration,
            cognitive_stability=detailed_stability,
            learning_efficiency=min(1.0, metrics.learning_rate * 10),
            error_rate=metrics.error_rate,
            metadata=metrics.metadata,
        )

        self._cycle += 1
        return state

    # ------------------------------------------------------------------ #
    # Utility Methods
    # ------------------------------------------------------------------ #

    def compute_delta_ilf(
        self, current: ILFState, previous: Optional[ILFState] = None
    ) -> float:
        """Calcola la variazione di ILF tra due stati."""
        if previous is None:
            return 0.0
        return current.value - previous.value

    def detect_stagnation(
        self, history: List[ILFState], window: int = 5, threshold: float = 0.01
    ) -> bool:
        """Rileva stagnazione: l'ILF non migliora da N cicli."""
        if len(history) < window:
            return False

        recent = history[-window:]
        max_ilf = max(s.value for s in recent)
        min_ilf = min(s.value for s in recent)

        return (max_ilf - min_ilf) < threshold

    def get_ilf_trend(self, history: List[ILFState], window: int = 10) -> str:
        """Restituisce il trend dell'ILF: 'improving', 'declining', 'stable'."""
        if len(history) < 2:
            return "stable"

        recent = history[-window:]
        if len(recent) < 2:
            return "stable"

        # Linear regression semplice
        n = len(recent)
        indices = list(range(n))
        values = [s.value for s in recent]

        mean_x = sum(indices) / n
        mean_y = sum(values) / n

        numerator = sum((indices[i] - mean_x) * (values[i] - mean_y) for i in range(n))
        denominator = sum((indices[i] - mean_x) ** 2 for i in range(n))

        if denominator == 0:
            return "stable"

        slope = numerator / denominator

        if slope > 0.005:
            return "improving"
        elif slope < -0.005:
            return "declining"
        return "stable"

    def create_default_metrics(self) -> ILFMetrics:
        """Crea un metrics object con valori di default."""
        return ILFMetrics(
            region_outputs={},
            cell_states={},
            cell_types={},
            energy_levels={},
            connectivity_matrix={},
            signal_trains={},
            memory_utilization=0.5,
            memory_retention=0.5,
            learning_rate=0.05,
            error_rate=0.1,
            goal_activations={},
            goal_progress={},
            ilf_history=[],
            metadata={"timestamp": 0.0},
        )


# Import math per compute_adaptation_score
import math