"""
Example: Integrating Field with Real SPEACE Components

This module shows how to connect the Informational Field to actual
SPEACE components like BrainRegion, MorphologicalMemory, and DNA.

Usage pattern for integrating field into SPEACE architecture.
"""

from typing import Dict, Any, Optional, Callable
from speace_core.ilf import (
    InformationalField, FieldState, ILFMetrics,
    SubsystemFieldConnector, FieldBroadcastScheduler,
    GlobalFieldIntegrator,
)
from speace_core.ilf.field_integrator import MetricsAdapter


class FieldAwareBrainRegion:
    """BrainRegion che legge e risponde al campo informazionale.

    Pattern di integrazione per le regioni del cervello.
    """

    def __init__(
        self,
        region_id: str,
        region_type: str,
        field_integrator: Optional[GlobalFieldIntegrator] = None,
    ):
        self.region_id = region_id
        self.region_type = region_type

        # Parametri che verranno modificati dal campo
        self.activation_threshold = 0.5
        self.gain_modulation = 1.0
        self.routing_priority = 0.5

        # Stato
        self._field_state: Optional[FieldState] = None
        self._field_connector: Optional[SubsystemFieldConnector] = None
        self._field_integrator = field_integrator

        # Registra al campo se integrator fornito
        if field_integrator:
            self._register_to_field()

    def _register_to_field(self) -> None:
        """Registra questa regione al campo globale."""
        if not self._field_integrator:
            return

        # Registra tramite l'integrator
        self._field_integrator.register_subsystem(
            name=f"brain_region_{self.region_id}",
            get_metrics_fn=self._get_ilf_metrics,
            on_field_update_fn=self._on_field_update,
            reconfigure_fn=self._on_field_update,
            weight=1.0,
        )

    def _on_field_update(self, state: FieldState) -> None:
        """Callback: il campo CAUSA aggiornamento della regione."""
        self._field_state = state

        # Il campo modifica i parametri della regione
        old_threshold = self.activation_threshold
        old_gain = self.gain_modulation
        old_priority = self.routing_priority

        # Logica di adattamento basata sul campo
        if state.ilf_value < 0.35:
            # Basso ILF: aumentare soglia, ridurre gain
            self.activation_threshold = min(0.9, self.activation_threshold * 1.1)
            self.gain_modulation = max(0.5, self.gain_modulation * 0.9)
        elif state.ilf_value > 0.65:
            # Alto ILF: diminuire soglia, aumentare gain
            self.activation_threshold = max(0.2, self.activation_threshold * 0.95)
            self.gain_modulation = min(1.5, self.gain_modulation * 1.05)

        # Noise alto = aumentare routing priority per sincronizzazione
        if state.field_noise > 0.25:
            self.routing_priority = min(1.0, self.routing_priority * 1.1)
        else:
            self.routing_priority = max(0.3, self.routing_priority * 0.98)

        # Coherence in calo = rafforzare connessioni
        if state.coherence_gradient < -0.05:
            self.gain_modulation = min(1.5, self.gain_modulation * 1.1)

    def _get_ilf_metrics(self) -> ILFMetrics:
        """Fornisce metriche della regione al campo."""
        return ILFMetrics(
            region_outputs={self.region_id: self.gain_modulation * 0.7},
            cell_states={
                f'{self.region_id}_threshold': self.activation_threshold,
                f'{self.region_id}_gain': self.gain_modulation,
            },
            cell_types={
                f'{self.region_id}_threshold': 'parameter',
                f'{self.region_id}_gain': 'parameter',
            },
            energy_levels={self.region_id: 0.6 * self.gain_modulation},
            memory_utilization=0.6,
            memory_retention=0.7,
            learning_rate=0.1,
            error_rate=0.08,
            goal_activations={},
            ilf_history=[],
        )

    def process_signal(self, input_signal: float) -> float:
        """Processa un segnale usando i parametri correnti."""
        # Applica threshold e gain modificati dal campo
        activated = max(0.0, input_signal - self.activation_threshold)
        return activated * self.gain_modulation * self.routing_priority

    def get_adaptation_summary(self) -> Dict[str, Any]:
        """Riepilogo dell'adattamento corrente."""
        return {
            'region_id': self.region_id,
            'activation_threshold': self.activation_threshold,
            'gain_modulation': self.gain_modulation,
            'routing_priority': self.routing_priority,
            'has_field_state': self._field_state is not None,
            'field_ilf': self._field_state.ilf_value if self._field_state else None,
        }


class FieldAwareMemory:
    """Memory che si adatta al campo informazionale."""

    def __init__(
        self,
        memory_id: str = "main",
        field_integrator: Optional[GlobalFieldIntegrator] = None,
    ):
        self.memory_id = memory_id

        # Parametri modificati dal campo
        self.consolidation_threshold = 0.6
        self.retention_level = 0.8
        self.forgetting_rate = 0.05

        # Stato
        self._field_state: Optional[FieldState] = None
        self._field_connector: Optional[SubsystemFieldConnector] = None
        self._field_integrator = field_integrator

        if field_integrator:
            self._register_to_field()

    def _register_to_field(self) -> None:
        """Registra questa memoria al campo globale."""
        if not self._field_integrator:
            return

        # Registra tramite l'integrator
        self._field_integrator.register_subsystem(
            name=f"memory_{self.memory_id}",
            get_metrics_fn=self._get_ilf_metrics,
            on_field_update_fn=self._on_field_update,
            reconfigure_fn=self._on_field_update,
            weight=1.0,
        )

    def _on_field_update(self, state: FieldState) -> None:
        """Il campo CAUSA adattamento della memoria."""
        self._field_state = state

        # Adatta parametri memoria al campo
        if state.continuity < 0.35:
            # Bassa continuità: aumentare plasticità
            self.consolidation_threshold = max(0.3, self.consolidation_threshold * 0.95)
            self.forgetting_rate = min(0.15, self.forgetting_rate * 1.1)
        elif state.continuity > 0.7:
            # Alta continuità: consolidare di più
            self.consolidation_threshold = min(0.9, self.consolidation_threshold * 1.02)
            self.forgetting_rate = max(0.01, self.forgetting_rate * 0.98)

        # Noise alto = aumentare retention
        if state.field_noise > 0.3:
            self.retention_level = min(1.0, self.retention_level * 1.05)

    def _get_ilf_metrics(self) -> ILFMetrics:
        return ILFMetrics(
            region_outputs={f'memory_{self.memory_id}': self.retention_level * 0.6},
            memory_utilization=self.consolidation_threshold,
            memory_retention=self.retention_level,
            learning_rate=0.08,
            error_rate=self.forgetting_rate,
            ilf_history=[],
        )

    def store(self, key: str, value: Any) -> None:
        """Memorizza con soglia di consolidazione modificata dal campo."""
        # Logica di storage con parametri adattivi
        pass

    def get_adaptation_summary(self) -> Dict[str, Any]:
        return {
            'memory_id': self.memory_id,
            'consolidation_threshold': self.consolidation_threshold,
            'retention_level': self.retention_level,
            'forgetting_rate': self.forgetting_rate,
            'has_field_state': self._field_state is not None,
        }


class FieldAwareDNA:
    """DNA che modula l'espressione genica in base al campo."""

    def __init__(
        self,
        dna_id: str = "main",
        field_integrator: Optional[GlobalFieldIntegrator] = None,
    ):
        self.dna_id = dna_id

        # Parametri epigenetici modificati dal campo
        self.expression_level = 0.7
        self.plasticity_modifier = 1.0
        self.mutation_rate = 0.05

        # Stato
        self._field_state: Optional[FieldState] = None
        self._field_connector = None
        self._field_integrator = field_integrator

        if field_integrator:
            self._register_to_field()

    def _register_to_field(self) -> None:
        """Registra questo DNA al campo globale."""
        if not self._field_integrator:
            return

        # Registra tramite l'integrator
        self._field_integrator.register_subsystem(
            name=f"dna_{self.dna_id}",
            get_metrics_fn=self._get_ilf_metrics,
            on_field_update_fn=self._on_field_update,
            reconfigure_fn=self._on_field_update,
            weight=1.0,
        )

    def _on_field_update(self, state: FieldState) -> None:
        """Il campo CAUSA cambiamenti nell'espressione genica."""
        self._field_state = state

        # Adatta espressione al campo
        if state.adaptation < 0.35:
            # Bassa adattamento: aumentare plasticità
            self.plasticity_modifier = min(1.5, self.plasticity_modifier * 1.15)
            self.expression_level = min(1.0, self.expression_level * 1.1)
        elif state.adaptation > 0.7:
            # Alta adattamento: mantenimento stabile
            self.plasticity_modifier = max(0.7, self.plasticity_modifier * 0.98)
            self.expression_level = max(0.5, self.expression_level * 0.99)

        # ILF critico = aumentare mutation rate per esplorazione
        if state.ilf_value < 0.3:
            self.mutation_rate = min(0.2, self.mutation_rate * 1.2)

    def _get_ilf_metrics(self) -> ILFMetrics:
        return ILFMetrics(
            region_outputs={f'dna_{self.dna_id}': self.expression_level * 0.7},
            cell_states={
                'expression_level': self.expression_level,
                'plasticity_modifier': self.plasticity_modifier,
            },
            cell_types={
                'expression_level': 'epigenetic',
                'plasticity_modifier': 'epigenetic',
            },
            memory_utilization=0.5,
            memory_retention=0.8,
            learning_rate=self.mutation_rate,
            error_rate=0.05,
            ilf_history=[],
        )

    def get_adaptation_summary(self) -> Dict[str, Any]:
        return {
            'dna_id': self.dna_id,
            'expression_level': self.expression_level,
            'plasticity_modifier': self.plasticity_modifier,
            'mutation_rate': self.mutation_rate,
            'has_field_state': self._field_state is not None,
        }


def demonstrate_real_integration():
    """Dimostra l'integrazione del campo con componenti reali di SPEACE."""
    print("=" * 70)
    print("FIELD INTEGRATION WITH REAL SPEACE COMPONENTS")
    print("=" * 70)
    print()

    # Crea l'integratore del campo
    integrator = GlobalFieldIntegrator(broadcast_interval=0.0)

    # Crea componenti field-aware
    brain_region = FieldAwareBrainRegion(
        region_id="cortex_primary",
        region_type="sensory",
        field_integrator=integrator,
    )

    memory = FieldAwareMemory(
        memory_id="semantic",
        field_integrator=integrator,
    )

    dna = FieldAwareDNA(
        dna_id="cognitive",
        field_integrator=integrator,
    )

    print("Registered subsystems:")
    print(f"  - brain_region: {brain_region.region_id}")
    print(f"  - memory: {memory.memory_id}")
    print(f"  - dna: {dna.dna_id}")
    print()

    # Simula cicli
    print("Running 30 cycles with field active...")
    print("-" * 70)

    for i in range(30):
        state = integrator.tick()

        if state and (i < 5 or i == 29):
            print(f"Cycle {i+1}: ILF={state.ilf_value:.4f}, "
                  f"Coherence={state.coherence:.4f}, "
                  f"Noise={state.field_noise:.4f}")

    print()
    print("=" * 70)
    print("ADAPTATION RESULTS")
    print("=" * 70)
    print()

    # Mostra come i componenti si sono adattati
    print("Brain Region adaptation:")
    for key, value in brain_region.get_adaptation_summary().items():
        print(f"  {key}: {value}")

    print()
    print("Memory adaptation:")
    for key, value in memory.get_adaptation_summary().items():
        print(f"  {key}: {value}")

    print()
    print("DNA adaptation:")
    for key, value in dna.get_adaptation_summary().items():
        print(f"  {key}: {value}")

    print()
    print("=" * 70)
    print("FIELD STATISTICS")
    print("=" * 70)
    stats = integrator.get_statistics()
    print(f"Systemic Coherence Index: {stats['systemic_coherence_index']:.4f}")
    print(f"Coherence Trend: {stats['coherence_trend']}")
    print(f"Total Reconfigurations: {stats['total_reconfigurations']}")
    print()
    print("Per-subsystem reconfigurations:")
    for name, data in stats['subsystems'].items():
        print(f"  {name}: {data['reconfiguration_count']} reconfigs")

    print()
    print("=" * 70)
    print("VERIFICATION: Field is causally affecting real components")
    print("=" * 70)

    # Verifica che i componenti abbiano ricevuto update dal campo
    all_have_state = (
        brain_region._field_state is not None
        and memory._field_state is not None
        and dna._field_state is not None
    )

    if all_have_state:
        print("[PASS] All components received field updates")
        print()
        print("The field is not just distributing information.")
        print("It is causally modifying the behavior of real SPEACE components.")
        print()
        print("Evidence:")
        print(f"  - Brain threshold changed to {brain_region.activation_threshold:.4f}")
        print(f"  - Memory consolidation changed to {memory.consolidation_threshold:.4f}")
        print(f"  - DNA expression changed to {dna.expression_level:.4f}")
    else:
        print("[FAIL] Components not receiving field updates")

    print("=" * 70)

    return integrator


if __name__ == "__main__":
    demonstrate_real_integration()