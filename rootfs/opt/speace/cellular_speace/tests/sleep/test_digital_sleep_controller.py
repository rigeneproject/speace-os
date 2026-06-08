from speace_core.cellular_brain.sleep.digital_sleep_controller import DigitalSleepController
from speace_core.cellular_brain.sleep.sleep_cycle_detector import SleepPhase
from speace_core.cellular_brain.regulation.homeostasis_engine import SystemMetrics
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.cells.digital_synapse import DigitalSynapse
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory


def _make_orchestrator():
    class FakeOrchestrator:
        def __init__(self):
            self.metrics_log = []
            self.current_tick = 0
            n1 = DigitalNeuron(cell_id="n1", role="input")
            n2 = DigitalNeuron(cell_id="n2", role="output")
            syn = DigitalSynapse(cell_id="s1", role="synapse", source="n1", target="n2", weight=0.02)
            self.circuit = NeuralCircuit(
                circuit_id="c1", input_neurons=[n1], output_neurons=[n2], synapses=[syn]
            )
            self._memory = MorphologicalMemory()
            self._memory.load()

    return FakeOrchestrator()


def test_controller_starts_awake():
    ctrl = DigitalSleepController()
    assert ctrl.state.phase == SleepPhase.AWAKE


def test_controller_enters_sleep_after_stable_period():
    orch = _make_orchestrator()
    ctrl = DigitalSleepController(sleep_duration_ticks=2)
    # Fill metrics with stable values
    orch.metrics_log = [
        SystemMetrics(tick=i, coherence_phi=0.7, mean_energy=0.5, active_neurons=10, pruned_synapses=0)
        for i in range(20)
    ]
    # First tick: detect eligible
    ctrl.tick(orch)
    assert ctrl.state.phase == SleepPhase.SLEEP_ELIGIBLE
    # Need min_consecutive_stable ticks to enter sleep
    for _ in range(ctrl.detector.min_consecutive_stable):
        ctrl.tick(orch)
    assert ctrl.state.phase == SleepPhase.SLEEPING


def test_controller_runs_consolidation_during_sleep():
    orch = _make_orchestrator()
    ctrl = DigitalSleepController(sleep_duration_ticks=2)
    ctrl.state.phase = SleepPhase.SLEEPING
    ctrl.sleep_ticks_remaining = 2
    ctrl.tick(orch)
    assert ctrl.sleep_ticks_remaining == 1
    assert ctrl.last_consolidation_result is not None


def test_controller_exits_sleep_after_duration():
    orch = _make_orchestrator()
    ctrl = DigitalSleepController(sleep_duration_ticks=1)
    ctrl.state.phase = SleepPhase.SLEEPING
    ctrl.sleep_ticks_remaining = 1
    ctrl.tick(orch)
    assert ctrl.state.phase == SleepPhase.AWAKE
