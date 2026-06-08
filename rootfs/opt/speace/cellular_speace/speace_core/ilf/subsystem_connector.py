from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
import time

from speace_core.ilf.informational_field import InformationalField, FieldState
from speace_core.ilf.ilf_engine import ILFMetrics


@dataclass
class SubsystemFieldConnector:
    """Connector che lega un sottosistema al campo ILF.

    Ogni sottosistema (brain, memory, dna, agents) usa questo
    connector per:
    1. Ricevere FieldState dal campo
    2. Inviare le proprie metriche al campo
    3. Adattare il proprio comportamento in base al campo
    """

    subsystem_name: str
    field: InformationalField

    # Callbacks per adattamento
    _on_receive_state: Optional[Callable[[FieldState], None]] = None
    _on_send_metrics: Optional[Callable[[], ILFMetrics]] = None

    # Stato locale del sottosistema
    _last_state: Optional[FieldState] = None
    _adaptation_count: int = 0
    _last_adaptation_time: float = 0.0

    def __init__(
        self,
        subsystem_name: str,
        field: InformationalField,
        on_receive_state: Optional[Callable[[FieldState], None]] = None,
        on_send_metrics: Optional[Callable[[], ILFMetrics]] = None,
    ):
        self.subsystem_name = subsystem_name
        self.field = field
        self._on_receive_state = on_receive_state
        self._on_send_metrics = on_send_metrics

        # Stato locale del sottosistema
        self._last_state: Optional[FieldState] = None
        self._adaptation_count: int = 0
        self._last_adaptation_time: float = 0.0

        # Registra questo sottosistema al campo per OSSERVARE (fornire metriche)
        self.field.register_subsystem(
            name=subsystem_name,
            update_fn=self._update_wrapper,
            weight=1.0,
        )

        # Registra per RICEVERE broadcast del campo
        if on_receive_state:
            self.field.on_state_change(self._on_broadcast_received)

    def _on_broadcast_received(self, state: FieldState) -> None:
        """Callback chiamata quando il campo broadcast il suo stato."""
        self._last_state = state
        self._adaptation_count += 1
        self._last_adaptation_time = time.time()

        if self._on_receive_state:
            self._on_receive_state(state)

    def _update_wrapper(
        self,
        field: InformationalField,
        current_state: Optional[FieldState],
    ) -> Dict[str, Any]:
        """Wrapper che il campo chiama per ottenere dati dal sottosistema.

        Il campo chiama questo per OSSERVARE (raccogliere metriche).
        Il broadcast viene poi fatto separatamente via on_state_change.
        """
        # Invia le metriche del sottosistema
        if self._on_send_metrics:
            metrics = self._on_send_metrics()
            return self._metrics_to_dict(metrics)

        return {"subsystem": self.subsystem_name, "no_metrics": True}

    def _metrics_to_dict(self, metrics: ILFMetrics) -> Dict[str, Any]:
        return {
            "subsystem": self.subsystem_name,
            "memory_utilization": metrics.memory_utilization,
            "memory_retention": metrics.memory_retention,
            "learning_rate": metrics.learning_rate,
            "error_rate": metrics.error_rate,
            "region_outputs": metrics.region_outputs,
            "goal_activations": metrics.goal_activations,
            "timestamp": time.time(),
        }

    def receive_update(self, state: FieldState) -> None:
        """Riceve un update del campo.

        Il sottosistema dovrebbe chiamare questo metodo
        quando riceve broadcast dal campo.
        """
        self._last_state = state
        self._adaptation_count += 1
        self._last_adaptation_time = time.time()

        if self._on_receive_state:
            self._on_receive_state(state)

    def send_metrics(self, metrics: ILFMetrics) -> None:
        """Invia le metriche al campo.

        Il sottosistema chiama questo per aggiornare
        lo stato del campo con i propri dati locali.
        """
        # Il campo aggregherà automaticamente
        pass

    def get_local_state(self) -> Optional[FieldState]:
        """Restituisce l'ultimo FieldState ricevuto."""
        return self._last_state

    def should_adapt(self) -> bool:
        """Determina se il sottosistema dovrebbe adattarsi.

        Basato su:
        - Campo richiede intervento
        - Coerenza bassa
        - Alto rumore
        """
        if not self._last_state:
            return False

        return self._last_state.needs_intervention() or not self._last_state.is_coherent()

    def get_adaptation_signal(self) -> Dict[str, Any]:
        """Restituisce il segnale di adattamento per questo sottosistema.

        Il sottosistema usa questo per capire come modificare
        il proprio comportamento.
        """
        if not self._last_state:
            return {"action": "wait", "reason": "no_field_state"}

        state = self._last_state

        # Calcola azione basata sul campo
        if state.ilf_value < 0.35:
            action = "recover"
            reason = "critical_ilf"
        elif state.field_noise > 0.3:
            action = "synchronize"
            reason = "high_noise"
        elif state.coherence_gradient < -0.1:
            action = "stabilize"
            reason = "coherence_declining"
        elif state.adaptation_gradient < -0.1:
            action = "adapt"
            reason = "adaptation_declining"
        else:
            action = "continue"
            reason = "field_stable"

        return {
            "action": action,
            "reason": reason,
            "ilf_value": state.ilf_value,
            "coherence": state.coherence,
            "field_noise": state.field_noise,
            "gradient": state.get_gradient(self.subsystem_name),
        }

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "subsystem": self.subsystem_name,
            "adaptation_count": self._adaptation_count,
            "last_adaptation_time": self._last_adaptation_time,
            "has_local_state": self._last_state is not None,
            "field_connected": True,
        }


class FieldBroadcastScheduler:
    """Scheduler che gestisce il timing del broadcast del campo.

    Assicura che tutti i sottosistemi siano sincronizzati.
    """

    def __init__(self, field: InformationalField):
        self.field = field
        self._cycle_interval: float = 0.0  # 0 = every cycle
        self._last_broadcast: float = 0.0
        self._last_broadcast_cycle: int = -1
        self._subsystem_metrics: Dict[str, Callable[[], ILFMetrics]] = {}

    def register_subsystem_metrics(
        self,
        subsystem: str,
        get_metrics_fn: Callable[[], ILFMetrics],
    ) -> None:
        """Registra una funzione che fornisce metriche per un sottosistema."""
        self._subsystem_metrics[subsystem] = get_metrics_fn

    def tick(self, current_cycle: int = 0, field_messages: Optional[Dict[str, Any]] = None) -> Optional[FieldState]:
        """Esegue un tick del campo.

        Args:
            current_cycle: Ciclo corrente del sistema
            field_messages: Messaggi endocrini opzionali (needs/goals/alarms/intentions)

        Returns:
            FieldState broadcast, o None se in cooldown.
        """
        # Always broadcast if cycle changed (for simulation mode with _cycle_interval=0)
        # or if enough time has passed (for real-time mode)
        if self._cycle_interval == 0:
            if current_cycle == self._last_broadcast_cycle:
                return None  # Already broadcast this cycle
        else:
            current_time = time.time()
            if current_time - self._last_broadcast < self._cycle_interval:
                return None

        # Raccoglie metriche da tutti i sottosistemi
        all_metrics = {}
        for name, get_fn in self._subsystem_metrics.items():
            try:
                all_metrics[name] = get_fn()
            except Exception:
                pass

        if not all_metrics:
            return None

        # Update del campo con messaggi endocrini
        state = self.field.update(all_metrics, field_messages=field_messages)
        self._last_broadcast = time.time()
        self._last_broadcast_cycle = current_cycle

        return state

    def set_cycle_interval(self, seconds: float) -> None:
        self._cycle_interval = seconds

    def force_broadcast(self, metrics: Dict[str, ILFMetrics], field_messages: Optional[Dict[str, Any]] = None) -> FieldState:
        """Forza un broadcast immediato."""
        self._last_broadcast = 0
        return self.field.update(metrics, field_messages=field_messages)


def create_brain_connector(
    field: InformationalField,
    brain_instance: Any,
) -> SubsystemFieldConnector:
    """Factory per creare un connector per il brain.

    Il brain deve implementare:
    - get_local_metrics() -> ILFMetrics
    - receive_field_state(FieldState)
    """

    def on_receive(state: FieldState):
        # Brain aggiorna il proprio comportamento
        if hasattr(brain_instance, 'update_from_field'):
            brain_instance.update_from_field(state)

    def on_send() -> ILFMetrics:
        if hasattr(brain_instance, 'get_ilf_metrics'):
            return brain_instance.get_ilf_metrics()
        return ILFMetrics()

    return SubsystemFieldConnector(
        subsystem_name="brain",
        field=field,
        on_receive_state=on_receive,
        on_send_metrics=on_send,
    )


def create_memory_connector(
    field: InformationalField,
    memory_instance: Any,
) -> SubsystemFieldConnector:
    """Factory per creare un connector per la memoria."""

    def on_receive(state: FieldState):
        if hasattr(memory_instance, 'update_from_field'):
            memory_instance.update_from_field(state)

    def on_send() -> ILFMetrics:
        if hasattr(memory_instance, 'get_ilf_metrics'):
            return memory_instance.get_ilf_metrics()
        return ILFMetrics()

    return SubsystemFieldConnector(
        subsystem_name="memory",
        field=field,
        on_receive_state=on_receive,
        on_send_metrics=on_send,
    )


def create_dna_connector(
    field: InformationalField,
    dna_instance: Any,
) -> SubsystemFieldConnector:
    """Factory per creare un connector per il DNA."""

    def on_receive(state: FieldState):
        if hasattr(dna_instance, 'update_from_field'):
            dna_instance.update_from_field(state)

    def on_send() -> ILFMetrics:
        if hasattr(dna_instance, 'get_ilf_metrics'):
            return dna_instance.get_ilf_metrics()
        return ILFMetrics()

    return SubsystemFieldConnector(
        subsystem_name="dna",
        field=field,
        on_receive_state=on_receive,
        on_send_metrics=on_send,
    )


def create_agents_connector(
    field: InformationalField,
    agents_instance: Any,
) -> SubsystemFieldConnector:
    """Factory per creare un connector per gli agenti."""

    def on_receive(state: FieldState):
        if hasattr(agents_instance, 'update_from_field'):
            agents_instance.update_from_field(state)

    def on_send() -> ILFMetrics:
        if hasattr(agents_instance, 'get_ilf_metrics'):
            return agents_instance.get_ilf_metrics()
        return ILFMetrics()

    return SubsystemFieldConnector(
        subsystem_name="agents",
        field=field,
        on_receive_state=on_receive,
        on_send_metrics=on_send,
    )