"""
Global Field Integrator for SPEACE

Integra il campo informazionale (ILF) nell'architettura reale di SPEACE.
Questo permette a ogni sottosistema di:
1. Ricevere FieldState dal campo globale
2. Inviare le proprie metriche al campo
3. Adattare il proprio comportamento in base al campo

Il campo diventa l'organizzatore centrale dell'organismo.
"""

from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
import time

from speace_core.ilf import (
    InformationalField,
    FieldState,
    ILFEngine,
    ILFMetrics,
    SubsystemFieldConnector,
    FieldBroadcastScheduler,
)


@dataclass
class SubsystemInterface:
    """Interfaccia standardizzata per un sottosistema SPEACE."""

    name: str
    # Funzione che restituisce le metriche ILF del sottosistema
    get_metrics_fn: Callable[[], ILFMetrics]
    # Funzione chiamata quando il campo invia un update
    on_field_update_fn: Optional[Callable[[FieldState], None]] = None
    # Funzione per riconfigurare il sottosistema basata sul campo
    reconfigure_fn: Optional[Callable[[FieldState], None]] = None
    # Peso del sottosistema nel campo (default 1.0)
    weight: float = 1.0
    # Stato interno
    _connector: Optional[SubsystemFieldConnector] = None
    _last_reconfiguration_time: float = 0.0
    _reconfiguration_count: int = 0


class GlobalFieldIntegrator:
    """Integratore del campo informazionale globale in SPEACE.

    Si collega all'orchestrator e ai sottosistemi esistenti,
    aggiungendo la funzionalità del campo senza modificarli.

    Usage:
        integrator = GlobalFieldIntegrator()
        integrator.register_subsystem('brain', brain_get_metrics, brain_on_field_update)
        integrator.register_subsystem('memory', memory_get_metrics, memory_on_field_update)

        # Nel tick loop dell'orchestrator:
        integrator.tick()
    """

    def __init__(
        self,
        ilf_config: Optional[Dict[str, Any]] = None,
        broadcast_interval: float = 0.0,  # 0 = ogni ciclo
    ):
        # Campo informazionale
        self.field = InformationalField(ilf_engine=ILFEngine(ilf_config))
        self._broadcast_interval = broadcast_interval
        self._scheduler = FieldBroadcastScheduler(self.field)
        self._scheduler.set_cycle_interval(broadcast_interval)

        # Sottosistemi registrati
        self._subsystems: Dict[str, SubsystemInterface] = {}

        # Stato
        self._cycle: int = 0
        self._enabled: bool = True
        self._field_effects_enabled: bool = True

        # Callbacks per eventi
        self._on_coherence_change: List[Callable[[float, float], None]] = []
        self._on_stagnation_detected: List[Callable[[], None]] = []
        self._on_intervention_needed: List[Callable[[FieldState], None]] = []

        # Buffer messaggi endocrini (needs/goals/alarms/intentions)
        self._pending_messages: Dict[str, Any] = {}

        # Storia per analisi
        self._reconfiguration_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------ #
    # Registration
    # ------------------------------------------------------------------ #

    def register_subsystem(
        self,
        name: str,
        get_metrics_fn: Callable[[], ILFMetrics],
        on_field_update_fn: Optional[Callable[[FieldState], None]] = None,
        reconfigure_fn: Optional[Callable[[FieldState], None]] = None,
        weight: float = 1.0,
    ) -> None:
        """Registra un sottosistema al campo.

        Args:
            name: Nome univoco del sottosistema (es: 'brain', 'memory', 'dna')
            get_metrics_fn: Funzione che restituisce ILFMetrics del sottosistema
            on_field_update_fn: Callback chiamata quando il campo invia update
            reconfigure_fn: Funzione per riconfigurare il sottosistema
            weight: Peso del sottosistema nel calcolo del campo
        """
        interface = SubsystemInterface(
            name=name,
            get_metrics_fn=get_metrics_fn,
            on_field_update_fn=on_field_update_fn,
            reconfigure_fn=reconfigure_fn,
            weight=weight,
        )

        # Crea connector
        connector = SubsystemFieldConnector(
            subsystem_name=name,
            field=self.field,
            on_receive_state=self._create_update_callback(name),
            on_send_metrics=get_metrics_fn,
        )

        interface._connector = connector
        self._subsystems[name] = interface

        # Registra metriche nello scheduler
        self._scheduler.register_subsystem_metrics(name, get_metrics_fn)

    def _create_update_callback(self, name: str) -> Callable[[FieldState], None]:
        """Crea la callback per gli aggiornamenti del campo."""
        def callback(state: FieldState):
            interface = self._subsystems.get(name)
            if not interface:
                return

            # Chiama on_field_update se definita
            if interface.on_field_update_fn:
                interface.on_field_update_fn(state)

            # Se reconfigure è attivo e definito, applica la riconfigurazione
            if self._field_effects_enabled and interface.reconfigure_fn:
                interface.reconfigure_fn(state)
                interface._reconfiguration_count += 1
                interface._last_reconfiguration_time = time.time()

                # Log della riconfigurazione
                self._reconfiguration_log.append({
                    'timestamp': time.time(),
                    'cycle': self._cycle,
                    'subsystem': name,
                    'ilf_value': state.ilf_value,
                    'coherence': state.coherence,
                    'field_noise': state.field_noise,
                })

                # Limita la storia del log
                if len(self._reconfiguration_log) > 1000:
                    self._reconfiguration_log = self._reconfiguration_log[-500:]

        return callback

    def unregister_subsystem(self, name: str) -> bool:
        """Rimuove un sottosistema."""
        if name in self._subsystems:
            del self._subsystems[name]
            return True
        return False

    # ------------------------------------------------------------------ #
    # Endocrine Messaging — inject needs/goals/alarms/intentions into field
    # ------------------------------------------------------------------ #

    def inject_messages(
        self,
        *,
        needs: Optional[Dict[str, float]] = None,
        goals: Optional[Dict[str, float]] = None,
        alarms: Optional[List[str]] = None,
        intentions: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Bufferizza messaggi endocrini per il prossimo broadcast del campo.

        I messaggi vengono inclusi nel prossimo FieldState e propagati a tutti
        i sottosistemi. Dopo il broadcast il buffer viene azzerato.
        """
        msg: Dict[str, Any] = {}
        if needs is not None:
            msg["needs"] = needs
        if goals is not None:
            msg["goals"] = goals
        if alarms is not None:
            msg["alarms"] = alarms
        if intentions is not None:
            msg["intentions"] = intentions
        if msg:
            self._pending_messages.update(msg)

    # ------------------------------------------------------------------ #
    # Core Loop
    # ------------------------------------------------------------------ #

    def tick(self, force_broadcast: bool = False) -> Optional[FieldState]:
        """Esegue un ciclo del campo.

        Da chiamare nel tick loop principale dell'orchestrator.

        Args:
            force_broadcast: Se True, forza il broadcast anche se in cooldown

        Returns:
            FieldState se è stato fatto broadcast, None altrimenti
        """
        if not self._enabled:
            return None

        self._cycle += 1

        # Includi messaggi endocrini pendenti, poi azzera
        messages = dict(self._pending_messages)
        self._pending_messages.clear()

        # Broadcast del campo con messaggi
        state = self._scheduler.tick(self._cycle, field_messages=messages)

        if state:
            # Verifica se serve intervento
            if state.needs_intervention():
                for callback in self._on_intervention_needed:
                    callback(state)

            # Verifica stagnazione
            if len(self.field._coherence_history) >= 5:
                trend = self.field.get_coherence_trend()
                if trend == 'stable':
                    for callback in self._on_stagnation_detected:
                        callback()

        return state

    def enable(self) -> None:
        """Abilita il campo."""
        self._enabled = True

    def disable(self) -> None:
        """Disabilita il campo (i sottosistemi non ricevono più update)."""
        self._enabled = False

    def enable_field_effects(self) -> None:
        """Abilita gli effetti del campo sui sottosistemi (riconfigurazione)."""
        self._field_effects_enabled = True

    def disable_field_effects(self) -> None:
        """Disabilita gli effetti del campo (solo osservazione, no causalità)."""
        self._field_effects_enabled = False

    # ------------------------------------------------------------------ #
    # Callbacks
    # ------------------------------------------------------------------ #

    def on_coherence_change(
        self, callback: Callable[[float, float], None]
    ) -> None:
        """Registra callback per cambi di coerenza."""
        self._on_coherence_change.append(callback)

    def on_stagnation_detected(self, callback: Callable[[], None]) -> None:
        """Registra callback per rilevamento stagnazione."""
        self._on_stagnation_detected.append(callback)

    def on_intervention_needed(self, callback: Callable[[FieldState], None]) -> None:
        """Registra callback per intervento necessario."""
        self._on_intervention_needed.append(callback)

    # ------------------------------------------------------------------ #
    # Query
    # ------------------------------------------------------------------ #

    def get_current_state(self) -> Optional[FieldState]:
        """Restituisce lo stato corrente del campo."""
        return self.field.get_current_state()

    def get_systemic_coherence_index(self) -> float:
        """Restituisce l'SCI corrente."""
        return self.field.get_systemic_coherence_index()

    def get_coherence_trend(self) -> str:
        """Restituisce il trend di coerenza."""
        return self.field.get_coherence_trend()

    def get_subsystem_reconfiguration_count(self, name: str) -> int:
        """Numero di riconfigurazioni effettuate da un sottosistema."""
        if name in self._subsystems:
            return self._subsystems[name]._reconfiguration_count
        return 0

    def get_reconfiguration_log(
        self, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Storia delle riconfigurazioni."""
        return self._reconfiguration_log[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        """Statistiche complete del sistema."""
        state = self.get_current_state()
        sci = self.get_systemic_coherence_index()

        subs_stats = {}
        for name, interface in self._subsystems.items():
            subs_stats[name] = {
                'weight': interface.weight,
                'reconfiguration_count': interface._reconfiguration_count,
                'last_reconfiguration': interface._last_reconfiguration_time,
            }

        return {
            'cycle': self._cycle,
            'enabled': self._enabled,
            'field_effects_enabled': self._field_effects_enabled,
            'subsystem_count': len(self._subsystems),
            'current_state': state.to_dict() if state else None,
            'systemic_coherence_index': sci,
            'coherence_trend': self.field.get_coherence_trend(),
            'field_hash': self.field.get_field_hash(),
            'subsystems': subs_stats,
            'total_reconfigurations': sum(
                s._reconfiguration_count for s in self._subsystems.values()
            ),
        }


class FieldAwareMixin:
    """Mixin che aggiunge la funzionalità del campo a un orchestrator.

    Usage:
        class MyOrchestrator(FieldAwareMixin, BaseOrchestrator):
            def __init__(self, ...):
                super().__init__(...)
                self.init_field_integrator()
    """

    _field_integrator: Optional[GlobalFieldIntegrator] = None

    def init_field_integrator(
        self,
        ilf_config: Optional[Dict[str, Any]] = None,
        broadcast_interval: float = 0.0,
    ) -> None:
        """Inizializza l'integratore del campo."""
        self._field_integrator = GlobalFieldIntegrator(
            ilf_config=ilf_config,
            broadcast_interval=broadcast_interval,
        )

    def register_subsystem_to_field(
        self,
        name: str,
        get_metrics_fn: Callable[[], ILFMetrics],
        on_field_update_fn: Optional[Callable[[FieldState], None]] = None,
        reconfigure_fn: Optional[Callable[[FieldState], None]] = None,
        weight: float = 1.0,
    ) -> None:
        """Registra un sottosistema al campo."""
        if self._field_integrator:
            self._field_integrator.register_subsystem(
                name=name,
                get_metrics_fn=get_metrics_fn,
                on_field_update_fn=on_field_update_fn,
                reconfigure_fn=reconfigure_fn,
                weight=weight,
            )

    def field_tick(self, force_broadcast: bool = False) -> Optional[FieldState]:
        """Esegue un tick del campo. Chiamare nel tick loop."""
        if self._field_integrator:
            return self._field_integrator.tick(force_broadcast)
        return None

    def get_field_state(self) -> Optional[FieldState]:
        """Stato corrente del campo."""
        if self._field_integrator:
            return self._field_integrator.get_current_state()
        return None

    def get_systemic_coherence_index(self) -> float:
        """SCI corrente."""
        if self._field_integrator:
            return self._field_integrator.get_systemic_coherence_index()
        return 0.0

    def enable_field_effects(self) -> None:
        """Abilita effetti del campo."""
        if self._field_integrator:
            self._field_integrator.enable_field_effects()

    def disable_field_effects(self) -> None:
        """Disabilita effetti del campo."""
        if self._field_integrator:
            self._field_integrator.disable_field_effects()

    def inject_field_messages(
        self,
        *,
        needs: Optional[Dict[str, float]] = None,
        goals: Optional[Dict[str, float]] = None,
        alarms: Optional[List[str]] = None,
        intentions: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Inietta messaggi endocrini nel campo (needs/goals/alarms/intentions)."""
        if self._field_integrator:
            self._field_integrator.inject_messages(
                needs=needs, goals=goals, alarms=alarms, intentions=intentions,
            )

    def get_field_statistics(self) -> Dict[str, Any]:
        """Statistiche del campo."""
        if self._field_integrator:
            return self._field_integrator.get_statistics()
        return {}


# ------------------------------------------------------------------ #
# Utility: Crea adapter per componenti esistenti
# ------------------------------------------------------------------ #

class MetricsAdapter:
    """Adapter che converte metriche esistenti in ILFMetrics."""

    @staticmethod
    def from_neuron_circuit(circuit) -> ILFMetrics:
        """Crea ILFMetrics da un NeuralCircuit."""
        # Estrai outputs delle regioni
        region_outputs = {}
        if hasattr(circuit, 'hidden_neurons'):
            for i, neuron in enumerate(circuit.hidden_neurons[:5]):  # Limita a 5
                region_outputs[f'region_{i}'] = getattr(neuron, 'activation', 0.5)

        # Cell states
        cell_states = {}
        cell_types = {}
        if hasattr(circuit, 'hidden_neurons'):
            for neuron in circuit.hidden_neurons[:10]:
                cid = getattr(neuron, 'cell_id', str(id(neuron)))
                cell_states[cid] = getattr(neuron, 'activation', 0.5)
                cell_types[cid] = getattr(neuron, 'cell_type', 'unknown')

        return ILFMetrics(
            region_outputs=region_outputs,
            cell_states=cell_states,
            cell_types=cell_types,
            energy_levels={},
            memory_utilization=0.5,
            memory_retention=0.7,
            learning_rate=0.1,
            error_rate=0.1,
            goal_activations={},
            ilf_history=[],
        )

    @staticmethod
    def from_system_metrics(metrics) -> ILFMetrics:
        """Crea ILFMetrics da SystemMetrics."""
        region_outputs = {}
        if hasattr(metrics, 'region_energies'):
            for region, energy in getattr(metrics, 'region_energies', {}).items():
                region_outputs[region] = energy

        return ILFMetrics(
            region_outputs=region_outputs,
            cell_states={},
            cell_types={},
            energy_levels=getattr(metrics, 'region_energies', {}),
            memory_utilization=getattr(metrics, 'memory_utilization', 0.5),
            memory_retention=getattr(metrics, 'memory_retention', 0.7),
            learning_rate=getattr(metrics, 'learning_rate', 0.1),
            error_rate=getattr(metrics, 'error_rate', 0.1),
            goal_activations={},
            ilf_history=[],
        )


def create_field_aware_orchestrator_adapter(
    orchestrator,
    subsystem_configs: Dict[str, Dict[str, Any]],
) -> GlobalFieldIntegrator:
    """Crea un adapter che connette un orchestrator esistente al campo.

    Args:
        orchestrator: L'orchestrator esistente
        subsystem_configs: Dict di {name: {
            'get_metrics': callable,
            'on_update': callable,
            'reconfigure': callable,
            'weight': float
        }}

    Returns:
        GlobalFieldIntegrator configurato
    """
    integrator = GlobalFieldIntegrator()

    for name, config in subsystem_configs.items():
        integrator.register_subsystem(
            name=name,
            get_metrics_fn=config.get('get_metrics', lambda: ILFMetrics()),
            on_field_update_fn=config.get('on_update'),
            reconfigure_fn=config.get('reconfigure'),
            weight=config.get('weight', 1.0),
        )

    return integrator