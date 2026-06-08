import asyncio

import numpy as np
import pytest

from speace_core.orchestrator import CellularBrainOrchestrator
from speace_core.dna.models import SharedGenome


class TestOrchestratorDynamicsIntegration:
    @pytest.fixture
    def orchestrator(self):
        genome = SharedGenome()
        orch = CellularBrainOrchestrator.build_mvp(genome=genome)
        return orch

    def test_dynamics_flags_disabled_by_default(self, orchestrator):
        assert orchestrator.temporal_dynamics_enabled is False
        assert orchestrator.neural_oscillator_enabled is False
        assert orchestrator.phase_coupling_enabled is False
        assert orchestrator.energy_field_enabled is False
        assert orchestrator.predictive_coding_enabled is False
        assert orchestrator.active_inference_enabled is False
        assert orchestrator.homeostatic_drive_enabled is False
        assert orchestrator.criticality_monitor_enabled is False

    def test_orchestrator_initializes_with_all_dynamics_enabled(self):
        genome = SharedGenome()
        orch = CellularBrainOrchestrator.build_mvp(genome=genome)
        orch.temporal_dynamics_enabled = True
        orch.neural_oscillator_enabled = True
        orch.phase_coupling_enabled = True
        orch.energy_field_enabled = True
        orch.predictive_coding_enabled = True
        orch.active_inference_enabled = True
        orch.homeostatic_drive_enabled = True
        orch.criticality_monitor_enabled = True
        # model_post_init runs during build_mvp; we need to trigger re-init
        orch.model_post_init(None)

        assert orch._temporal_dynamics is not None
        assert orch._oscillator_bank is not None
        assert orch._phase_coupling is not None
        assert orch._energy_field is not None
        assert orch._predictive_coding is not None
        assert orch._active_inference is not None
        assert orch._homeostatic_drive is not None
        assert orch._criticality_monitor is not None

    def test_one_tick_advances_all_dynamics_modules(self):
        genome = SharedGenome()
        orch = CellularBrainOrchestrator.build_mvp(genome=genome)
        orch.temporal_dynamics_enabled = True
        orch.neural_oscillator_enabled = True
        orch.phase_coupling_enabled = True
        orch.energy_field_enabled = True
        orch.predictive_coding_enabled = True
        orch.active_inference_enabled = True
        orch.homeostatic_drive_enabled = True
        orch.criticality_monitor_enabled = True
        orch.model_post_init(None)

        # Record initial states where applicable
        t0 = orch._temporal_dynamics.t
        ef_energy0 = orch._energy_field.get_global_energy()

        asyncio.run(orch._tick())

        assert orch._temporal_dynamics.t > t0
        # Oscillator bank should still be valid after stepping
        assert orch._oscillator_bank is not None
        for band in orch._oscillator_bank.bands:
            phase = orch._oscillator_bank.get_phase(band)
            assert 0.0 <= phase < 2.0 * np.pi
        # Energy field should have registered neurons and stepped
        assert orch._energy_field.neuron_count() > 0
        # Predictive coding layers exist
        assert "sensory" in orch._predictive_coding.layers
        assert "association" in orch._predictive_coding.layers
        assert "abstract" in orch._predictive_coding.layers
        # Active inference engine should have stepped (no crash)
        assert orch._active_inference is not None
        # Homeostatic drive modulation should be computed
        modulation = orch._homeostatic_drive.get_global_modulation()
        assert "plasticity_multiplier" in modulation
        # Criticality monitor should have recorded activations
        assert len(orch._criticality_monitor._spikes) > 0

    def test_homeostatic_drive_modulates_circuit_parameters(self):
        genome = SharedGenome()
        orch = CellularBrainOrchestrator.build_mvp(genome=genome)
        orch.homeostatic_drive_enabled = True
        orch.model_post_init(None)

        all_neurons = (
            orch.circuit.input_neurons
            + orch.circuit.hidden_neurons
            + orch.circuit.output_neurons
        )
        original_thresholds = [n.threshold for n in all_neurons]
        original_plasticity = [n.plasticity_rate for n in all_neurons]

        asyncio.run(orch._tick())

        new_thresholds = [n.threshold for n in all_neurons]
        new_plasticity = [n.plasticity_rate for n in all_neurons]

        # At least one parameter should have changed
        assert any(nt != ot for nt, ot in zip(new_thresholds, original_thresholds)) or \
               any(np != op for np, op in zip(new_plasticity, original_plasticity))

    def test_criticality_monitor_records_spikes(self):
        genome = SharedGenome()
        orch = CellularBrainOrchestrator.build_mvp(genome=genome)
        orch.criticality_monitor_enabled = True
        orch.model_post_init(None)

        assert len(orch._criticality_monitor._spikes) == 0
        asyncio.run(orch._tick())
        assert len(orch._criticality_monitor._spikes) > 0
        recommendation = orch._criticality_monitor.recommend_modulation()
        assert "excitability_delta" in recommendation
        assert "target_branching_ratio" in recommendation

    def test_energy_field_registers_neurons_and_synapses(self):
        genome = SharedGenome()
        orch = CellularBrainOrchestrator.build_mvp(genome=genome)
        orch.energy_field_enabled = True
        orch.model_post_init(None)

        assert orch._energy_field.neuron_count() > 0
        assert orch._energy_field.synapse_count() >= 0

    def test_predictive_coding_registers_layers_from_circuit(self):
        genome = SharedGenome()
        orch = CellularBrainOrchestrator.build_mvp(genome=genome)
        orch.predictive_coding_enabled = True
        orch.model_post_init(None)

        assert orch._predictive_coding is not None
        assert orch._predictive_coding.layers["sensory"]["dim"] == len(orch.circuit.input_neurons)
        assert orch._predictive_coding.layers["association"]["dim"] == len(orch.circuit.hidden_neurons)
        assert orch._predictive_coding.layers["abstract"]["dim"] == len(orch.circuit.output_neurons)

    def test_phase_coupling_with_oscillator_bank(self):
        genome = SharedGenome()
        orch = CellularBrainOrchestrator.build_mvp(genome=genome)
        orch.neural_oscillator_enabled = True
        orch.phase_coupling_enabled = True
        orch.model_post_init(None)

        # Oscillator bank bands should be registered as oscillators in phase coupling
        for band in orch._oscillator_bank.bands:
            assert band in orch._phase_coupling.list_oscillators()

        asyncio.run(orch._tick())
        # Phase coupling should step without error
        assert orch._phase_coupling is not None

    def test_temporal_dynamics_engine_synced_with_circuit(self):
        genome = SharedGenome()
        orch = CellularBrainOrchestrator.build_mvp(genome=genome)
        orch.temporal_dynamics_enabled = True
        orch.model_post_init(None)

        neuron_ids = [n.cell_id for n in orch.circuit.input_neurons + orch.circuit.hidden_neurons + orch.circuit.output_neurons]
        # All neurons should be known to the engine
        for nid in neuron_ids:
            assert orch._temporal_dynamics.get_neuron_state(nid) == pytest.approx(0.0, abs=1e-9)

        asyncio.run(orch._tick())
        # After tick, engine time should have advanced
        assert orch._temporal_dynamics.t == pytest.approx(1.0, abs=1e-9)


class TestOrchestratorEmbodimentIntegration:
    def test_embodiment_flags_disabled_by_default(self):
        genome = SharedGenome()
        orch = CellularBrainOrchestrator.build_mvp(genome=genome)
        assert orch.embodiment_enabled is False
        assert orch._sensor_array is None
        assert orch._physical_environment is None
        assert orch._embodied_actuator is None
        assert orch._embodiment_monitor is None

    def test_orchestrator_initializes_embodiment_when_enabled(self):
        genome = SharedGenome()
        orch = CellularBrainOrchestrator.build_mvp(genome=genome)
        orch.embodiment_enabled = True
        orch.model_post_init(None)

        assert orch._sensor_array is not None
        assert orch._physical_environment is not None
        assert orch._embodied_actuator is not None
        assert orch._embodiment_monitor is not None
        assert orch._last_sensor_snapshot is not None

    def test_embodiment_tick_closes_sensorimotor_loop(self):
        genome = SharedGenome()
        orch = CellularBrainOrchestrator.build_mvp(genome=genome)
        orch.embodiment_enabled = True
        orch.model_post_init(None)

        asyncio.run(orch._tick())

        # Sensor snapshot should be updated after tick
        assert orch._last_sensor_snapshot is not None
        # Embodiment monitor should have recorded a tick
        assert orch._embodiment_monitor._tick_count == 1

    def test_embodiment_with_active_inference_registers_actions(self):
        genome = SharedGenome()
        orch = CellularBrainOrchestrator.build_mvp(genome=genome)
        orch.embodiment_enabled = True
        orch.active_inference_enabled = True
        orch.model_post_init(None)

        assert orch._active_inference is not None
        assert "stable" in orch._active_inference.beliefs
        assert "unstable" in orch._active_inference.beliefs
        assert "observe" in orch._active_inference.actions
        assert "actuate" in orch._active_inference.actions

    def test_flatten_sensor_snapshot(self):
        snapshot = {
            "cpu": {"usage_percent": 25.0},
            "memory": {"used_bytes": 2048.0},
            "disk": {"drives": [{"used_bytes": 1024.0}]},
            "network": {"bytes_received": 100.0, "bytes_sent": 50.0},
            "temperature": {"cpu_celsius": 45.0},
            "process": {"process_count": 42.0},
            "power": {"battery_percent": 80.0},
        }
        flat = CellularBrainOrchestrator._flatten_sensor_snapshot(snapshot)
        assert flat["cpu_avg"] == 25.0
        assert flat["mem_used"] == 2048.0
        assert flat["disk_used"] == 1024.0
        assert flat["net_in"] == 100.0
        assert flat["net_out"] == 50.0
        assert flat["temp_avg"] == 45.0
        assert flat["process_count"] == 42.0
        assert flat["battery_level"] == 80.0
