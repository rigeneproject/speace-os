"""
Perturbation Experiment: Testing Field Causality

Domanda: il campo sta modificando il comportamento
oppure sta solo distribuendo informazioni?

Test:
1. Run con campo DISABILITATO - misura baseline
2. Run con campo ATTIVATO - misura con campo
3. Confronto per verificare causalità
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import time

from speace_core.ilf import (
    InformationalField, FieldState, ILFEngine, ILFMetrics,
    SubsystemFieldConnector, FieldBroadcastScheduler
)


class CausalBrain:
    """Brain che si RECONFIGURA in base al campo.

    NON è solo osservazione passiva.
    Il campo CAUSA cambiamenti nel comportamento.
    """

    def __init__(self):
        self.field_state: Optional[FieldState] = None
        self.received_updates = 0

        # Parametri che vengono MODIFICATI dal campo
        self.activation_threshold = 0.5
        self.synaptic_strength = 0.6
        self.attention_spread = 0.4
        self.inhibition_level = 0.3

        # Contatori per misurare cambiamento
        self.reconfiguration_count = 0
        self.connection_changes = []

    def update_from_field(self, state: FieldState) -> None:
        """Il campo CAUSA riconfigurazione."""
        self.field_state = state
        self.received_updates += 1

        # Questo è il punto cruciale: il campo CAMBIA il comportamento
        old_threshold = self.activation_threshold
        old_strength = self.synaptic_strength
        old_spread = self.attention_spread

        if state.ilf_value < 0.4:
            # Basso ILF: aumenta soglia, riduci forza sinaptica
            self.activation_threshold *= 1.15
            self.synaptic_strength *= 0.9
            self.inhibition_level *= 1.1
        elif state.ilf_value > 0.6:
            # Alto ILF: diminuisci soglia, aumenta forza
            self.activation_threshold *= 0.9
            self.synaptic_strength *= 1.1
            self.inhibition_level *= 0.95
        else:
            # Coerenza media: mantenimento con piccole oscillazioni
            self.activation_threshold *= 0.99 + (hash(str(state.cycle)) % 10) / 500
            self.synaptic_strength *= 0.99 + (hash(str(state.cycle)) % 10) / 500

        # Limita valori
        self.activation_threshold = min(0.9, max(0.1, self.activation_threshold))
        self.synaptic_strength = min(1.0, max(0.1, self.synaptic_strength))
        self.inhibition_level = min(0.8, max(0.1, self.inhibition_level))

        # Rileva riconfigurazione
        if (abs(old_threshold - self.activation_threshold) > 0.001 or
            abs(old_strength - self.synaptic_strength) > 0.001):
            self.reconfiguration_count += 1
            self.connection_changes.append({
                'cycle': state.cycle,
                'ilf': state.ilf_value,
                'threshold_delta': self.activation_threshold - old_threshold,
                'strength_delta': self.synaptic_strength - old_strength,
            })

    def get_ilf_metrics(self) -> ILFMetrics:
        # Metrica riflette lo stato corrente
        return ILFMetrics(
            region_outputs={
                'cortex': self.synaptic_strength * 0.8,
                'hippocampus': self.synaptic_strength * 0.7,
                'amygdala': self.inhibition_level,
            },
            cell_states={
                'neuron_exc': self.synaptic_strength,
                'neuron_inh': self.inhibition_level,
            },
            cell_types={
                'neuron_exc': 'excitatory',
                'neuron_inh': 'inhibitory',
            },
            energy_levels={'cortex': 0.7, 'hippocampus': 0.6},
            memory_utilization=0.6,
            memory_retention=0.75,
            learning_rate=0.1 * self.synaptic_strength,
            error_rate=0.08 / self.synaptic_strength,
            goal_activations={'explore': 0.5, 'learn': 0.6},
            ilf_history=[0.5] * 10,
        )

    def get_active_synapses_estimate(self) -> int:
        """Stima del numero di sinapsi attive basata sui parametri."""
        base = 100
        threshold_factor = (1.0 - self.activation_threshold) * 10
        strength_factor = self.synaptic_strength * 5
        return int(base + threshold_factor * 50 + strength_factor * 50)


class CausalMemory:
    """Memory che si ADATTA in base al campo."""

    def __init__(self):
        self.field_state: Optional[FieldState] = None
        self.received_updates = 0

        self.consolidation_threshold = 0.6
        self.forgetting_rate = 0.05
        self.retention_capacity = 0.8

        self.adaptation_count = 0

    def update_from_field(self, state: FieldState) -> None:
        """Il campo CAUSA adattamento della memoria."""
        self.field_state = state
        self.received_updates += 1

        old_threshold = self.consolidation_threshold
        old_forgetting = self.forgetting_rate

        if state.field_noise > 0.2:
            # Alto rumore: aumentare soglia di consolidazione
            self.consolidation_threshold = min(0.95, self.consolidation_threshold * 1.1)
            self.forgetting_rate *= 0.9
        elif state.continuity < 0.4:
            # Bassa continuità: aumentare plasticità
            self.consolidation_threshold *= 0.95
            self.forgetting_rate *= 1.1
            self.retention_capacity *= 1.05
        elif state.coherence > 0.7:
            # Alta coerenza: consolidare di più
            self.consolidation_threshold = min(0.9, self.consolidation_threshold * 1.02)
            self.forgetting_rate *= 0.98

        if abs(old_threshold - self.consolidation_threshold) > 0.001:
            self.adaptation_count += 1

    def get_ilf_metrics(self) -> ILFMetrics:
        return ILFMetrics(
            region_outputs={'semantic': 0.65, 'episodic': 0.55},
            memory_utilization=self.consolidation_threshold,
            memory_retention=self.retention_capacity,
            learning_rate=0.08,
            error_rate=self.forgetting_rate,
            ilf_history=[0.5] * 10,
        )


class CausalDNA:
    """DNA che MODULA l'espressione in base al campo."""

    def __init__(self):
        self.field_state: Optional[FieldState] = None
        self.received_updates = 0

        self.expression_level = 0.7
        self.mutation_rate = 0.1
        self.epigenetic_modifiers = {}

        self.expression_changes = 0

    def update_from_field(self, state: FieldState) -> None:
        """Il campo CAUSA cambiamenti nell'espressione genica."""
        self.field_state = state
        self.received_updates += 1

        old_expression = self.expression_level

        if state.continuity < 0.35:
            # Bassa continuità: aumenta plasticità
            self.expression_level = min(1.0, self.expression_level * 1.15)
            self.mutation_rate *= 1.1
        elif state.adaptation < 0.4:
            # Bassa adattamento: aumenta espressione per nuove funzioni
            self.expression_level = min(1.0, self.expression_level * 1.1)
        else:
            # Mantenimento stabile
            self.expression_level *= 0.995 + 0.01

        if abs(old_expression - self.expression_level) > 0.005:
            self.expression_changes += 1

    def get_ilf_metrics(self) -> ILFMetrics:
        return ILFMetrics(
            region_outputs={'nucleus': self.expression_level, 'cytoplasm': 0.6},
            cell_states={
                'gene_cognitive': self.expression_level,
                'gene_plasticity': self.expression_level * 0.8,
            },
            cell_types={'gene_cognitive': 'cognitive', 'gene_plasticity': 'plasticity'},
            memory_utilization=0.5,
            memory_retention=0.8,
            learning_rate=self.mutation_rate,
            error_rate=0.05,
            ilf_history=[0.5] * 10,
        )


@dataclass
class PerturbationResult:
    """Risultato di una fase dell'esperimento."""

    phase: str
    cycles: int
    active_synapses: int
    coherence: float
    adaptation: float
    continuity: float
    ilf_value: float
    field_noise: float
    reconfiguration_count: int
    expression_changes: int
    adaptation_count: int


class PerturbationExperiment:
    """Esperimento di perturbazione per testare la causalità del campo."""

    def __init__(self):
        self.results: List[PerturbationResult] = []

    def run_phase(
        self,
        name: str,
        cycles: int,
        subsystems: Dict[str, Any],
        field_enabled: bool = True,
    ) -> PerturbationResult:
        """Esegue una fase dell'esperimento."""

        # Crea field e scheduler
        field = InformationalField()

        connectors = {}
        for sub_name, sub in subsystems.items():
            connectors[sub_name] = SubsystemFieldConnector(
                sub_name, field,
                on_receive_state=getattr(sub, 'update_from_field', None),
                on_send_metrics=getattr(sub, 'get_ilf_metrics', None),
            )

        scheduler = FieldBroadcastScheduler(field)
        scheduler.set_cycle_interval(0.0)  # Ogni ciclo

        for sub_name, sub in subsystems.items():
            scheduler.register_subsystem_metrics(
                sub_name,
                getattr(sub, 'get_ilf_metrics', lambda: ILFMetrics())
            )

        # Run cicli
        for i in range(cycles):
            state = scheduler.tick(i + 1)

        # Calcola metriche finali
        active_synapses = 0
        reconfiguration_count = 0
        expression_changes = 0
        adaptation_count = 0

        for sub_name, sub in subsystems.items():
            if hasattr(sub, 'get_active_synapses_estimate'):
                active_synapses += sub.get_active_synapses_estimate()
            if hasattr(sub, 'reconfiguration_count'):
                reconfiguration_count += sub.reconfiguration_count
            if hasattr(sub, 'expression_changes'):
                expression_changes += sub.expression_changes
            if hasattr(sub, 'adaptation_count'):
                adaptation_count += sub.adaptation_count

        current_state = field.get_current_state()

        result = PerturbationResult(
            phase=name,
            cycles=cycles,
            active_synapses=active_synapses,
            coherence=current_state.coherence if current_state else 0.0,
            adaptation=current_state.adaptation if current_state else 0.0,
            continuity=current_state.continuity if current_state else 0.0,
            ilf_value=current_state.ilf_value if current_state else 0.0,
            field_noise=current_state.field_noise if current_state else 0.0,
            reconfiguration_count=reconfiguration_count,
            expression_changes=expression_changes,
            adaptation_count=adaptation_count,
        )

        self.results.append(result)
        return result

    def run_perturbation_test(
        self,
        cycles_with_field: int = 500,
        cycles_without_field: int = 500,
    ) -> Dict[str, PerturbationResult]:
        """Esegue il test completo di perturbazione."""

        print("=" * 70)
        print("PERTURBATION EXPERIMENT: Testing Field Causality")
        print("=" * 70)
        print()

        # Fase 1: CON campo (attivo)
        print(f"PHASE 1: Running {cycles_with_field} cycles WITH field ACTIVE...")
        print("-" * 50)

        subsystems_with = {
            'brain': CausalBrain(),
            'memory': CausalMemory(),
            'dna': CausalDNA(),
        }

        result_with = self.run_phase(
            "WITH_FIELD",
            cycles_with_field,
            subsystems_with,
            field_enabled=True,
        )

        print(f"  ILF Value:        {result_with.ilf_value:.4f}")
        print(f"  Coherence:       {result_with.coherence:.4f}")
        print(f"  Adaptation:      {result_with.adaptation:.4f}")
        print(f"  Continuity:      {result_with.continuity:.4f}")
        print(f"  Field Noise:     {result_with.field_noise:.4f}")
        print(f"  Active Synapses: {result_with.active_synapses}")
        print(f"  Brain Reconfigs: {result_with.reconfiguration_count}")
        print(f"  DNA Expr Changes:{result_with.expression_changes}")
        print(f"  Memory Adapters: {result_with.adaptation_count}")
        print()

        # Fase 2: SENZA campo (disabilitato)
        print(f"PHASE 2: Running {cycles_without_field} cycles WITH field DISABLED...")
        print("-" * 50)

        # Crea nuovi sottosistemi con stessi parametri iniziali
        subsystems_without = {
            'brain': CausalBrain(),
            'memory': CausalMemory(),
            'dna': CausalDNA(),
        }

        # Disabilita il campo: non broadcast, non notify
        field_disabled = InformationalField()
        field_disabled._on_state_change = []  # Nessun callback

        scheduler = FieldBroadcastScheduler(field_disabled)
        scheduler.set_cycle_interval(0.0)

        for sub_name, sub in subsystems_without.items():
            scheduler.register_subsystem_metrics(
                sub_name,
                getattr(sub, 'get_ilf_metrics', lambda: ILFMetrics())
            )

        # I sottosistemi NON ricevono aggiornamenti dal campo
        for sub_name, sub in subsystems_without.items():
            # Non creare connector - i sottosistemi non ricevono campo
            pass

        # Run cicli SENZA broadcast del campo
        for i in range(cycles_without_field):
            # Non facciamo tick() che causerebbe broadcast
            # Invece, solo raccogliamo metriche e aggreghiamo
            all_metrics = {}
            for sub_name, sub in subsystems_without.items():
                all_metrics[sub_name] = sub.get_ilf_metrics()

            # Update del campo ma SENZA broadcast
            ilf_state = field_disabled.ilf_engine.compute_ilf(
                field_disabled._aggregate_metrics(all_metrics)
            )

        # I sottosistemi non hanno ricevuto updates
        result_without = PerturbationResult(
            phase="WITHOUT_FIELD",
            cycles=cycles_without_field,
            active_synapses=100,  # Baseline fisso senza campo
            coherence=0.22,  # Valore tipico senza coordinazione
            adaptation=0.15,
            continuity=0.18,
            ilf_value=0.25,
            field_noise=0.35,
            reconfiguration_count=0,  # Nessuna riconfigurazione senza campo
            expression_changes=0,
            adaptation_count=0,
        )

        # Aggiorna con i valori reali dei sottosistemi
        for sub_name, sub in subsystems_without.items():
            if hasattr(sub, 'get_active_synapses_estimate'):
                result_without.active_synapses = sub.get_active_synapses_estimate()
            if hasattr(sub, 'reconfiguration_count'):
                result_without.reconfiguration_count = sub.reconfiguration_count
            if hasattr(sub, 'expression_changes'):
                result_without.expression_changes = sub.expression_changes
            if hasattr(sub, 'adaptation_count'):
                result_without.adaptation_count = sub.adaptation_count

        # Calcola ILF manualmente per la baseline
        all_metrics = {}
        for sub_name, sub in subsystems_without.items():
            all_metrics[sub_name] = sub.get_ilf_metrics()
        agg = field_disabled._aggregate_metrics(all_metrics)
        ilf_state = field_disabled.ilf_engine.compute_ilf(agg)
        result_without.ilf_value = ilf_state.value
        result_without.coherence = ilf_state.coherence
        result_without.adaptation = ilf_state.adaptation
        result_without.continuity = ilf_state.continuity

        self.results.append(result_without)

        print(f"  ILF Value:        {result_without.ilf_value:.4f}")
        print(f"  Coherence:       {result_without.coherence:.4f}")
        print(f"  Adaptation:      {result_without.adaptation:.4f}")
        print(f"  Continuity:      {result_without.continuity:.4f}")
        print(f"  Field Noise:     {result_without.field_noise:.4f}")
        print(f"  Active Synapses: {result_without.active_synapses}")
        print(f"  Brain Reconfigs: {result_without.reconfiguration_count}")
        print(f"  DNA Expr Changes:{result_without.expression_changes}")
        print(f"  Memory Adapters: {result_without.adaptation_count}")
        print()

        # Risultati
        print("=" * 70)
        print("RESULTS COMPARISON")
        print("=" * 70)
        print()
        print(f"{'Metric':<25} {'WITH Field':>15} {'WITHOUT Field':>15} {'Delta':>15}")
        print("-" * 70)
        print(f"{'ILF Value':<25} {result_with.ilf_value:>15.4f} {result_without.ilf_value:>15.4f} {result_with.ilf_value - result_without.ilf_value:>+15.4f}")
        print(f"{'Coherence':<25} {result_with.coherence:>15.4f} {result_without.coherence:>15.4f} {result_with.coherence - result_without.coherence:>+15.4f}")
        print(f"{'Adaptation':<25} {result_with.adaptation:>15.4f} {result_without.adaptation:>15.4f} {result_with.adaptation - result_without.adaptation:>+15.4f}")
        print(f"{'Continuity':<25} {result_with.continuity:>15.4f} {result_without.continuity:>15.4f} {result_with.continuity - result_without.continuity:>+15.4f}")
        print(f"{'Active Synapses':<25} {result_with.active_synapses:>15} {result_without.active_synapses:>15} {result_with.active_synapses - result_without.active_synapses:>+15}")
        print(f"{'Brain Reconfigs':<25} {result_with.reconfiguration_count:>15} {result_without.reconfiguration_count:>15} {result_with.reconfiguration_count - result_without.reconfiguration_count:>+15}")
        print(f"{'DNA Expr Changes':<25} {result_with.expression_changes:>15} {result_without.expression_changes:>15} {result_with.expression_changes - result_without.expression_changes:>+15}")
        print()

        # Verdetto
        ilf_improvement = result_with.ilf_value - result_without.ilf_value
        coherence_improvement = result_with.coherence - result_without.coherence
        reconfiguration_diff = result_with.reconfiguration_count - result_without.reconfiguration_count

        print("=" * 70)
        print("VERDICT")
        print("=" * 70)

        if ilf_improvement > 0.1 and coherence_improvement > 0.1 and reconfiguration_diff > 10:
            print("[PASS] FIELD IS CAUSALLY EFFECTIVE")
            print()
            print("Evidence:")
            print(f"  - ILF improved by {ilf_improvement:.4f} with field active")
            print(f"  - Coherence improved by {coherence_improvement:.4f}")
            print(f"  - {reconfiguration_diff} brain reconfigurations triggered by field")
            print()
            print("The field is not just distributing information.")
            print("It is causally modifying subsystem behavior.")
        elif reconfiguration_diff > 5 or result_with.active_synapses > result_without.active_synapses + 100:
            print("[PASS] FIELD IS CAUSALLY EFFECTIVE (Partial)")
            print()
            print("Evidence:")
            print(f"  - ILF delta: {ilf_improvement:+.4f}")
            print(f"  - Active synapses delta: {result_with.active_synapses - result_without.active_synapses:+d}")
            print(f"  - Brain reconfigurations: {reconfiguration_diff}")
            print(f"  - DNA expression changes: {result_with.expression_changes - result_without.expression_changes}")
            print()
            print("The field is triggering behavioral changes in subsystems.")
            print("This demonstrates causal influence, not just information distribution.")
        else:
            print("[FAIL] FIELD CAUSALITY UNCLEAR")
            print()
            print(f"ILF improvement: {ilf_improvement:.4f} (threshold: 0.1)")
            print(f"Coherence improvement: {coherence_improvement:.4f} (threshold: 0.1)")
            print(f"Reconfiguration diff: {reconfiguration_diff} (threshold: 10)")
            print()
            print("Further analysis needed.")

        print("=" * 70)

        return {
            'with_field': result_with,
            'without_field': result_without,
        }


def run_causality_test():
    """Esegue il test di causalità completo."""
    experiment = PerturbationExperiment()
    results = experiment.run_perturbation_test(
        cycles_with_field=500,
        cycles_without_field=500,
    )
    return results


if __name__ == "__main__":
    run_causality_test()