from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
import time
import hashlib
import json

from speace_core.ilf.ilf_state import ILFState
from speace_core.ilf.ilf_engine import ILFEngine, ILFMetrics
from speace_core.ilf.coherence_metrics import CoherenceMetrics


@dataclass
class FieldState:
    """Stato globale del campo informazionale.

    Questo oggetto viene broadcast a TUTTI i sottosistemi
    ad ogni ciclo. Ogni sottosistema lo usa per modificare
    il proprio comportamento.
    """

    timestamp: float
    cycle: int

    # Metriche globali
    ilf_value: float = 0.5
    coherence: float = 0.5
    adaptation: float = 0.5
    continuity: float = 0.5
    goal_alignment: float = 0.5

    # Gradienti per aggiornamento
    coherence_gradient: float = 0.0  # +1 = migliora, -1 = peggiora
    adaptation_gradient: float = 0.0
    continuity_gradient: float = 0.0

    # Vettore di stato per ogni sottosistema
    subsystem_states: Dict[str, float] = field(default_factory=dict)

    # Rumore/distorsione del campo
    field_noise: float = 0.0
    field_stability: float = 1.0

    # Canali di comunicazione endocrina — bisogni/obiettivi/allarmi/intenzioni
    # Ogni sottosistema può leggere questi canali e adattare il comportamento.
    needs: Dict[str, float] = field(default_factory=dict)
    goals: Dict[str, float] = field(default_factory=dict)
    alarms: List[str] = field(default_factory=list)
    intentions: Dict[str, Any] = field(default_factory=dict)

    # Histore recente per calcoli ricorsivi
    recent_cycles: int = 5

    def get_gradient(self, subsystem: str) -> float:
        """Restituisce il gradiente per un sottosistema specifico."""
        # Calcola gradiente basato su performance del sottosistema
        sub_state = self.subsystem_states.get(subsystem, 0.5)
        return sub_state - 0.5  # Deviazione dal centro

    def is_coherent(self) -> bool:
        return self.ilf_value >= 0.4 and self.field_stability >= 0.6

    def needs_intervention(self) -> bool:
        """Il campo richiede intervento evolutivo?"""
        return self.ilf_value < 0.35 or self.field_noise > 0.3

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "cycle": self.cycle,
            "ilf_value": self.ilf_value,
            "coherence": self.coherence,
            "adaptation": self.adaptation,
            "continuity": self.continuity,
            "goal_alignment": self.goal_alignment,
            "coherence_gradient": self.coherence_gradient,
            "adaptation_gradient": self.adaptation_gradient,
            "continuity_gradient": self.continuity_gradient,
            "subsystem_states": self.subsystem_states,
            "field_noise": self.field_noise,
            "field_stability": self.field_stability,
            "needs": self.needs,
            "goals": self.goals,
            "alarms": self.alarms,
            "intentions": self.intentions,
        }


@dataclass
class SubsystemInterface:
    """Interfaccia standard per sottosistemi che ricevono FieldState."""

    name: str
    update_fn: Callable[["InformationalField", FieldState], None]
    weight: float = 1.0  # Quanto questo sottosistema influenza il campo


class InformationalField:
    """ILF come campo dinamico.

    Non è più un osservatore che misura e assegna punteggi.
    È la dinamica che collega tutto - ogni sottosistema
    legge continuamente lo stato globale e modifica il
    proprio comportamento.

    Schema:
        modulo ↔ campo ↔ modulo

    Non esiste più:
        modulo → output

    Ma:
        modulo → campo → modulo
    """

    def __init__(
        self,
        ilf_engine: Optional[ILFEngine] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.ilf_engine = ilf_engine or ILFEngine()
        self.config = config or {}

        # Sottosistemi registrati
        self._subsystems: Dict[str, SubsystemInterface] = {}

        # Stato del campo
        self._current_state: Optional[FieldState] = None
        self._state_history: List[FieldState] = []

        # Metriche di coerenza globale
        self._coherence_history: List[float] = []
        self._last_ilf: float = 0.5

        # Callbacks per eventi
        self._on_state_change: List[Callable[[FieldState], None]] = []
        self._on_coherence_change: List[Callable[[float, float], None]] = []

    # ------------------------------------------------------------------ #
    # Registration
    # ------------------------------------------------------------------ #

    def register_subsystem(
        self,
        name: str,
        update_fn: Callable[["InformationalField", FieldState], None],
        weight: float = 1.0,
    ) -> None:
        """Registra un sottosistema che riceverà FieldState."""
        self._subsystems[name] = SubsystemInterface(
            name=name,
            update_fn=update_fn,
            weight=weight,
        )

    def unregister_subsystem(self, name: str) -> None:
        if name in self._subsystems:
            del self._subsystems[name]

    # ------------------------------------------------------------------ #
    # Core Loop
    # ------------------------------------------------------------------ #

    def observe(self) -> Dict[str, Any]:
        """Fase 1: Raccoglie dati da tutti i sottosistemi.

        Ogni sottosistema fornisce il proprio stato locale.
        """
        subsystem_data = {}

        for name, iface in self._subsystems.items():
            try:
                # Chiama la funzione di osservazione del sottosistema
                data = iface.update_fn(self, self._current_state)
                subsystem_data[name] = data
            except Exception:
                subsystem_data[name] = {"error": True}

        return subsystem_data

    def compute_coherence(self, metrics: ILFMetrics) -> float:
        """Fase 2: Calcola coerenza globale.

        Usa l'ILF engine per computare il campo.
        """
        return self.ilf_engine.compute_coherence(metrics)

    def generate_gradients(self) -> Dict[str, float]:
        """Fase 3: Genera gradienti per ogni sottosistema.

        I gradienti indicano quanto e in quale direzione
        ogni sottosistema dovrebbe modificare il proprio comportamento.
        """
        if not self._current_state:
            return {}

        gradients = {}

        # Gradiente di coerenza
        for name in self._subsystems:
            sub_state = self._current_state.subsystem_states.get(name, 0.5)
            # Gradiente = quanto il sottosistema è fuori fase col campo
            gradients[name] = (self._current_state.coherence - sub_state) * self._current_state.field_stability

        return gradients

    def broadcast(self, state: FieldState) -> None:
        """Fase 4: Broadcast dello stato a tutti i sottosistemi.

        Ogni sottosistema riceve FieldState e aggiorna il proprio comportamento.
        """
        self._current_state = state
        self._state_history.append(state)

        # Limita la storia
        max_history = self.config.get("max_history", 1000)
        if len(self._state_history) > max_history:
            self._state_history = self._state_history[-max_history:]

        # Notifica callbacks
        for callback in self._on_state_change:
            try:
                callback(state)
            except Exception:
                pass

        # Notifica cambi di coerenza
        if self._last_ilf != state.ilf_value:
            for callback in self._on_coherence_change:
                try:
                    callback(self._last_ilf, state.ilf_value)
                except Exception:
                    pass
            self._last_ilf = state.ilf_value

    def update(
        self,
        subsystem_metrics: Dict[str, ILFMetrics],
        field_messages: Optional[Dict[str, Any]] = None,
    ) -> FieldState:
        """Ciclo completo di aggiornamento del campo.

        Args:
            subsystem_metrics: Dict di metriche per ogni sottosistema
            field_messages: Dict opzionale con canali needs/goals/alarms/intentions

        Returns:
            FieldState broadcast a tutti i sottosistemi
        """
        # Osserva
        obs = self.observe()

        # Aggrega metriche
        aggregated = self._aggregate_metrics(subsystem_metrics)

        # Computa ILF
        ilf_state = self.ilf_engine.compute_ilf(aggregated)

        # Genera gradiente
        coherence_delta = ilf_state.coherence - (self._coherence_history[-1] if self._coherence_history else 0.5)

        # Messaggi endocrini (needs/goals/alarms/intentions)
        msg = field_messages or {}

        # Costruisci FieldState
        state = FieldState(
            timestamp=time.time(),
            cycle=ilf_state.cycle,
            ilf_value=ilf_state.value,
            coherence=ilf_state.coherence,
            adaptation=ilf_state.adaptation,
            continuity=ilf_state.continuity,
            goal_alignment=ilf_state.goal_alignment,
            coherence_gradient=coherence_delta,
            adaptation_gradient=ilf_state.adaptation - (self._state_history[-1].adaptation if self._state_history else 0.5),
            continuity_gradient=ilf_state.continuity - (self._state_history[-1].continuity if self._state_history else 0.5),
            subsystem_states=self._extract_subsystem_states(subsystem_metrics),
            field_noise=self._calculate_field_noise(aggregated),
            field_stability=ilf_state.cognitive_stability,
            needs=msg.get("needs", {}),
            goals=msg.get("goals", {}),
            alarms=msg.get("alarms", []),
            intentions=msg.get("intentions", {}),
        )

        # Broadcast
        self.broadcast(state)

        # Aggiorna storia coerenza
        self._coherence_history.append(ilf_state.coherence)
        if len(self._coherence_history) > 50:
            self._coherence_history = self._coherence_history[-50:]

        return state

    def _aggregate_metrics(
        self, subsystem_metrics: Dict[str, ILFMetrics]
    ) -> ILFMetrics:
        """Aggrega metriche da tutti i sottosistemi.

       加权 average basato su pesi sottosistemi.
        """
        if not subsystem_metrics:
            return self.ilf_engine.create_default_metrics()

        total_weight = sum(
            self._subsystems.get(name, SubsystemInterface(name=name, update_fn=lambda *a: None)).weight
            for name in subsystem_metrics.keys()
        )

        if total_weight == 0:
            return list(subsystem_metrics.values())[0]

        # Aggrega
        aggregated = ILFMetrics()

        for name, metrics in subsystem_metrics.items():
            weight = self._subsystems.get(name, SubsystemInterface(name=name, update_fn=lambda *a: None)).weight
            norm_weight = weight / total_weight

            # Merge region outputs
            for region, output in metrics.region_outputs.items():
                if region not in aggregated.region_outputs:
                    aggregated.region_outputs[region] = output * norm_weight
                else:
                    aggregated.region_outputs[region] += output * norm_weight

            # Merge cell states
            for cell_id, state in metrics.cell_states.items():
                if cell_id not in aggregated.cell_states:
                    aggregated.cell_states[cell_id] = state * norm_weight
                else:
                    aggregated.cell_states[cell_id] += state * norm_weight

            # Merge energy levels
            for region, energy in metrics.energy_levels.items():
                if region not in aggregated.energy_levels:
                    aggregated.energy_levels[region] = energy * norm_weight
                else:
                    aggregated.energy_levels[region] += energy * norm_weight

            # Merge goal activations
            for goal_id, activation in metrics.goal_activations.items():
                if goal_id not in aggregated.goal_activations:
                    aggregated.goal_activations[goal_id] = activation * norm_weight
                else:
                    aggregated.goal_activations[goal_id] += activation * norm_weight

            # Accumula metrics scalari
            aggregated.memory_utilization += metrics.memory_utilization * norm_weight
            aggregated.memory_retention += metrics.memory_retention * norm_weight
            aggregated.learning_rate += metrics.learning_rate * norm_weight
            aggregated.error_rate += metrics.error_rate * norm_weight * 0  # Error should average differently

        return aggregated

    def _extract_subsystem_states(
        self, subsystem_metrics: Dict[str, ILFMetrics]
    ) -> Dict[str, float]:
        """Estrae lo stato di ogni sottosistema per il FieldState."""
        states = {}
        for name, metrics in subsystem_metrics.items():
            # Calcola uno score normalizzato per il sottosistema
            score = (
                metrics.memory_utilization * 0.3 +
                metrics.memory_retention * 0.3 +
                (1.0 - metrics.error_rate) * 0.4
            )
            states[name] = min(1.0, max(0.0, score))
        return states

    def _calculate_field_noise(self, metrics: ILFMetrics) -> float:
        """Calcola il rumore/distorsione nel campo.

        Alto rumore = sottosistemi non sincronizzati.
        """
        if not metrics.region_outputs:
            return 0.0

        values = list(metrics.region_outputs.values())
        if len(values) < 2:
            return 0.0

        # Variance dei outputs = rumore
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)

        # Normalizza a 0-1
        return min(1.0, variance * 2)

    # ------------------------------------------------------------------ #
    # Query Methods
    # ------------------------------------------------------------------ #

    def get_current_state(self) -> Optional[FieldState]:
        return self._current_state

    def get_state_history(self, limit: int = 100) -> List[FieldState]:
        return self._state_history[-limit:]

    def get_coherence_trend(self) -> str:
        """Restituisce il trend di coerenza: 'improving', 'declining', 'stable'."""
        if len(self._coherence_history) < 5:
            return "stable"

        recent = self._coherence_history[-5:]
        if all(recent[i] <= recent[i+1] for i in range(len(recent)-1)):
            return "improving"
        elif all(recent[i] >= recent[i+1] for i in range(len(recent)-1)):
            return "declining"
        return "stable"

    def get_systemic_coherence_index(self) -> float:
        """Systemic Coherence Index.

        Misura quanto le decisioni di parti diverse dell'organismo
        convergono spontaneamente senza coordinazione esplicita.
        """
        if not self._state_history:
            return 0.0

        recent = self._state_history[-10:]

        # Coerenza del campo
        field_coherence = sum(s.coherence for s in recent) / len(recent)

        # Coerenza dei gradienti (quanto sono allineati)
        gradient_variance = 0.0
        for s in recent:
            g_sum = abs(s.coherence_gradient) + abs(s.adaptation_gradient) + abs(s.continuity_gradient)
            gradient_variance += g_sum / 3
        gradient_coherence = 1.0 - min(1.0, gradient_variance / len(recent))

        # Stabilità
        stability = sum(s.field_stability for s in recent) / len(recent)

        # Combina
        sci = (field_coherence * 0.4 + gradient_coherence * 0.3 + stability * 0.3)
        return min(1.0, max(0.0, sci))

    def get_subsystem_influence(self, subsystem: str) -> Dict[str, float]:
        """Restituisce l'influenza di un sottosistema sul campo."""
        if subsystem not in self._subsystems:
            return {}

        iface = self._subsystems[subsystem]

        # Calcola quanto il sottosistema contribuisce al campo
        contributions = []
        for state in self._state_history[-10:]:
            sub_state = state.subsystem_states.get(subsystem, 0.5)
            contributions.append(sub_state)

        if not contributions:
            return {"influence": 0.0, "alignment": 0.0}

        avg_sub = sum(contributions) / len(contributions)
        avg_coherence = sum(s.coherence for s in self._state_history[-10:]) / 10

        return {
            "influence": avg_sub * iface.weight,
            "alignment": 1.0 - abs(avg_sub - avg_coherence),
            "weight": iface.weight,
        }

    # ------------------------------------------------------------------ #
    # Callbacks
    # ------------------------------------------------------------------ #

    def on_state_change(self, callback: Callable[[FieldState], None]) -> None:
        self._on_state_change.append(callback)

    def on_coherence_change(self, callback: Callable[[float, float], None]) -> None:
        self._on_coherence_change.append(callback)

    # ------------------------------------------------------------------ #
    # Serialization
    # ------------------------------------------------------------------ #

    def export_state(self) -> str:
        if not self._current_state:
            return "{}"
        return json.dumps(self._current_state.to_dict(), indent=2)

    def get_field_hash(self) -> str:
        """Hash unico dello stato corrente del campo."""
        if not self._current_state:
            return "no_state"
        state_str = json.dumps(self._current_state.to_dict(), sort_keys=True)
        return hashlib.sha256(state_str.encode()).hexdigest()[:16]