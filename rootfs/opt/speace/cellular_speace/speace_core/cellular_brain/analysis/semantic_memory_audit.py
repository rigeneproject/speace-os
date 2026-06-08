import copy
import json
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.memory.semantic.cell_assembly import SemanticMemoryMetrics
from speace_core.dna.models import SharedGenome
from speace_core.dna.parser import load_genome
from speace_core.orchestrator import CellularBrainOrchestrator


class SemanticMemoryAuditProfile(BaseModel):
    """Configuration for a single semantic memory audit profile."""

    profile_id: str
    name: str
    semantic_memory_enabled: bool = False
    recall_enabled: bool = False
    consolidation_enabled: bool = False
    decay_enabled: bool = False
    reactivation_enabled: bool = False
    repeated_pattern_count: int = 5
    novel_pattern_count: int = 3
    recall_trials: int = 5
    n_cycles: int = 20
    description: str = ""

    model_config = ConfigDict(extra="allow")


class SemanticMemoryAuditMetrics(BaseModel):
    """Metrics extracted for a single profile run."""

    cognitive_score: float = 0.0
    coherence_phi: float = 0.0
    energy_efficiency: float = 0.0
    semantic_assembly_count: int = 0
    semantic_active_assembly_count: int = 0
    semantic_consolidated_assembly_count: int = 0
    mean_assembly_strength: float = 0.0
    mean_assembly_stability: float = 0.0
    semantic_recall_success_rate: float = 0.0
    semantic_memory_density: float = 0.0
    semantic_memory_utility: float = 0.0
    semantic_consolidation_rate: float = 0.0
    semantic_memory_score: float = 0.0
    assembly_creation_events: int = 0
    assembly_reinforcement_events: int = 0
    assembly_consolidation_events: int = 0
    assembly_decay_events: int = 0
    semantic_recall_success_events: int = 0
    semantic_recall_failure_events: int = 0
    reactivation_events: int = 0
    cognitive_delta_vs_baseline: float = 0.0
    phi_delta_vs_baseline: float = 0.0
    energy_delta_vs_baseline: float = 0.0
    semantic_net_gain: float = 0.0


class SemanticMemoryAuditResult(BaseModel):
    """Result of running one profile."""

    profile: SemanticMemoryAuditProfile
    metrics: SemanticMemoryAuditMetrics = Field(default_factory=SemanticMemoryAuditMetrics)
    passed: bool = True


class SemanticMemoryAuditSuiteResult(BaseModel):
    """Top-level audit report container."""

    audit_id: str
    created_at: str
    baseline_result: SemanticMemoryAuditResult = Field(
        default_factory=lambda: SemanticMemoryAuditResult(
            profile=SemanticMemoryAuditProfile(profile_id="baseline", name="baseline")
        )
    )
    profile_results: List[SemanticMemoryAuditResult] = Field(default_factory=list)
    best_profile: Optional[str] = None
    verdict: str = "INSUFFICIENT_EVIDENCE"
    semantic_net_gain: float = 0.0
    json_report_path: Optional[str] = None
    markdown_report_path: Optional[str] = None


class SemanticMemoryAuditor:
    """T43B — Validate the functional impact of T43 Semantic Cell Assembly Memory."""

    def __init__(
        self,
        genome: Optional[Dict[str, Any]] = None,
        report_dir: str = "reports/semantic_memory_audit",
        seed: int = 42,
    ):
        self._seed = seed
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)

        if genome is not None:
            self.genome = genome
        else:
            loaded = load_genome("speace_core/dna/genome/default_genome.yaml")
            self.genome = loaded.model_dump()

    # ------------------------------------------------------------------ #
    # Profile presets
    # ------------------------------------------------------------------ #

    @staticmethod
    def default_profiles() -> List[SemanticMemoryAuditProfile]:
        return [
            SemanticMemoryAuditProfile(
                profile_id="sm0",
                name="semantic_memory_off",
                description="T43 completely disabled",
            ),
            SemanticMemoryAuditProfile(
                profile_id="sm1",
                name="semantic_memory_observe_only",
                semantic_memory_enabled=True,
                description="Only observe activation traces",
            ),
            SemanticMemoryAuditProfile(
                profile_id="sm2",
                name="semantic_memory_create_only",
                semantic_memory_enabled=True,
                description="Create assemblies but no reinforcement",
            ),
            SemanticMemoryAuditProfile(
                profile_id="sm3",
                name="semantic_memory_create_reinforce",
                semantic_memory_enabled=True,
                description="Create and reinforce assemblies",
            ),
            SemanticMemoryAuditProfile(
                profile_id="sm4",
                name="semantic_memory_full_cycle",
                semantic_memory_enabled=True,
                consolidation_enabled=True,
                decay_enabled=True,
                description="Full semantic memory cycle",
            ),
            SemanticMemoryAuditProfile(
                profile_id="sm5",
                name="semantic_memory_recall_enabled",
                semantic_memory_enabled=True,
                consolidation_enabled=True,
                decay_enabled=True,
                recall_enabled=True,
                description="Full cycle + recall",
            ),
            SemanticMemoryAuditProfile(
                profile_id="sm6",
                name="semantic_memory_consolidation_enabled",
                semantic_memory_enabled=True,
                consolidation_enabled=True,
                description="Full cycle with consolidation",
            ),
            SemanticMemoryAuditProfile(
                profile_id="sm7",
                name="semantic_memory_decay_enabled",
                semantic_memory_enabled=True,
                decay_enabled=True,
                description="Full cycle with decay",
            ),
            SemanticMemoryAuditProfile(
                profile_id="sm8",
                name="semantic_memory_reactivation_enabled",
                semantic_memory_enabled=True,
                consolidation_enabled=True,
                decay_enabled=True,
                reactivation_enabled=True,
                description="Full cycle + reactivation",
            ),
            SemanticMemoryAuditProfile(
                profile_id="sm9",
                name="semantic_memory_full_stack",
                semantic_memory_enabled=True,
                consolidation_enabled=True,
                decay_enabled=True,
                recall_enabled=True,
                reactivation_enabled=True,
                description="Complete T43 stack",
            ),
        ]

    # ------------------------------------------------------------------ #
    # Orchestrator factory
    # ------------------------------------------------------------------ #

    def _build_orchestrator(self) -> CellularBrainOrchestrator:
        random.seed(self._seed)
        genome = SharedGenome(**copy.deepcopy(self.genome))
        orch = CellularBrainOrchestrator.build_mvp(genome)
        return orch

    @staticmethod
    def _apply_profile(
        orch: CellularBrainOrchestrator, profile: SemanticMemoryAuditProfile
    ) -> None:
        orch.semantic_memory_enabled = profile.semantic_memory_enabled
        orch.model_post_init(None)
        if orch.semantic_memory_enabled and orch._cell_assembly_engine is not None:
            # Lower thresholds so MVP circuit reliably creates assemblies
            orch._cell_assembly_engine.min_mean_activation = 0.05
            orch._cell_assembly_engine.min_neurons = 2
            orch._cell_assembly_engine.min_phi = 0.0
            orch._cell_assembly_engine.min_confidence = 0.0

    # ------------------------------------------------------------------ #
    # Pattern helpers
    # ------------------------------------------------------------------ #

    def _get_repeated_pattern(self, index: int) -> List[float]:
        rng = random.Random(self._seed + index)
        return [round(rng.random(), 4) for _ in range(10)]

    def _get_novel_pattern(self, index: int) -> List[float]:
        rng = random.Random(self._seed + 1000 + index)
        return [round(rng.random(), 4) for _ in range(10)]

    def _default_pattern(self) -> List[float]:
        return [1.0 if i % 2 == 0 else 0.0 for i in range(10)]

    # ------------------------------------------------------------------ #
    # Semantic cycle helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _run_semantic_cycle(
        orch: CellularBrainOrchestrator, profile: SemanticMemoryAuditProfile
    ) -> None:
        engine = orch._cell_assembly_engine
        store = orch._semantic_memory_store
        if engine is None or store is None:
            return

        if profile.name == "semantic_memory_observe_only":
            engine.observe_activation(orch)
            return

        trace = engine.observe_activation(orch)

        if profile.name == "semantic_memory_create_only":
            candidate = engine.detect_candidate_assembly(trace)
            if candidate is not None:
                store.save(candidate)
            return

        # create_reinforce, full_cycle, recall, consolidation, decay, reactivation, full_stack
        matched = engine.match_existing_assembly(trace)
        if matched is not None:
            engine.reinforce_assembly(matched, trace)
            if orch.memory is not None:
                orch.memory.create_event(
                    event_type=MorphologyEventType.CELL_ASSEMBLY_REINFORCED,
                    source_id="audit",
                    target_id=matched.assembly_id,
                )
        else:
            candidate = engine.detect_candidate_assembly(trace)
            if candidate is not None:
                store.save(candidate)
                if orch.memory is not None:
                    orch.memory.create_event(
                        event_type=MorphologyEventType.CELL_ASSEMBLY_CREATED,
                        source_id="audit",
                        target_id=candidate.assembly_id,
                    )

        if profile.decay_enabled:
            engine.decay_assemblies()

        if profile.consolidation_enabled:
            engine.consolidate_assemblies()

    # ------------------------------------------------------------------ #
    # Profile runner
    # ------------------------------------------------------------------ #

    async def _run_profile(
        self, profile: SemanticMemoryAuditProfile
    ) -> SemanticMemoryAuditResult:
        orch = self._build_orchestrator()
        self._apply_profile(orch, profile)

        # Disable automatic semantic cycle in _tick so the auditor drives it manually
        if profile.semantic_memory_enabled:
            orch.semantic_memory_enabled = False

        # Build cycle schedule
        cycles: List[tuple] = []
        for i in range(profile.repeated_pattern_count):
            cycles.extend([("repeated", i), ("repeated", i)])
        for i in range(profile.novel_pattern_count):
            cycles.extend([("novel", i), ("novel", i)])
        # Pad with repeated patterns to reach n_cycles
        while len(cycles) < profile.n_cycles:
            cycles.append(("repeated", 0))
        cycles = cycles[: profile.n_cycles]

        recall_successes = 0
        recall_attempts = 0
        reactivation_count = 0

        for cycle_idx, (ptype, pidx) in enumerate(cycles):
            if ptype == "repeated":
                pattern = self._get_repeated_pattern(pidx)
            else:
                pattern = self._get_novel_pattern(pidx)

            orch.inject(pattern)
            await orch.run_ticks(1)

            if profile.semantic_memory_enabled:
                self._run_semantic_cycle(orch, profile)

            # Interleaved recall for recall-enabled profiles
            if (
                profile.recall_enabled
                and cycle_idx % max(1, profile.n_cycles // max(1, profile.recall_trials)) == 0
                and recall_attempts < profile.recall_trials
            ):
                query = self._get_repeated_pattern(recall_attempts % profile.repeated_pattern_count)
                engine = orch._semantic_recall_engine
                if engine is not None:
                    res = engine.recall(query)
                    recall_attempts += 1
                    if res is not None and res.recall_success:
                        recall_successes += 1
                        if orch.memory is not None:
                            orch.memory.create_event(
                                event_type=MorphologyEventType.SEMANTIC_RECALL_SUCCEEDED,
                                source_id="audit",
                                target_id=res.best_match_id or "",
                            )
                    else:
                        if orch.memory is not None:
                            orch.memory.create_event(
                                event_type=MorphologyEventType.SEMANTIC_RECALL_FAILED,
                                source_id="audit",
                            )

        # Post-cycle recall if not already exhausted
        if profile.recall_enabled:
            while recall_attempts < profile.recall_trials:
                query = self._get_repeated_pattern(recall_attempts % profile.repeated_pattern_count)
                engine = orch._semantic_recall_engine
                if engine is not None:
                    res = engine.recall(query)
                    recall_attempts += 1
                    if res is not None and res.recall_success:
                        recall_successes += 1
                        if orch.memory is not None:
                            orch.memory.create_event(
                                event_type=MorphologyEventType.SEMANTIC_RECALL_SUCCEEDED,
                                source_id="audit",
                                target_id=res.best_match_id or "",
                            )
                    else:
                        if orch.memory is not None:
                            orch.memory.create_event(
                                event_type=MorphologyEventType.SEMANTIC_RECALL_FAILED,
                                source_id="audit",
                            )

        # Reactivation trials
        if profile.reactivation_enabled and orch._semantic_recall_engine is not None:
            active_assemblies = (
                orch._semantic_memory_store.list_active()
                if orch._semantic_memory_store is not None
                else []
            )
            for asm in active_assemblies:
                orch._semantic_recall_engine.reactivate_assembly(asm.assembly_id, orch)
                reactivation_count += 1
                if orch.memory is not None:
                    orch.memory.create_event(
                        event_type=MorphologyEventType.CELL_ASSEMBLY_REACTIVATED,
                        source_id="audit",
                        target_id=asm.assembly_id,
                    )

        # Collect metrics
        metrics = self._collect_metrics(orch, recall_successes, recall_attempts, reactivation_count)
        result = SemanticMemoryAuditResult(profile=profile, metrics=metrics, passed=True)
        return result

    def _collect_metrics(
        self,
        orch: CellularBrainOrchestrator,
        recall_successes: int,
        recall_attempts: int,
        reactivation_count: int,
    ) -> SemanticMemoryAuditMetrics:
        # Baseline circuit metrics
        latest = orch.latest_metrics
        coherence_phi = latest.coherence_phi if latest else 0.0
        mean_energy = latest.mean_energy if latest else 0.0
        energy_efficiency = max(0.0, min(1.0, mean_energy))

        # Output-based cognitive score proxy
        outputs = orch.circuit.output_neurons
        target = self._default_pattern()[: len(outputs)]
        if target and outputs:
            clamped = [min(1.0, max(0.0, n.activation)) for n in outputs]
            mae = sum(abs(t - o) for t, o in zip(target, clamped)) / len(target)
            cognitive_score = 1.0 - mae
        else:
            cognitive_score = 0.0

        # Semantic metrics
        store = orch._semantic_memory_store
        all_assemblies = list(store._assemblies.values()) if store else []
        active_assemblies = [a for a in all_assemblies if a.active] if store else []
        consolidated_assemblies = [a for a in all_assemblies if a.consolidated] if store else []

        assembly_count = len(all_assemblies)
        active_count = len(active_assemblies)
        consolidated_count = len(consolidated_assemblies)
        mean_strength = (
            sum(a.strength for a in all_assemblies) / max(1, assembly_count)
        )
        mean_stability = (
            sum(a.stability for a in all_assemblies) / max(1, assembly_count)
        )
        density = min(1.0, assembly_count / max(1, active_count * 2))
        utility = (
            sum(a.utility_score for a in all_assemblies) / max(1, assembly_count)
        )
        consolidation_rate = consolidated_count / max(1, assembly_count)
        recall_rate = recall_successes / max(1, recall_attempts)

        # Event counts
        events = orch.memory.events if orch.memory is not None else []
        event_counts: Dict[str, int] = {}
        for e in events:
            key = e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type)
            event_counts[key] = event_counts.get(key, 0) + 1

        # Semantic memory score
        semantic_memory_score = round(
            0.25 * recall_rate
            + 0.20 * mean_stability
            + 0.15 * mean_strength
            + 0.15 * consolidation_rate
            + 0.10 * utility
            + 0.10 * min(1.0, density)
            + 0.05 * coherence_phi,
            4,
        )

        return SemanticMemoryAuditMetrics(
            cognitive_score=round(cognitive_score, 4),
            coherence_phi=round(coherence_phi, 4),
            energy_efficiency=round(energy_efficiency, 4),
            semantic_assembly_count=assembly_count,
            semantic_active_assembly_count=active_count,
            semantic_consolidated_assembly_count=consolidated_count,
            mean_assembly_strength=round(mean_strength, 4),
            mean_assembly_stability=round(mean_stability, 4),
            semantic_recall_success_rate=round(recall_rate, 4),
            semantic_memory_density=round(density, 4),
            semantic_memory_utility=round(utility, 4),
            semantic_consolidation_rate=round(consolidation_rate, 4),
            semantic_memory_score=semantic_memory_score,
            assembly_creation_events=event_counts.get("cell_assembly_created", 0),
            assembly_reinforcement_events=event_counts.get("cell_assembly_reinforced", 0),
            assembly_consolidation_events=event_counts.get("cell_assembly_consolidated", 0),
            assembly_decay_events=event_counts.get("cell_assembly_decayed", 0),
            semantic_recall_success_events=event_counts.get("semantic_recall_succeeded", 0),
            semantic_recall_failure_events=event_counts.get("semantic_recall_failed", 0),
            reactivation_events=reactivation_count,
        )

    # ------------------------------------------------------------------ #
    # Suite runner
    # ------------------------------------------------------------------ #

    async def run_audit_suite(
        self, profiles: Optional[List[SemanticMemoryAuditProfile]] = None
    ) -> SemanticMemoryAuditSuiteResult:
        if profiles is None:
            profiles = self.default_profiles()

        audit_id = f"t43b-{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()

        baseline_profile = profiles[0]
        baseline_result = await self._run_profile(baseline_profile)

        profile_results: List[SemanticMemoryAuditResult] = []
        for profile in profiles[1:]:
            result = await self._run_profile(profile)
            result.metrics.cognitive_delta_vs_baseline = (
                result.metrics.cognitive_score - baseline_result.metrics.cognitive_score
            )
            result.metrics.phi_delta_vs_baseline = (
                result.metrics.coherence_phi - baseline_result.metrics.coherence_phi
            )
            result.metrics.energy_delta_vs_baseline = (
                result.metrics.energy_efficiency - baseline_result.metrics.energy_efficiency
            )
            result.metrics.semantic_net_gain = self.compute_semantic_net_gain(
                baseline_result.metrics, result.metrics
            )
            profile_results.append(result)

        best_profile = self._select_best_profile(profile_results)
        verdict = self._compute_verdict(baseline_result, profile_results, best_profile)
        net_gain = self._compute_overall_net_gain(baseline_result, profile_results)

        report = SemanticMemoryAuditSuiteResult(
            audit_id=audit_id,
            created_at=created_at,
            baseline_result=baseline_result,
            profile_results=profile_results,
            best_profile=best_profile,
            verdict=verdict,
            semantic_net_gain=net_gain,
        )

        report.json_report_path = str(self._generate_json_report(report))
        report.markdown_report_path = str(self._generate_markdown_report(report))
        return report

    # ------------------------------------------------------------------ #
    # Net gain & verdict
    # ------------------------------------------------------------------ #

    @staticmethod
    def compute_semantic_net_gain(
        baseline: SemanticMemoryAuditMetrics, candidate: SemanticMemoryAuditMetrics
    ) -> float:
        delta_cognitive = candidate.cognitive_score - baseline.cognitive_score
        delta_phi = candidate.coherence_phi - baseline.coherence_phi
        delta_energy = candidate.energy_efficiency - baseline.energy_efficiency
        gain = (
            0.25 * delta_cognitive
            + 0.25 * delta_phi
            + 0.20 * candidate.semantic_recall_success_rate
            + 0.15 * candidate.mean_assembly_stability
            + 0.10 * candidate.semantic_consolidation_rate
            + 0.05 * delta_energy
        )
        return max(-1.0, min(1.0, round(gain, 4)))

    @staticmethod
    def _compute_overall_net_gain(
        baseline: SemanticMemoryAuditResult,
        profile_results: List[SemanticMemoryAuditResult],
    ) -> float:
        if not profile_results:
            return 0.0
        gains = [
            SemanticMemoryAuditor.compute_semantic_net_gain(
                baseline.metrics, r.metrics
            )
            for r in profile_results
            if r.profile.semantic_memory_enabled
        ]
        return round(sum(gains) / max(1, len(gains)), 4) if gains else 0.0

    @staticmethod
    def _select_best_profile(
        profile_results: List[SemanticMemoryAuditResult],
    ) -> Optional[str]:
        scored = []
        for r in profile_results:
            if not r.passed:
                continue
            score = (
                r.metrics.semantic_memory_score * 0.30
                + r.metrics.semantic_recall_success_rate * 0.25
                + r.metrics.mean_assembly_stability * 0.20
                + r.metrics.cognitive_score * 0.15
                + r.metrics.coherence_phi * 0.10
            )
            scored.append((score, r.profile.name))
        if not scored:
            return None
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    @staticmethod
    def _compute_verdict(
        baseline: SemanticMemoryAuditResult,
        profile_results: List[SemanticMemoryAuditResult],
        best_profile_name: Optional[str],
    ) -> str:
        if not profile_results:
            return "INSUFFICIENT_EVIDENCE"

        enabled_results = [r for r in profile_results if r.profile.semantic_memory_enabled]
        if not enabled_results:
            return "INSUFFICIENT_EVIDENCE"

        baseline_cognitive = baseline.metrics.cognitive_score
        baseline_phi = baseline.metrics.coherence_phi
        baseline_energy = baseline.metrics.energy_efficiency

        avg_cognitive = sum(r.metrics.cognitive_score for r in enabled_results) / max(
            1, len(enabled_results)
        )
        avg_phi = sum(r.metrics.coherence_phi for r in enabled_results) / max(
            1, len(enabled_results)
        )
        avg_energy = sum(r.metrics.energy_efficiency for r in enabled_results) / max(
            1, len(enabled_results)
        )
        avg_recall_rate = sum(
            r.metrics.semantic_recall_success_rate for r in enabled_results
        ) / max(1, len(enabled_results))
        avg_consolidation_rate = sum(
            r.metrics.semantic_consolidation_rate for r in enabled_results
        ) / max(1, len(enabled_results))

        cognitive_regression = avg_cognitive < baseline_cognitive * 0.85
        phi_regression = avg_phi < baseline_phi * 0.85
        energy_regression = avg_energy < baseline_energy * 0.85

        if cognitive_regression:
            return "SEMANTIC_COGNITIVE_REGRESSION"
        if phi_regression:
            return "SEMANTIC_PHI_REGRESSION"
        if energy_regression:
            return "SEMANTIC_ENERGY_REGRESSION"

        overconsolidation = any(
            r.metrics.semantic_consolidated_assembly_count > 0
            and r.metrics.cognitive_score < baseline_cognitive * 0.90
            and r.metrics.coherence_phi < baseline_phi * 0.90
            for r in enabled_results
        )
        if overconsolidation:
            return "SEMANTIC_OVERCONSOLIDATION"

        if 0 < avg_recall_rate < 0.30:
            return "SEMANTIC_RECALL_WEAK"

        if avg_recall_rate > 0 and not cognitive_regression and not phi_regression and not energy_regression:
            return "SEMANTIC_MEMORY_VALIDATED"

        if all(r.metrics.semantic_assembly_count > 0 for r in enabled_results) and avg_recall_rate == 0:
            return "SEMANTIC_MEMORY_PASSIVE"

        return "INSUFFICIENT_EVIDENCE"

    # ------------------------------------------------------------------ #
    # Report generation
    # ------------------------------------------------------------------ #

    def _generate_json_report(self, report: SemanticMemoryAuditSuiteResult) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.report_dir / f"semantic_memory_audit_{timestamp}.json"
        path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        return path

    def _generate_markdown_report(self, report: SemanticMemoryAuditSuiteResult) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.report_dir / f"semantic_memory_audit_{timestamp}.md"
        lines = [
            "# T43B — Semantic Memory Functional Audit Report",
            "",
            f"**Audit ID:** {report.audit_id}",
            f"**Created At:** {report.created_at}",
            f"**Verdict:** {report.verdict}",
            f"**Overall Semantic Net Gain:** {report.semantic_net_gain:.4f}",
            "",
            "## Baseline Profile",
            f"- **Profile:** {report.baseline_result.profile.name}",
            f"- **Cognitive Score:** {report.baseline_result.metrics.cognitive_score:.4f}",
            f"- **Coherence Φ:** {report.baseline_result.metrics.coherence_phi:.4f}",
            f"- **Energy Efficiency:** {report.baseline_result.metrics.energy_efficiency:.4f}",
            "",
            "## Profile Results",
            "",
            "| Profile | Assemblies | Active | Consolidated | Strength | Stability | Recall Rate | Density | Utility | Consolidation | Score | Cog Δ | Φ Δ | Energy Δ | Net Gain | Passed |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for r in report.profile_results:
            m = r.metrics
            lines.append(
                f"| {r.profile.name} | {m.semantic_assembly_count} | {m.semantic_active_assembly_count} | "
                f"{m.semantic_consolidated_assembly_count} | {m.mean_assembly_strength:.4f} | "
                f"{m.mean_assembly_stability:.4f} | {m.semantic_recall_success_rate:.4f} | "
                f"{m.semantic_memory_density:.4f} | {m.semantic_memory_utility:.4f} | "
                f"{m.semantic_consolidation_rate:.4f} | {m.semantic_memory_score:.4f} | "
                f"{m.cognitive_delta_vs_baseline:+.4f} | {m.phi_delta_vs_baseline:+.4f} | "
                f"{m.energy_delta_vs_baseline:+.4f} | {m.semantic_net_gain:+.4f} | {r.passed} |"
            )
        lines.extend([
            "",
            "## Best Profile",
            f"{report.best_profile or 'None'}",
            "",
            "---",
            "*Generated by T43B Semantic Memory Auditor*",
        ])
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
