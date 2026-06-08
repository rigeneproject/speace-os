import copy
import json
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import (
    BenchmarkResult,
    NeuroFunctionalBenchmark,
)
from speace_core.cellular_brain.evolution.evolution_engine import EvolutionEngine
from speace_core.cellular_brain.evolution.genome_database import (
    GenomeDatabase,
    GenomeRecord,
)
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.dna.models import SharedGenome
from speace_core.dna.parser import load_genome
from speace_core.orchestrator import CellularBrainOrchestrator


class AuditConfiguration(BaseModel):
    name: str
    execution_mode: str = "global_tick"
    stdp_enabled: bool = False
    inhibition_enabled: bool = False
    energy_control_enabled: bool = False
    community_detection_enabled: bool = False
    confidence_enabled: bool = False
    inter_region_plasticity_enabled: bool = False
    evolution_enabled: bool = False
    n_adaptive_cycles: int = 5
    benchmark_case: str = "morphological_memory_trace"


class AuditCaseResult(BaseModel):
    configuration: AuditConfiguration
    benchmark_metrics: Dict[str, Any] = Field(default_factory=dict)
    fitness_score: Optional[float] = None
    best_genome_id: Optional[str] = None
    test_passed: bool = True
    failure_reason: Optional[str] = None


class IntegratedAuditSummary(BaseModel):
    baseline_name: str = ""
    best_configuration: Optional[str] = None
    best_cognitive_score: Optional[float] = None
    best_fitness_score: Optional[float] = None
    cognitive_score_delta: float = 0.0
    phi_delta: float = 0.0
    energy_efficiency_delta: float = 0.0
    modularity_delta: float = 0.0
    confidence_delta: float = 0.0
    stability_delta: float = 0.0
    verdict: str = "insufficient_evidence"


class IntegratedAuditReport(BaseModel):
    audit_id: str
    created_at: str
    configurations: List[AuditConfiguration]
    results: List[AuditCaseResult]
    summary: IntegratedAuditSummary
    json_report_path: Optional[str] = None
    markdown_report_path: Optional[str] = None


class IntegratedNeurocellularAudit:
    """Reproducible audit that validates SPEACE T7-T19 as an integrated organism."""

    def __init__(
        self,
        genome: Optional[Dict[str, Any]] = None,
        report_dir: str = "reports/audit",
        seed: int = 42,
        evolution_db_path: str = "data/evolution",
    ):
        self._seed = seed
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.evolution_db_path = evolution_db_path

        if genome is not None:
            self.genome = genome
        else:
            loaded = load_genome("speace_core/dna/genome/default_genome.yaml")
            self.genome = loaded.model_dump()

    # ------------------------------------------------------------------ #
    # Configuration presets
    # ------------------------------------------------------------------ #

    @staticmethod
    def default_configurations() -> List[AuditConfiguration]:
        return [
            AuditConfiguration(
                name="baseline_global_tick",
                execution_mode="global_tick",
            ),
            AuditConfiguration(
                name="burst_only",
                execution_mode="event_driven_burst",
            ),
            AuditConfiguration(
                name="burst_stdp",
                execution_mode="event_driven_burst",
                stdp_enabled=True,
            ),
            AuditConfiguration(
                name="burst_stdp_inhibition",
                execution_mode="event_driven_burst",
                stdp_enabled=True,
                inhibition_enabled=True,
            ),
            AuditConfiguration(
                name="burst_stdp_inhibition_energy",
                execution_mode="event_driven_burst",
                stdp_enabled=True,
                inhibition_enabled=True,
                energy_control_enabled=True,
            ),
            AuditConfiguration(
                name="burst_stdp_inhibition_energy_community",
                execution_mode="event_driven_burst",
                stdp_enabled=True,
                inhibition_enabled=True,
                energy_control_enabled=True,
                community_detection_enabled=True,
            ),
            AuditConfiguration(
                name="full_organism_with_confidence_and_evolution",
                execution_mode="event_driven_burst",
                stdp_enabled=True,
                inhibition_enabled=True,
                energy_control_enabled=True,
                community_detection_enabled=True,
                confidence_enabled=True,
                inter_region_plasticity_enabled=True,
                evolution_enabled=True,
            ),
        ]

    # ------------------------------------------------------------------ #
    # Orchestrator factory
    # ------------------------------------------------------------------ #

    def build_orchestrator_for_config(
        self, config: AuditConfiguration
    ) -> CellularBrainOrchestrator:
        random.seed(self._seed)
        genome = SharedGenome(**self.genome)
        orch = CellularBrainOrchestrator.build_mvp(genome)
        orch.execution_mode = config.execution_mode
        orch.stdp_enabled = config.stdp_enabled
        orch.inhibition_enabled = config.inhibition_enabled
        orch.energy_control_enabled = config.energy_control_enabled
        orch.community_detection_enabled = config.community_detection_enabled
        orch.confidence_enabled = config.confidence_enabled
        orch.inter_region_plasticity_enabled = config.inter_region_plasticity_enabled
        return orch

    # ------------------------------------------------------------------ #
    # Single configuration run
    # ------------------------------------------------------------------ #

    async def run_configuration(self, config: AuditConfiguration) -> AuditCaseResult:
        orch = self.build_orchestrator_for_config(config)
        benchmark = NeuroFunctionalBenchmark(orch)
        pattern = [1.0 if i % 2 == 0 else 0.0 for i in range(10)]

        try:
            result = await benchmark.run_case(
                config.benchmark_case,
                execution_mode=config.execution_mode,
                stdp_enabled=config.stdp_enabled,
                inhibition_enabled=config.inhibition_enabled,
                energy_control_enabled=config.energy_control_enabled,
                community_detection_enabled=config.community_detection_enabled,
                confidence_enabled=config.confidence_enabled,
                inter_region_plasticity_enabled=config.inter_region_plasticity_enabled,
                input_pattern=pattern,
                target_output=pattern,
                n_ticks=config.n_adaptive_cycles,
            )
        except Exception as exc:
            return AuditCaseResult(
                configuration=config,
                benchmark_metrics={},
                fitness_score=None,
                test_passed=False,
                failure_reason=str(exc),
            )

        metrics_dict = result.metrics.model_dump()

        # Supplement with event counts from memory
        mem = orch.memory
        stdp_events = mem.count_events(
            MorphologyEventType.SYNAPSE_REINFORCED
        ) + mem.count_events(MorphologyEventType.SYNAPSE_WEAKENED)
        energy_events = mem.count_events(MorphologyEventType.ENERGY_CHANGED)
        confidence_events = mem.count_events(MorphologyEventType.CONFIDENCE_EVALUATED)

        metrics_dict["stdp_events"] = stdp_events
        metrics_dict["energy_events"] = energy_events
        metrics_dict["confidence_events"] = confidence_events

        fitness_score = None
        best_genome_id = None

        if config.evolution_enabled:
            fitness_score, best_genome_id = await self._run_evolution_micro_run(
                config, result, mem
            )

        return AuditCaseResult(
            configuration=config,
            benchmark_metrics=metrics_dict,
            fitness_score=fitness_score,
            best_genome_id=best_genome_id,
            test_passed=True,
            failure_reason=None,
        )

    async def _run_evolution_micro_run(
        self,
        config: AuditConfiguration,
        baseline_result: BenchmarkResult,
        memory: Any,
    ) -> tuple[Optional[float], Optional[str]]:
        """Run a minimal evolution cycle: mutate, evaluate, select."""
        db = GenomeDatabase(base_path=self.evolution_db_path)
        evo = EvolutionEngine(db)

        # Save initial genome with baseline fitness
        initial_record = GenomeRecord(
            genome_id=f"gen_audit_{uuid.uuid4().hex[:8]}",
            generation=0,
            genome=copy.deepcopy(self.genome),
            created_at=datetime.now(timezone.utc).isoformat(),
            benchmark_case=config.benchmark_case,
        )
        db.save_genome(initial_record)

        baseline_fitness = evo.compute_fitness(baseline_result)
        initial_record.fitness_score = baseline_fitness.fitness_score
        initial_record.metrics = baseline_fitness.raw_metrics
        db.save_genome(initial_record)

        # Create 3 mutated candidates
        candidates = evo.create_candidate_generation(
            [initial_record],
            n_candidates=3,
            generation=1,
            benchmark_case=config.benchmark_case,
            memory=memory,
        )

        # Evaluate each candidate
        benchmark_results: Dict[str, BenchmarkResult] = {}
        for cand in candidates:
            try:
                cand_result = await evo.evaluate_genome(
                    cand, benchmark_case=config.benchmark_case, n_ticks=3
                )
                benchmark_results[cand.genome_id] = cand_result
            except Exception:
                continue

        # Select best
        run_record = evo.run_evolution_step(
            [initial_record],
            benchmark_results=benchmark_results,
            generation=1,
            candidate_records=candidates,
        )

        return run_record.best_fitness, run_record.best_genome_id

    # ------------------------------------------------------------------ #
    # Full audit run
    # ------------------------------------------------------------------ #

    async def run_all(
        self, configurations: Optional[List[AuditConfiguration]] = None
    ) -> IntegratedAuditReport:
        configs = configurations or self.default_configurations()
        results: List[AuditCaseResult] = []

        for config in configs:
            result = await self.run_configuration(config)
            results.append(result)

        summary = self.compute_summary(results)

        report = IntegratedAuditReport(
            audit_id=f"audit_{uuid.uuid4().hex[:8]}",
            created_at=datetime.now(timezone.utc).isoformat(),
            configurations=configs,
            results=results,
            summary=summary,
        )

        json_path = self.generate_json_report(report)
        md_path = self.generate_markdown_report(report)
        report.json_report_path = str(json_path)
        report.markdown_report_path = str(md_path)

        return report

    # ------------------------------------------------------------------ #
    # Summary & verdict
    # ------------------------------------------------------------------ #

    @staticmethod
    def compute_summary(results: List[AuditCaseResult]) -> IntegratedAuditSummary:
        if not results:
            return IntegratedAuditSummary(verdict="insufficient_evidence")

        baseline = results[0]
        full = results[-1]

        summary = IntegratedAuditSummary(
            baseline_name=baseline.configuration.name,
        )

        # Best configuration by cognitive score
        passed = [r for r in results if r.test_passed]
        if passed:
            best = max(
                passed,
                key=lambda r: r.benchmark_metrics.get("speace_cognitive_score", 0.0),
            )
            summary.best_configuration = best.configuration.name
            summary.best_cognitive_score = best.benchmark_metrics.get(
                "speace_cognitive_score", 0.0
            )

        # Best fitness among evolution-enabled configs
        evo_passed = [r for r in passed if r.fitness_score is not None]
        if evo_passed:
            best_fit = max(evo_passed, key=lambda r: r.fitness_score or 0.0)
            summary.best_fitness_score = best_fit.fitness_score

        # Deltas (full vs baseline)
        if baseline.test_passed and full.test_passed:
            b = baseline.benchmark_metrics
            f = full.benchmark_metrics

            summary.cognitive_score_delta = f.get(
                "speace_cognitive_score", 0.0
            ) - b.get("speace_cognitive_score", 0.0)
            summary.phi_delta = f.get("coherence_phi", 0.0) - b.get("coherence_phi", 0.0)
            summary.energy_efficiency_delta = f.get(
                "energy_efficiency", 0.0
            ) - b.get("energy_efficiency", 0.0)
            summary.modularity_delta = f.get("modularity_proxy", 0.0) - b.get(
                "modularity_proxy", 0.0
            )
            summary.confidence_delta = f.get("confidence_score", 0.0) - b.get(
                "confidence_score", 0.0
            )
            summary.stability_delta = f.get("morphological_stability", 0.0) - b.get(
                "morphological_stability", 0.0
            )

            summary.verdict = IntegratedNeurocellularAudit._compute_verdict(
                baseline, full
            )

        return summary

    @staticmethod
    def _compute_verdict(
        baseline: AuditCaseResult, full: AuditCaseResult
    ) -> str:
        if not baseline.test_passed or not full.test_passed:
            return "insufficient_evidence"

        b = baseline.benchmark_metrics
        f = full.benchmark_metrics

        b_cognitive = b.get("speace_cognitive_score", 0.0)
        f_cognitive = f.get("speace_cognitive_score", 0.0)
        b_phi = b.get("coherence_phi", 0.0)
        f_phi = f.get("coherence_phi", 0.0)
        f_energy = f.get("mean_energy")

        # Unstable: collapse or severe cognitive drop
        if (
            f_phi < 0.05
            or (f_energy is not None and f_energy < 0.05)
            or f_cognitive < b_cognitive * 0.5
        ):
            return "unstable"

        # Regression detected
        if f_cognitive < b_cognitive and f_phi < b_phi:
            return "regression_detected"

        # Validated: improvement or maintenance + required features available
        has_confidence = f.get("confidence_score", 0.0) > 0.0
        has_modularity = f.get("modularity_proxy", 0.0) > 0.0
        has_fitness = full.fitness_score is not None

        if (
            f_cognitive >= b_cognitive
            and f_phi >= 0.1
            and has_confidence
            and has_modularity
            and has_fitness
        ):
            return "validated"

        # Partially validated: at least 2 metric improvements, no collapse
        improvements = 0
        keys = [
            "speace_cognitive_score",
            "meta_cognitive_score",
            "coherence_phi",
            "energy_efficiency",
            "modularity_proxy",
            "structural_complexity",
            "functional_improvement",
        ]
        for key in keys:
            if f.get(key, 0.0) > b.get(key, 0.0):
                improvements += 1

        if improvements >= 2:
            return "partially_validated"

        return "insufficient_evidence"

    # ------------------------------------------------------------------ #
    # Report generation
    # ------------------------------------------------------------------ #

    def generate_json_report(self, report: IntegratedAuditReport) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"integrated_audit_{timestamp}.json"
        path = self.report_dir / filename
        path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        return path

    def generate_markdown_report(self, report: IntegratedAuditReport) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"integrated_audit_{timestamp}.md"
        path = self.report_dir / filename

        lines: List[str] = [
            "# SPEACE Integrated Neurocellular Evolution Audit Report",
            "",
            f"**Audit ID:** {report.audit_id}",
            f"**Date:** {report.created_at}",
            f"**Configurations tested:** {len(report.configurations)}",
            "",
            "## Comparative Results",
            "",
            "| Configuration | Cognitive Score | Φ | Energy Eff. | Modularity | Confidence | Fitness | Passed |",
            "|---|---|---|---|---|---|---|---|",
        ]

        for result in report.results:
            cfg = result.configuration
            m = result.benchmark_metrics
            lines.append(
                f"| {cfg.name} | "
                f"{m.get('speace_cognitive_score', 0.0):.4f} | "
                f"{m.get('coherence_phi', 0.0):.4f} | "
                f"{m.get('energy_efficiency', 0.0):.4f} | "
                f"{m.get('modularity_proxy', 0.0):.4f} | "
                f"{m.get('confidence_score', 0.0):.4f} | "
                f"{result.fitness_score if result.fitness_score is not None else '—'} | "
                f"{'✅' if result.test_passed else '❌'} |"
            )

        lines.extend([
            "",
            "## Incremental Effects",
            "",
        ])

        for i in range(1, len(report.results)):
            prev = report.results[i - 1]
            curr = report.results[i]
            p = prev.benchmark_metrics
            c = curr.benchmark_metrics
            name = curr.configuration.name
            lines.extend([
                f"### {prev.configuration.name} → {name}",
                "",
                f"- Cognitive Δ: {c.get('speace_cognitive_score', 0.0) - p.get('speace_cognitive_score', 0.0):+.4f}",
                f"- Φ Δ: {c.get('coherence_phi', 0.0) - p.get('coherence_phi', 0.0):+.4f}",
                f"- Energy Efficiency Δ: {c.get('energy_efficiency', 0.0) - p.get('energy_efficiency', 0.0):+.4f}",
                f"- Modularity Δ: {c.get('modularity_proxy', 0.0) - p.get('modularity_proxy', 0.0):+.4f}",
                f"- Confidence Δ: {c.get('confidence_score', 0.0) - p.get('confidence_score', 0.0):+.4f}",
                f"- Stability Δ: {c.get('morphological_stability', 0.0) - p.get('morphological_stability', 0.0):+.4f}",
                "",
            ])

        s = report.summary
        lines.extend([
            "## Summary",
            "",
            f"- **Baseline:** {s.baseline_name}",
            f"- **Best configuration:** {s.best_configuration or '—'}",
            f"- **Best cognitive score:** {s.best_cognitive_score if s.best_cognitive_score is not None else '—'}",
            f"- **Best fitness score:** {s.best_fitness_score if s.best_fitness_score is not None else '—'}",
            "",
            "### Deltas (full organism vs baseline)",
            "",
            f"- Cognitive score Δ: {s.cognitive_score_delta:+.4f}",
            f"- Φ Δ: {s.phi_delta:+.4f}",
            f"- Energy efficiency Δ: {s.energy_efficiency_delta:+.4f}",
            f"- Modularity Δ: {s.modularity_delta:+.4f}",
            f"- Confidence Δ: {s.confidence_delta:+.4f}",
            f"- Stability Δ: {s.stability_delta:+.4f}",
            "",
            f"## Verdict: {s.verdict.upper()}",
            "",
            "---",
            "*Generated by IntegratedNeurocellularAudit v0.3*",
        ])

        path.write_text("\n".join(lines), encoding="utf-8")
        return path
