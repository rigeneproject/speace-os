import pytest
from speace_core.orchestrator import CellularBrainOrchestrator
from speace_core.cellular_brain.cyber_physical.cyber_physical_models import (
    ExternalSignal,
)
from speace_core.dna.models import SharedGenome


class TestOrchestratorCyberPhysicalIntegration:
    @pytest.fixture
    def orchestrator(self):
        genome = SharedGenome()
        return CellularBrainOrchestrator.build_mvp(genome=genome)

    def test_cyber_physical_flag_disabled_by_default(self, orchestrator):
        assert orchestrator.cyber_physical_assimilation_enabled is False

    def test_get_cyber_physical_gateway_when_disabled(self, orchestrator):
        gateway = orchestrator.get_cyber_physical_gateway()
        assert gateway is not None

    def test_ingest_external_signal_simulated_disabled(self, orchestrator):
        signal = ExternalSignal(
            signal_id="s1",
            source_id="src",
            signal_type="environmental",
            value=0.5,
        )
        result = orchestrator.ingest_external_signal_simulated(signal)
        assert "error" in result
        assert result["error"] == "cyber_physical_assimilation_disabled"

    def test_synthesize_world_state_disabled(self, orchestrator):
        result = orchestrator.synthesize_world_state()
        assert result is None

    def test_run_cyber_physical_audit_disabled(self, orchestrator):
        import asyncio
        result = asyncio.run(orchestrator.run_cyber_physical_audit())
        assert result is None

    def test_ingest_external_signal_simulated_enabled(self, orchestrator):
        orchestrator.cyber_physical_assimilation_enabled = True
        signal = ExternalSignal(
            signal_id="s1",
            source_id="src",
            signal_type="environmental",
            value=0.5,
            confidence=0.8,
            noise_score=0.1,
        )
        result = orchestrator.ingest_external_signal_simulated(signal)
        assert "error" not in result
        assert result["accepted"] is True

    def test_run_cyber_physical_audit_enabled(self, orchestrator):
        import asyncio
        orchestrator.cyber_physical_assimilation_enabled = True
        result = asyncio.run(orchestrator.run_cyber_physical_audit())
        assert result is not None
        assert "aggregate_verdict" in result
        assert result["aggregate_verdict"] in [
            "CYBER_PHYSICAL_ASSIMILATION_VALIDATED",
            "CYBER_PHYSICAL_SAFE_BUT_PASSIVE",
            "CYBER_PHYSICAL_INSUFFICIENT_EVIDENCE",
            "UNSAFE_EXTERNAL_SIGNAL_ROUTED",
        ]

    def test_t60_does_not_apply_architecture_patch(self, orchestrator):
        assert orchestrator.architecture_patch_execution_enabled is False

    def test_t60_does_not_enable_self_improvement(self, orchestrator):
        assert orchestrator.self_improvement_enabled is False

    def test_t60_does_not_connect_to_real_iot(self, orchestrator):
        # No real IoT connections should exist
        gateway = orchestrator.get_cyber_physical_gateway()
        # Gateway is purely in-memory
        assert hasattr(gateway, "assimilate_signal")
        assert hasattr(gateway, "publish_world_state_to_bus")

    def test_benchmark_metrics_t60_present(self, orchestrator):
        from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import (
            BenchmarkMetrics,
        )
        metrics = BenchmarkMetrics()
        assert hasattr(metrics, "cyber_physical_audit_count")
        assert hasattr(metrics, "external_signal_count")
        assert hasattr(metrics, "actuation_request_blocked_count")
        assert hasattr(metrics, "read_only_integrity_score")
        assert hasattr(metrics, "cyber_physical_score")
        assert hasattr(metrics, "proceed_to_t60b_score")

    def test_morphological_events_recorded(self, orchestrator):
        from speace_core.cellular_brain.memory.morphology_events import (
            MorphologyEventType,
        )
        assert hasattr(
            MorphologyEventType, "CYBER_PHYSICAL_ASSIMILATION_STARTED"
        )
        assert hasattr(
            MorphologyEventType, "CYBER_PHYSICAL_SIGNAL_ACCEPTED"
        )
        assert hasattr(
            MorphologyEventType, "CYBER_PHYSICAL_ACTUATION_REQUEST_BLOCKED"
        )
        assert hasattr(
            MorphologyEventType, "CYBER_PHYSICAL_AUDIT_COMPLETED"
        )

    def test_audit_result_stored_on_orchestrator(self, orchestrator):
        import asyncio
        orchestrator.cyber_physical_assimilation_enabled = True
        asyncio.run(orchestrator.run_cyber_physical_audit())
        assert orchestrator._last_cyber_physical_audit_result is not None
        assert "aggregate_verdict" in orchestrator._last_cyber_physical_audit_result
