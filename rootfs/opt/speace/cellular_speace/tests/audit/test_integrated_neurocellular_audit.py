import os
import tempfile

import pytest

from speace_core.cellular_brain.audit.integrated_neurocellular_audit import (
    AuditCaseResult,
    AuditConfiguration,
    IntegratedAuditReport,
    IntegratedAuditSummary,
    IntegratedNeurocellularAudit,
)
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.dna.parser import load_genome


@pytest.fixture
def audit():
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    return IntegratedNeurocellularAudit(
        genome=genome.model_dump(),
        seed=42,
        evolution_db_path=tempfile.mkdtemp(),
    )


@pytest.fixture
def fast_config():
    return AuditConfiguration(
        name="fast_test",
        execution_mode="event_driven_burst",
        stdp_enabled=True,
        inhibition_enabled=True,
        energy_control_enabled=True,
        community_detection_enabled=True,
        confidence_enabled=True,
        n_adaptive_cycles=2,
        benchmark_case="morphological_memory_trace",
    )


# ---------------------------------------------------------------------------
# Import & structure
# ---------------------------------------------------------------------------

def test_audit_importable():
    assert IntegratedNeurocellularAudit is not None
    assert AuditConfiguration is not None
    assert AuditCaseResult is not None
    assert IntegratedAuditSummary is not None
    assert IntegratedAuditReport is not None


def test_default_configurations_count():
    configs = IntegratedNeurocellularAudit.default_configurations()
    assert len(configs) >= 6
    names = {c.name for c in configs}
    assert "baseline_global_tick" in names
    assert "full_organism_with_confidence_and_evolution" in names


# ---------------------------------------------------------------------------
# Orchestrator builder
# ---------------------------------------------------------------------------

def test_build_orchestrator_applies_flags(audit):
    config = AuditConfiguration(
        name="test_flags",
        execution_mode="event_driven_burst",
        stdp_enabled=True,
        inhibition_enabled=False,
        energy_control_enabled=True,
        community_detection_enabled=False,
        confidence_enabled=True,
    )
    orch = audit.build_orchestrator_for_config(config)
    assert orch.execution_mode == "event_driven_burst"
    assert orch.stdp_enabled is True
    assert orch.inhibition_enabled is False
    assert orch.energy_control_enabled is True
    assert orch.community_detection_enabled is False
    assert orch.confidence_enabled is True


# ---------------------------------------------------------------------------
# Single configuration run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_configuration_produces_result(audit, fast_config):
    result = await audit.run_configuration(fast_config)
    assert isinstance(result, AuditCaseResult)
    assert result.test_passed is True
    assert result.failure_reason is None
    assert "speace_cognitive_score" in result.benchmark_metrics


@pytest.mark.asyncio
async def test_run_configuration_full_organism_includes_confidence(audit):
    config = AuditConfiguration(
        name="full",
        execution_mode="event_driven_burst",
        stdp_enabled=True,
        inhibition_enabled=True,
        energy_control_enabled=True,
        community_detection_enabled=True,
        confidence_enabled=True,
        n_adaptive_cycles=2,
        benchmark_case="morphological_memory_trace",
    )
    result = await audit.run_configuration(config)
    assert result.test_passed is True
    assert result.benchmark_metrics.get("confidence_score", 0.0) >= 0.0
    assert result.benchmark_metrics.get("uncertainty_score", 0.0) >= 0.0
    assert result.benchmark_metrics.get("error_risk", 0.0) >= 0.0
    assert result.benchmark_metrics.get("meta_cognitive_score", 0.0) >= 0.0


@pytest.mark.asyncio
async def test_run_configuration_full_organism_includes_community(audit):
    config = AuditConfiguration(
        name="full_community",
        execution_mode="event_driven_burst",
        stdp_enabled=True,
        inhibition_enabled=True,
        energy_control_enabled=True,
        community_detection_enabled=True,
        confidence_enabled=True,
        n_adaptive_cycles=2,
        benchmark_case="morphological_memory_trace",
    )
    result = await audit.run_configuration(config)
    assert result.test_passed is True
    assert result.benchmark_metrics.get("community_count", 0) >= 0
    assert result.benchmark_metrics.get("modularity_proxy", 0.0) >= 0.0


@pytest.mark.asyncio
async def test_run_configuration_evolution_produces_fitness(audit):
    config = AuditConfiguration(
        name="evo_test",
        execution_mode="event_driven_burst",
        stdp_enabled=True,
        inhibition_enabled=True,
        energy_control_enabled=True,
        community_detection_enabled=True,
        confidence_enabled=True,
        evolution_enabled=True,
        n_adaptive_cycles=2,
        benchmark_case="morphological_memory_trace",
    )
    result = await audit.run_configuration(config)
    assert result.test_passed is True
    assert result.fitness_score is not None
    assert result.best_genome_id is not None


# ---------------------------------------------------------------------------
# Full audit run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_all_produces_report(audit):
    configs = [
        AuditConfiguration(name="c1", execution_mode="global_tick", n_adaptive_cycles=2),
        AuditConfiguration(
            name="c2",
            execution_mode="event_driven_burst",
            stdp_enabled=True,
            n_adaptive_cycles=2,
        ),
    ]
    report = await audit.run_all(configurations=configs)
    assert isinstance(report, IntegratedAuditReport)
    assert report.audit_id is not None
    assert len(report.results) == 2
    assert report.summary is not None


@pytest.mark.asyncio
async def test_run_all_summary_has_best_configuration(audit):
    configs = [
        AuditConfiguration(name="c1", execution_mode="global_tick", n_adaptive_cycles=2),
        AuditConfiguration(
            name="c2",
            execution_mode="event_driven_burst",
            stdp_enabled=True,
            n_adaptive_cycles=2,
        ),
    ]
    report = await audit.run_all(configurations=configs)
    assert report.summary.best_configuration in {"c1", "c2"}


@pytest.mark.asyncio
async def test_verdict_is_allowed_value(audit):
    configs = [
        AuditConfiguration(name="c1", execution_mode="global_tick", n_adaptive_cycles=2),
        AuditConfiguration(
            name="c2",
            execution_mode="event_driven_burst",
            stdp_enabled=True,
            n_adaptive_cycles=2,
        ),
    ]
    report = await audit.run_all(configurations=configs)
    assert report.summary.verdict in {
        "validated",
        "partially_validated",
        "unstable",
        "regression_detected",
        "insufficient_evidence",
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_json_report_generated(audit):
    configs = [
        AuditConfiguration(name="c1", execution_mode="global_tick", n_adaptive_cycles=2),
    ]
    report = await audit.run_all(configurations=configs)
    assert report.json_report_path is not None
    assert os.path.exists(report.json_report_path)


@pytest.mark.asyncio
async def test_markdown_report_contains_table(audit):
    configs = [
        AuditConfiguration(name="c1", execution_mode="global_tick", n_adaptive_cycles=2),
        AuditConfiguration(
            name="c2",
            execution_mode="event_driven_burst",
            stdp_enabled=True,
            n_adaptive_cycles=2,
        ),
    ]
    report = await audit.run_all(configurations=configs)
    assert report.markdown_report_path is not None
    assert os.path.exists(report.markdown_report_path)
    md_text = open(report.markdown_report_path, encoding="utf-8").read()
    assert "## Comparative Results" in md_text
    assert "| Configuration |" in md_text
    assert "## Incremental Effects" in md_text
    assert "## Verdict:" in md_text


# ---------------------------------------------------------------------------
# Verdict logic unit tests
# ---------------------------------------------------------------------------

def test_verdict_insufficient_evidence_on_failure():
    baseline = AuditCaseResult(
        configuration=AuditConfiguration(name="b"),
        benchmark_metrics={"speace_cognitive_score": 0.5, "coherence_phi": 0.5},
        test_passed=True,
    )
    full = AuditCaseResult(
        configuration=AuditConfiguration(name="f"),
        benchmark_metrics={"speace_cognitive_score": 0.5, "coherence_phi": 0.5},
        test_passed=False,
    )
    assert IntegratedNeurocellularAudit._compute_verdict(baseline, full) == "insufficient_evidence"


def test_verdict_unstable_phi_collapse():
    baseline = AuditCaseResult(
        configuration=AuditConfiguration(name="b"),
        benchmark_metrics={"speace_cognitive_score": 0.5, "coherence_phi": 0.5},
        test_passed=True,
    )
    full = AuditCaseResult(
        configuration=AuditConfiguration(name="f"),
        benchmark_metrics={"speace_cognitive_score": 0.5, "coherence_phi": 0.01},
        test_passed=True,
    )
    assert IntegratedNeurocellularAudit._compute_verdict(baseline, full) == "unstable"


def test_verdict_regression_detected():
    baseline = AuditCaseResult(
        configuration=AuditConfiguration(name="b"),
        benchmark_metrics={"speace_cognitive_score": 0.6, "coherence_phi": 0.6},
        test_passed=True,
    )
    full = AuditCaseResult(
        configuration=AuditConfiguration(name="f"),
        benchmark_metrics={"speace_cognitive_score": 0.3, "coherence_phi": 0.3},
        test_passed=True,
    )
    assert IntegratedNeurocellularAudit._compute_verdict(baseline, full) == "regression_detected"


def test_verdict_validated():
    baseline = AuditCaseResult(
        configuration=AuditConfiguration(name="b"),
        benchmark_metrics={"speace_cognitive_score": 0.5, "coherence_phi": 0.5},
        test_passed=True,
    )
    full = AuditCaseResult(
        configuration=AuditConfiguration(name="f"),
        benchmark_metrics={
            "speace_cognitive_score": 0.6,
            "coherence_phi": 0.6,
            "confidence_score": 0.3,
            "modularity_proxy": 0.2,
        },
        test_passed=True,
        fitness_score=0.5,
    )
    assert IntegratedNeurocellularAudit._compute_verdict(baseline, full) == "validated"


def test_verdict_partially_validated():
    baseline = AuditCaseResult(
        configuration=AuditConfiguration(name="b"),
        benchmark_metrics={
            "speace_cognitive_score": 0.5,
            "coherence_phi": 0.5,
            "energy_efficiency": 0.5,
            "modularity_proxy": 0.1,
        },
        test_passed=True,
    )
    full = AuditCaseResult(
        configuration=AuditConfiguration(name="f"),
        benchmark_metrics={
            "speace_cognitive_score": 0.5,
            "coherence_phi": 0.5,
            "energy_efficiency": 0.7,
            "modularity_proxy": 0.3,
            "confidence_score": 0.0,
        },
        test_passed=True,
    )
    assert IntegratedNeurocellularAudit._compute_verdict(baseline, full) == "partially_validated"
