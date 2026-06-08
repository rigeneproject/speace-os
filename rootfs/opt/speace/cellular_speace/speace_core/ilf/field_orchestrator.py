from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
import time
import random
import hashlib

from speace_core.ilf import (
    InformationalField, FieldState, ILFEngine, ILFMetrics,
    SubsystemFieldConnector, FieldBroadcastScheduler
)
from speace_core.evolution import EvolutionController, FitnessTracker
from speace_core.evolution.safety import SafetyLayer
from speace_core.experiments import ExperimentTracker


class MockBrain:
    """Simulated brain subsystem."""

    def __init__(self):
        self.field_state: Optional[FieldState] = None
        self.region_outputs = {'cortex': 0.6, 'hippocampus': 0.5, 'amygdala': 0.4}
        self.activation_modifier = 1.0
        self.update_count = 0

    def update_from_field(self, state: FieldState) -> None:
        self.field_state = state
        self.update_count += 1

        # Adapt behavior based on field
        if state.ilf_value < 0.4:
            # Low coherence - increase inhibition
            self.activation_modifier = 0.8
        elif state.ilf_value > 0.6:
            # High coherence - increase activation
            self.activation_modifier = 1.1
        else:
            self.activation_modifier = 1.0

    def get_ilf_metrics(self) -> ILFMetrics:
        # Outputs vary based on field state
        modifier = self.activation_modifier
        outputs = {k: min(1.0, v * modifier) for k, v in self.region_outputs.items()}
        return ILFMetrics(
            region_outputs=outputs,
            cell_states={'neuron_1': 0.7, 'neuron_2': 0.6},
            cell_types={'neuron_1': 'excitatory', 'neuron_2': 'inhibitory'},
            energy_levels={'cortex': 0.7, 'hippocampus': 0.6},
            memory_utilization=0.6,
            memory_retention=0.75,
            learning_rate=0.1,
            error_rate=0.08,
            goal_activations={'explore': 0.5, 'learn': 0.6},
            ilf_history=[0.5] * 10,
        )


class MockMemory:
    """Simulated memory subsystem."""

    def __init__(self):
        self.field_state: Optional[FieldState] = None
        self.consolidation_threshold = 0.6
        self.forgetting_rate = 0.05
        self.update_count = 0

    def update_from_field(self, state: FieldState) -> None:
        self.field_state = state
        self.update_count += 1

        # Adapt memory parameters based on field
        if state.field_noise > 0.3:
            # High noise - increase consolidation threshold
            self.consolidation_threshold = min(0.9, self.consolidation_threshold * 1.1)
        else:
            self.consolidation_threshold = max(0.4, self.consolidation_threshold * 0.98)

    def get_ilf_metrics(self) -> ILFMetrics:
        return ILFMetrics(
            region_outputs={'semantic': 0.65, 'episodic': 0.55},
            memory_utilization=self.consolidation_threshold,
            memory_retention=1.0 - self.forgetting_rate,
            learning_rate=0.08,
            error_rate=self.forgetting_rate,
            ilf_history=[0.5] * 10,
        )


class MockDNA:
    """Simulated DNA subsystem."""

    def __init__(self):
        self.field_state: Optional[FieldState] = None
        self.mutation_rate = 0.1
        self.expression_level = 0.7
        self.update_count = 0

    def update_from_field(self, state: FieldState) -> None:
        self.field_state = state
        self.update_count += 1

        # Adapt genetic expression based on field
        if state.continuity < 0.4:
            # Low continuity - increase plasticity
            self.expression_level = min(1.0, self.expression_level * 1.2)
        else:
            self.expression_level = max(0.5, self.expression_level * 0.98)

    def get_ilf_metrics(self) -> ILFMetrics:
        return ILFMetrics(
            region_outputs={'nucleus': 0.7, 'cytoplasm': 0.6},
            cell_states={'gene_1': self.expression_level, 'gene_2': 0.6},
            cell_types={'gene_1': 'cognitive', 'gene_2': 'plasticity'},
            memory_utilization=0.5,
            memory_retention=0.8,
            learning_rate=self.mutation_rate,
            error_rate=0.05,
            ilf_history=[0.5] * 10,
        )


class MockAgents:
    """Simulated agents subsystem."""

    def __init__(self):
        self.field_state: Optional[FieldState] = None
        self.exploration_rate = 0.3
        self.exploitation_rate = 0.7
        self.update_count = 0

    def update_from_field(self, state: FieldState) -> None:
        self.field_state = state
        self.update_count += 1

        # Adapt agent behavior based on field
        if state.adaptation < 0.4:
            # Low adaptation - increase exploration
            self.exploration_rate = min(0.5, self.exploration_rate * 1.1)
            self.exploitation_rate = 1.0 - self.exploration_rate
        else:
            self.exploration_rate = max(0.2, self.exploration_rate * 0.98)
            self.exploitation_rate = 1.0 - self.exploration_rate

    def get_ilf_metrics(self) -> ILFMetrics:
        return ILFMetrics(
            region_outputs={'agent_1': 0.6, 'agent_2': 0.55},
            memory_utilization=0.65,
            memory_retention=0.7,
            learning_rate=self.exploration_rate,
            error_rate=1.0 - self.exploitation_rate,
            ilf_history=[0.5] * 10,
        )


class DynamicSystemOrchestrator:
    """Orchestratore del sistema dinamico completo.

    Dimostra il ciclo chiuso:
    Esperienza → Memoria → ILF (campo) → Valutazione → Evoluzione → Nuova Architettura → Nuova Esperienza
    """

    def __init__(
        self,
        cycle_interval: float = 0.0,  # 0 = every cycle for simulation
        use_tracker: bool = True,
    ):
        # Core field
        self.field = InformationalField()

        # Subsystems
        self.brain = MockBrain()
        self.memory = MockMemory()
        self.dna = MockDNA()
        self.agents = MockAgents()

        # Connectors
        self.brain_conn = SubsystemFieldConnector(
            'brain', self.field, on_receive_state=self.brain.update_from_field
        )
        self.memory_conn = SubsystemFieldConnector(
            'memory', self.field, on_receive_state=self.memory.update_from_field
        )
        self.dna_conn = SubsystemFieldConnector(
            'dna', self.field, on_receive_state=self.dna.update_from_field
        )
        self.agents_conn = SubsystemFieldConnector(
            'agents', self.field, on_receive_state=self.agents.update_from_field
        )

        # Scheduler
        self.scheduler = FieldBroadcastScheduler(self.field)
        self.scheduler.set_cycle_interval(cycle_interval)  # 0 = every cycle

        # Register subsystem metrics providers
        self.scheduler.register_subsystem_metrics('brain', self.brain.get_ilf_metrics)
        self.scheduler.register_subsystem_metrics('memory', self.memory.get_ilf_metrics)
        self.scheduler.register_subsystem_metrics('dna', self.dna.get_ilf_metrics)
        self.scheduler.register_subsystem_metrics('agents', self.agents.get_ilf_metrics)

        # Tracking
        self.tracker = ExperimentTracker('data/experiments/field_test') if use_tracker else None

        # State
        self._cycle = 0
        self._running = False
        self._history: List[Dict[str, Any]] = []

    def tick(self) -> Optional[FieldState]:
        """Esegue un ciclo del sistema."""
        self._cycle += 1

        # Broadcast field state (pass current cycle)
        state = self.scheduler.tick(self._cycle)

        if state:
            # Record
            if self.tracker:
                self.tracker.record_ilf(
                    cycle=self._cycle,
                    ilf_state=state.to_dict(),
                    trend=self.field.get_coherence_trend(),
                )

            # Store history
            self._history.append({
                'cycle': self._cycle,
                'timestamp': state.timestamp,
                'ilf_value': state.ilf_value,
                'coherence': state.coherence,
                'adaptation': state.adaptation,
                'continuity': state.continuity,
                'field_noise': state.field_noise,
                'field_stability': state.field_stability,
                'brain_updates': self.brain.update_count,
                'memory_updates': self.memory.update_count,
                'dna_updates': self.dna.update_count,
                'agents_updates': self.agents.update_count,
            })

        return state

    def run_cycles(self, n: int, verbose: bool = True) -> List[Dict[str, Any]]:
        """Esegue N cicli."""
        results = []
        for i in range(n):
            state = self.tick()
            if state and verbose:
                print(f"Cycle {self._cycle}: ILF={state.ilf_value:.4f}, "
                      f"Coherence={state.coherence:.4f}, "
                      f"Adaptation={state.adaptation:.4f}, "
                      f"Noise={state.field_noise:.4f}")
            results.append(state)
        return results

    def get_systemic_coherence_index(self) -> float:
        """Systemic Coherence Index del sistema."""
        return self.field.get_systemic_coherence_index()

    def get_statistics(self) -> Dict[str, Any]:
        """Statistiche complete del sistema."""
        return {
            'cycle': self._cycle,
            'systemic_coherence_index': self.get_systemic_coherence_index(),
            'field_hash': self.field.get_field_hash(),
            'subsystems': {
                'brain': {
                    'updates': self.brain.update_count,
                    'activation_modifier': self.brain.activation_modifier,
                },
                'memory': {
                    'updates': self.memory.update_count,
                    'consolidation_threshold': self.memory.consolidation_threshold,
                },
                'dna': {
                    'updates': self.dna.update_count,
                    'expression_level': self.dna.expression_level,
                },
                'agents': {
                    'updates': self.agents.update_count,
                    'exploration_rate': self.agents.exploration_rate,
                },
            },
            'field_trend': self.field.get_coherence_trend(),
            'history_length': len(self._history),
        }

    def print_summary(self) -> None:
        """Stampa un riepilogo del sistema."""
        stats = self.get_statistics()
        print()
        print("=" * 60)
        print("DYNAMIC FIELD SYSTEM - SUMMARY")
        print("=" * 60)
        print(f"Cycles executed: {stats['cycle']}")
        print(f"Systemic Coherence Index (SCI): {stats['systemic_coherence_index']:.4f}")
        print(f"Field hash: {stats['field_hash']}")
        print(f"Field trend: {stats['field_trend']}")
        print()
        print("Subsystems status:")
        for name, data in stats['subsystems'].items():
            print(f"  {name}:")
            for k, v in data.items():
                if isinstance(v, float):
                    print(f"    {k}: {v:.4f}")
                else:
                    print(f"    {k}: {v}")
        print("=" * 60)


def demonstrate_field_based_system():
    """Dimostrazione completa del sistema a campo."""
    print("Creating Dynamic Field-Based SPEACE System...")
    print()

    # Create orchestrator
    orchestrator = DynamicSystemOrchestrator(cycle_interval=0.1)

    print("Subsystems registered:")
    print("  - Brain (cortex, hippocampus, amygdala)")
    print("  - Memory (semantic, episodic)")
    print("  - DNA (cognitive, plasticity genes)")
    print("  - Agents (exploration, exploitation)")
    print()

    # Run initial cycles
    print("Running 20 cycles...")
    print("-" * 60)
    orchestrator.run_cycles(20, verbose=True)

    # Print summary
    orchestrator.print_summary()

    # Verify subsystems received field state
    print()
    print("Subsystem field state reception:")
    print(f"  Brain: {orchestrator.brain.update_count} updates")
    print(f"  Memory: {orchestrator.memory.update_count} updates")
    print(f"  DNA: {orchestrator.dna.update_count} updates")
    print(f"  Agents: {orchestrator.agents.update_count} updates")

    # Verify behavioral adaptation
    print()
    print("Behavioral adaptation:")
    print(f"  Brain activation modifier: {orchestrator.brain.activation_modifier:.4f}")
    print(f"  Memory consolidation threshold: {orchestrator.memory.consolidation_threshold:.4f}")
    print(f"  DNA expression level: {orchestrator.dna.expression_level:.4f}")
    print(f"  Agents exploration rate: {orchestrator.agents.exploration_rate:.4f}")

    return orchestrator


if __name__ == "__main__":
    demonstrate_field_based_system()