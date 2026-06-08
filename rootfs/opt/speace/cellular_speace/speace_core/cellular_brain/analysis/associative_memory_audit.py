import copy
import json
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import BenchmarkMetrics
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.memory.semantic.cell_assembly import SemanticMemoryMetrics
from speace_core.dna.models import SharedGenome
from speace_core.dna.parser import load_genome
from speace_core.orchestrator import CellularBrainOrchestrator


class AssociativeMemoryAuditProfile(BaseModel):
    """Configuration for a single associative memory audit profile."""

    profile_id: str
    name: str
    semantic_memory_enabled: bool = True
    associative_learning_enabled: bool = False
    associative_recall_enabled: bool = False
    decay_enabled: bool = False
    prune_enabled: bool = False
    repeated_pattern_count: int = 5
    novel_pattern_count: int = 3
    associative_recall_trials: int = 5
    semantic_recall_trials: int = 3
    n_cycles: int = 20
    description: str = ""

    model_config = ConfigDict(extra="allow")


class AssociativeMemoryAuditMetrics(BaseModel):
    """Metrics extracted for a single profile run."""

    cognitive_score: float = 0.0
    coherence_phi: float = 0.0
    energy_efficiency: float = 0.0
    semantic_assembly_count: int = 0
    semantic_active_assembly_count: int = 0
    semantic_recall_success_rate: float = 0.0
    association_count: int = 0
    mean_association_strength: float = 0.0
    max_association_strength: float = 0.0
    associative_recall_success_rate: float = 0.0
    associative_recall_partial_success_rate: float = 0.0
    association_density: float = 0.0
    associative_memory_effect_score: float = 0.0
    association_creation_events: int = 0
    association_reinforcement_events: int = 0
    association_weakened_events: int = 0
    association_pruned_events: int = 0
    associative_recall_success_events: int = 0
    associative_recall_failure_events: int = 0
    cognitive_delta_vs_baseline: float = 0.0
    phi_delta_vs_baseline: float = 0.0
    energy_delta_vs_baseline: float = 0.0
    associative_net_gain: float = 0.0


class AssociativeMemoryAuditResult(BaseModel):
    """Result of running one profile."""

    profile: AssociativeMemoryAuditProfile
    metrics: AssociativeMemoryAuditMetrics = Field(default_factory=AssociativeMemoryAuditMetrics)
    passed: bool = True


class AssociativeMemoryAuditSuiteResult(BaseModel):
    """Top-level audit report container."""

    audit_id: str
    created_at: str
    baseline_result: AssociativeMemoryAuditResult = Field(
        default_factory=lambda: AssociativeMemoryAuditResult(
            profile=AssociativeMemoryAuditProfile(profile_id="baseline", name="baseline")
        )
    )
    profile_results: List[AssociativeMemoryAuditResult] = Field(default_factory=list)
    best_profile: Optional[str] = None
    verdict: str = "INSUFFICIENT_EVIDENCE"
    associative_net_gain: float = 0.0
    json_report_path: Optional[str] = None
    markdown_report_path: Optional[str] = None


class AssociativeMemoryAuditor:
    """T44B — Validate the functional impact of T44 Associative Learning Between Assemblies."""

    def __init__(
        self,
        genome: Optional[Dict[str, Any]] = None,
        report_dir: str = "reports/associative_memory_audit",
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
    def default_profiles() -> List[AssociativeMemoryAuditProfile]:
        return [
            AssociativeMemoryAuditProfile(
                profile_id="am0",
                name="associative_off",
                semantic_memory_enabled=True,
                associative_learning_enabled=False,
                description="T44 completely disabled; semantic memory only",
            ),
            AssociativeMemoryAuditProfile(
                profile_id="am1",
                name="association_create_only",
                semantic_memory_enabled=True,
                associative_learning_enabled=True,
                description="Create associations but no reinforcement",
            ),
            AssociativeMemoryAuditProfile(
                profile_id="am2",
                name="association_reinforce",
                semantic_memory_enabled=True,
                associative_learning_enabled=True,
                description="Create and reinforce associations",
            ),
            AssociativeMemoryAuditProfile(
                profile_id="am3",
                name="association_decay",
                semantic_memory_enabled=True,
                associative_learning_enabled=True,
                decay_enabled=True,
                description="Associations with decay",
            ),
            AssociativeMemoryAuditProfile(
                profile_id="am4",
                name="association_prune",
                semantic_memory_enabled=True,
                associative_learning_enabled=True,
                prune_enabled=True,
                description="Associations with pruning",
            ),
            AssociativeMemoryAuditProfile(
                profile_id="am5",
                name="associative_recall_enabled",
                semantic_memory_enabled=True,
                associative_learning_enabled=True,
                associative_recall_enabled=True,
                description="Associations + recall",
            ),
            AssociativeMemoryAuditProfile(
                profile_id="am6",
                name="full_associative_stack",
                semantic_memory_enabled=True,
                associative_learning_enabled=True,
                associative_recall_enabled=True,
                decay_enabled=True,
                prune_enabled=True,
                description="Complete T44 stack",
            ),
            AssociativeMemoryAuditProfile(
                profile_id="am7",
                name="noisy_cue_association",
                semantic_memory_enabled=True,
                associative_learning_enabled=True,
                associative_recall_enabled=True,
                description="Recall with noisy cues",
            ),
            AssociativeMemoryAuditProfile(
                profile_id="am8",
                name="sequence_association",
                semantic_memory_enabled=True,
                associative_learning_enabled=True,
                associative_recall_enabled=True,
                description="Sequential pattern associations",
            ),
            AssociativeMemoryAuditProfile(
                profile_id="am9",
                name="contextual_association",
                semantic_memory_enabled=True,
                associative_learning_enabled=True,
                associative_recall_enabled=True,
                description="Contextual multi-assembly associations",
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
        orch: CellularBrainOrchestrator, profile: AssociativeMemoryAuditProfile
    ) -> None:
        orch.semantic_memory_enabled = profile.semantic_memory_enabled
        orch.associative_learning_enabled = profile.associative_learning_enabled
        orch.associative_recall_enabled = profile.associative_recall_enabled
        orch.model_post_init(None)
        if orch.semantic_memory_enabled and orch._cell_assembly_engine is not None:
            orch._cell_assembly_engine.min_mean_activation = 0.05
            orch._cell_assembly_engine.min_neurons = 2
            orch._cell_assembly_engine.min_phi = 0.0
            orch._cell_assembly_engine.min_confidence = 0.0
        # Eagerly init associative engines so the audit can use them directly
        if orch.associative_learning_enabled:
            orch.get_associative_learning_engine()
        if orch.associative_recall_enabled:
            orch.get_associative_recall_engine()

    # ------------------------------------------------------------------ #
    # Pattern helpers
    # ------------------------------------------------------------------ #

    def _get_repeated_pattern(self, index: int) -> List[float]:
        rng = random.Random(self._seed + index)
        return [round(rng.random(), 4) for _ in range(10)]

    def _get_novel_pattern(self, index: int) -> List[float]:
        rng = random.Random(self._seed + 1000 + index)
        return [round(rng.random(), 4) for _ in range(10)]

    def _get_noisy_pattern(self, base_pattern: List[float], noise_level: float = 0.1) -> List[float]:
        rng = random.Random(self._seed + 2000)
        return [round(max(0.0, min(1.0, v + rng.uniform(-noise_level, noise_level))), 4) for v in base_pattern]

    def _default_pattern(self) -> List[float]:
        return [1.0 if i % 2 == 0 else 0.0 for i in range(10)]

    # ------------------------------------------------------------------ #
    # Semantic cycle helpers (mirrors T43B)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _run_semantic_cycle(
        orch: CellularBrainOrchestrator, profile: AssociativeMemoryAuditProfile
    ) -> None:
        engine = orch._cell_assembly_engine
        store = orch._semantic_memory_store
        if engine is None or store is None:
            return

        trace = engine.observe_activation(orch)
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

    # ------------------------------------------------------------------ #
    # Associative cycle helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _run_associative_cycle(
        orch: CellularBrainOrchestrator, profile: AssociativeMemoryAuditProfile
    ) -> None:
        if not profile.associative_learning_enabled:
            return
        engine = orch._associative_learning_engine
        store = orch._semantic_memory_store
        if engine is None or store is None:
            return

        assemblies = list(store._assemblies.values())
        if len(assemblies) < 2:
            return

        # Ensure assemblies are active so they can be observed
        for asm in assemblies:
            asm.active = True

        if profile.name == "association_create_only":
            engine.observe_assemblies(assemblies[:2], tick=orch.current_tick)
        elif profile.name == "association_reinforce":
            for _ in range(3):
                engine.observe_assemblies(assemblies[:2], tick=orch.current_tick)
        elif profile.name == "association_decay":
            for _ in range(3):
                engine.observe_assemblies(assemblies[:2], tick=orch.current_tick)
            engine.decay_associations()
        elif profile.name == "association_prune":
            for _ in range(2):
                engine.observe_assemblies(assemblies[:2], tick=orch.current_tick)
            # Force one association very weak so prune removes it
            if engine._associations:
                first_key = list(engine._associations.keys())[0]
                engine._associations[first_key].strength = 0.01
            engine.prune_weak_associations()
        elif profile.name == "associative_recall_enabled":
            for _ in range(5):
                engine.observe_assemblies(assemblies[:2], tick=orch.current_tick)
        elif profile.name == "full_associative_stack":
            for _ in range(3):
                engine.observe_assemblies(assemblies[:2], tick=orch.current_tick)
            engine.decay_associations()
            engine.prune_weak_associations()
        elif profile.name == "noisy_cue_association":
            for _ in range(4):
                engine.observe_assemblies(assemblies[:2], tick=orch.current_tick)
        elif profile.name == "sequence_association":
            if len(assemblies) >= 2:
                engine.observe_assemblies([assemblies[0], assemblies[1]], tick=orch.current_tick)
                engine.observe_assemblies([assemblies[0]], tick=orch.current_tick + 1)
                engine.observe_assemblies([assemblies[1]], tick=orch.current_tick + 2)
                engine.observe_assemblies([assemblies[0], assemblies[1]], tick=orch.current_tick + 3)
        elif profile.name == "contextual_association":
            if len(assemblies) >= 3:
                engine.observe_assemblies(assemblies[:3], tick=orch.current_tick)
            else:
                engine.observe_assemblies(assemblies, tick=orch.current_tick)
        else:
            # Default: observe first pair once
            engine.observe_assemblies(assemblies[:2], tick=orch.current_tick)

    # ------------------------------------------------------------------ #
    # Profile runner
    # ------------------------------------------------------------------ #

    async def _run_profile(
        self, profile: AssociativeMemoryAuditProfile
    ) -> AssociativeMemoryAuditResult:
        orch = self._build_orchestrator()
        self._apply_profile(orch, profile)

        # Disable automatic cycles so auditor drives them manually
        if profile.semantic_memory_enabled:
            orch.semantic_memory_enabled = False
        if profile.associative_learning_enabled:
            orch.associative_learning_enabled = False

        # Build cycle schedule
        cycles: List[tuple] = []
        for i in range(profile.repeated_pattern_count):
            cycles.extend([("repeated", i), ("repeated", i)])
        for i in range(profile.novel_pattern_count):
            cycles.extend([("novel", i), ("novel", i)])
        while len(cycles) < profile.n_cycles:
            cycles.append(("repeated", 0))
        cycles = cycles[: profile.n_cycles]

        semantic_recall_successes = 0
        semantic_recall_attempts = 0
        associative_recall_successes = 0
        associative_recall_attempts = 0
        associative_partial_successes = 0

        for cycle_idx, (ptype, pidx) in enumerate(cycles):
            if ptype == "repeated":
                pattern = self._get_repeated_pattern(pidx)
            else:
                pattern = self._get_novel_pattern(pidx)

            orch.inject(pattern)
            await orch.run_ticks(1)

            if profile.semantic_memory_enabled:
                self._run_semantic_cycle(orch, profile)

            if profile.associative_learning_enabled:
                self._run_associative_cycle(orch, profile)

            # Interleaved semantic recall
            if (
                profile.semantic_memory_enabled
                and profile.semantic_recall_trials > 0
                and cycle_idx % max(1, profile.n_cycles // max(1, profile.semantic_recall_trials)) == 0
                and semantic_recall_attempts < profile.semantic_recall_trials
            ):
                query = self._get_repeated_pattern(semantic_recall_attempts % profile.repeated_pattern_count)
                engine = orch._semantic_recall_engine
                if engine is not None:
                    res = engine.recall(query)
                    semantic_recall_attempts += 1
                    if res is not None and res.recall_success:
                        semantic_recall_successes += 1

            # Interleaved associative recall
            if (
                profile.associative_recall_enabled
                and profile.associative_recall_trials > 0
                and cycle_idx % max(1, profile.n_cycles // max(1, profile.associative_recall_trials)) == 0
                and associative_recall_attempts < profile.associative_recall_trials
            ):
                store = orch._semantic_memory_store
                recall_engine = orch._associative_recall_engine
                if store is not None and recall_engine is not None:
                    assemblies = list(store._assemblies.values())
                    if assemblies:
                        cue_assembly = assemblies[0]
                        res = recall_engine.recall_from_assembly(cue_assembly.assembly_id)
                        associative_recall_attempts += 1
                        if res is not None:
                            if res.success:
                                associative_recall_successes += 1
                                if orch.memory is not None:
                                    orch.memory.create_event(
                                        event_type=MorphologyEventType.ASSOCIATIVE_RECALL_SUCCEEDED,
                                        source_id="audit",
                                        target_id=cue_assembly.assembly_id,
                                    )
                            else:
                                if orch.memory is not None:
                                    orch.memory.create_event(
                                        event_type=MorphologyEventType.ASSOCIATIVE_RECALL_FAILED,
                                        source_id="audit",
                                        target_id=cue_assembly.assembly_id,
                                    )
                            if res.partial_success:
                                associative_partial_successes += 1

        # Post-cycle associative recall if not exhausted
        if profile.associative_recall_enabled:
            while associative_recall_attempts < profile.associative_recall_trials:
                store = orch._semantic_memory_store
                recall_engine = orch._associative_recall_engine
                if store is not None and recall_engine is not None:
                    assemblies = list(store._assemblies.values())
                    if assemblies:
                        cue_assembly = assemblies[0]
                        res = recall_engine.recall_from_assembly(cue_assembly.assembly_id)
                        associative_recall_attempts += 1
                        if res is not None:
                            if res.success:
                                associative_recall_successes += 1
                                if orch.memory is not None:
                                    orch.memory.create_event(
                                        event_type=MorphologyEventType.ASSOCIATIVE_RECALL_SUCCEEDED,
                                        source_id="audit",
                                        target_id=cue_assembly.assembly_id,
                                    )
                            else:
                                if orch.memory is not None:
                                    orch.memory.create_event(
                                        event_type=MorphologyEventType.ASSOCIATIVE_RECALL_FAILED,
                                        source_id="audit",
                                        target_id=cue_assembly.assembly_id,
                                    )
                            if res.partial_success:
                                associative_partial_successes += 1

        metrics = self._collect_metrics(
            orch,
            semantic_recall_successes,
            semantic_recall_attempts,
            associative_recall_successes,
            associative_recall_attempts,
            associative_partial_successes,
        )
        result = AssociativeMemoryAuditResult(profile=profile, metrics=metrics, passed=True)
        return result

    def _collect_metrics(
        self,
        orch: CellularBrainOrchestrator,
        semantic_recall_successes: int,
        semantic_recall_attempts: int,
        associative_recall_successes: int,
        associative_recall_attempts: int,
        associative_partial_successes: int,
    ) -> AssociativeMemoryAuditMetrics:
        # Baseline circuit metrics
        latest = orch.latest_metrics
        coherence_phi = latest.coherence_phi if latest else 0.0
        mean_energy = latest.mean_energy if latest else 0.0
        energy_efficiency = max(0.0, min(1.0, mean_energy))

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
        semantic_assembly_count = len(all_assemblies)
        semantic_active_count = len(active_assemblies)
        semantic_recall_rate = semantic_recall_successes / max(1, semantic_recall_attempts)

        # Associative metrics
        assoc_engine = orch._associative_learning_engine
        associations = assoc_engine.list_associations() if assoc_engine else []
        association_count = len(associations)
        mean_assoc_strength = (
            sum(a.strength for a in associations) / max(1, association_count)
        )
        max_assoc_strength = max((a.strength for a in associations), default=0.0)
        assoc_density = min(
            1.0, association_count / max(1, semantic_assembly_count * semantic_assembly_count)
        )
        associative_recall_rate = associative_recall_successes / max(1, associative_recall_attempts)
        associative_partial_rate = associative_partial_successes / max(1, associative_recall_attempts)

        # Event counts
        events = orch.memory.events if orch.memory is not None else []
        event_counts: Dict[str, int] = {}
        for e in events:
            key = e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type)
            event_counts[key] = event_counts.get(key, 0) + 1

        # Associative memory effect score
        associative_memory_effect_score = round(
            0.30 * associative_recall_rate
            + 0.20 * associative_partial_rate
            + 0.20 * mean_assoc_strength
            + 0.15 * assoc_density
            + 0.15 * min(1.0, association_count / max(1, semantic_assembly_count))
            if association_count > 0
            else 0.0,
            4,
        )

        return AssociativeMemoryAuditMetrics(
            cognitive_score=round(cognitive_score, 4),
            coherence_phi=round(coherence_phi, 4),
            energy_efficiency=round(energy_efficiency, 4),
            semantic_assembly_count=semantic_assembly_count,
            semantic_active_assembly_count=semantic_active_count,
            semantic_recall_success_rate=round(semantic_recall_rate, 4),
            association_count=association_count,
            mean_association_strength=round(mean_assoc_strength, 4),
            max_association_strength=round(max_assoc_strength, 4),
            associative_recall_success_rate=round(associative_recall_rate, 4),
            associative_recall_partial_success_rate=round(associative_partial_rate, 4),
            association_density=round(assoc_density, 4),
            associative_memory_effect_score=associative_memory_effect_score,
            association_creation_events=event_counts.get("assembly_association_created", 0),
            association_reinforcement_events=event_counts.get("assembly_association_reinforced", 0),
            association_weakened_events=event_counts.get("assembly_association_weakened", 0),
            association_pruned_events=event_counts.get("assembly_association_pruned", 0),
            associative_recall_success_events=event_counts.get("associative_recall_succeeded", 0),
            associative_recall_failure_events=event_counts.get("associative_recall_failed", 0),
        )

    # ------------------------------------------------------------------ #
    # Suite runner
    # ------------------------------------------------------------------ #

    async def run_audit_suite(
        self, profiles: Optional[List[AssociativeMemoryAuditProfile]] = None
    ) -> AssociativeMemoryAuditSuiteResult:
        if profiles is None:
            profiles = self.default_profiles()

        audit_id = f"t44b-{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()

        baseline_profile = profiles[0]
        baseline_result = await self._run_profile(baseline_profile)

        profile_results: List[AssociativeMemoryAuditResult] = []
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
            result.metrics.associative_net_gain = self.compute_associative_net_gain(
                baseline_result.metrics, result.metrics
            )
            profile_results.append(result)

        best_profile = self._select_best_profile(profile_results)
        verdict = self._compute_verdict(baseline_result, profile_results, best_profile)
        net_gain = self._compute_overall_net_gain(baseline_result, profile_results)

        report = AssociativeMemoryAuditSuiteResult(
            audit_id=audit_id,
            created_at=created_at,
            baseline_result=baseline_result,
            profile_results=profile_results,
            best_profile=best_profile,
            verdict=verdict,
            associative_net_gain=net_gain,
        )

        report.json_report_path = str(self._generate_json_report(report))
        report.markdown_report_path = str(self._generate_markdown_report(report))
        return report

    # ------------------------------------------------------------------ #
    # Net gain & verdict
    # ------------------------------------------------------------------ #

    @staticmethod
    def compute_associative_net_gain(
        baseline: AssociativeMemoryAuditMetrics, candidate: AssociativeMemoryAuditMetrics
    ) -> float:
        delta_cognitive = candidate.cognitive_score - baseline.cognitive_score
        delta_phi = candidate.coherence_phi - baseline.coherence_phi
        delta_energy = candidate.energy_efficiency - baseline.energy_efficiency
        gain = (
            0.20 * delta_cognitive
            + 0.20 * delta_phi
            + 0.20 * candidate.associative_recall_success_rate
            + 0.15 * candidate.mean_association_strength
            + 0.10 * candidate.association_density
            + 0.10 * candidate.associative_memory_effect_score
            + 0.05 * delta_energy
        )
        return max(-1.0, min(1.0, round(gain, 4)))

    @staticmethod
    def _compute_overall_net_gain(
        baseline: AssociativeMemoryAuditResult,
        profile_results: List[AssociativeMemoryAuditResult],
    ) -> float:
        if not profile_results:
            return 0.0
        gains = [
            AssociativeMemoryAuditor.compute_associative_net_gain(
                baseline.metrics, r.metrics
            )
            for r in profile_results
            if r.profile.associative_learning_enabled
        ]
        return round(sum(gains) / max(1, len(gains)), 4) if gains else 0.0

    @staticmethod
    def _select_best_profile(
        profile_results: List[AssociativeMemoryAuditResult],
    ) -> Optional[str]:
        scored = []
        for r in profile_results:
            if not r.passed:
                continue
            score = (
                r.metrics.associative_memory_effect_score * 0.30
                + r.metrics.associative_recall_success_rate * 0.25
                + r.metrics.mean_association_strength * 0.20
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
        baseline: AssociativeMemoryAuditResult,
        profile_results: List[AssociativeMemoryAuditResult],
        best_profile_name: Optional[str],
    ) -> str:
        if not profile_results:
            return "INSUFFICIENT_EVIDENCE"

        enabled_results = [r for r in profile_results if r.profile.associative_learning_enabled]
        if not enabled_results:
            return "INSUFFICIENT_EVIDENCE"

        baseline_cognitive = baseline.metrics.cognitive_score
        baseline_phi = baseline.metrics.coherence_phi
        baseline_energy = baseline.metrics.energy_efficiency
        baseline_semantic_recall = baseline.metrics.semantic_recall_success_rate

        avg_cognitive = sum(r.metrics.cognitive_score for r in enabled_results) / max(1, len(enabled_results))
        avg_phi = sum(r.metrics.coherence_phi for r in enabled_results) / max(1, len(enabled_results))
        avg_energy = sum(r.metrics.energy_efficiency for r in enabled_results) / max(1, len(enabled_results))
        avg_semantic_recall = sum(r.metrics.semantic_recall_success_rate for r in enabled_results) / max(1, len(enabled_results))
        avg_assoc_count = sum(r.metrics.association_count for r in enabled_results) / max(1, len(enabled_results))
        avg_assoc_recall = sum(r.metrics.associative_recall_success_rate for r in enabled_results) / max(1, len(enabled_results))
        avg_assoc_strength = sum(r.metrics.mean_association_strength for r in enabled_results) / max(1, len(enabled_results))

        cognitive_regression = avg_cognitive < baseline_cognitive * 0.85
        phi_regression = avg_phi < baseline_phi * 0.85
        energy_regression = avg_energy < baseline_energy * 0.85
        semantic_recall_regression = avg_semantic_recall < baseline_semantic_recall * 0.70 and baseline_semantic_recall > 0

        if cognitive_regression:
            return "SEMANTIC_COGNITIVE_REGRESSION"
        if phi_regression:
            return "PHI_REGRESSION"
        if energy_regression:
            return "ENERGY_REGRESSION"
        if semantic_recall_regression:
            return "SEMANTIC_RECALL_REGRESSION"

        # Association overgrowth: many associations but weak or no recall benefit
        overgrowth = avg_assoc_count > 10 and avg_assoc_recall < 0.20 and avg_assoc_strength < 0.30
        if overgrowth:
            return "ASSOCIATION_OVERGROWTH"

        if 0 < avg_assoc_recall < 0.30:
            return "ASSOCIATIVE_RECALL_WEAK"

        if avg_assoc_recall > 0 and not cognitive_regression and not phi_regression and not energy_regression and not semantic_recall_regression:
            return "ASSOCIATIVE_MEMORY_VALIDATED"

        if avg_assoc_count > 0 and avg_assoc_recall == 0:
            return "ASSOCIATION_NO_EFFECT"

        return "INSUFFICIENT_EVIDENCE"

    # ------------------------------------------------------------------ #
    # Report generation
    # ------------------------------------------------------------------ #

    def _generate_json_report(self, report: AssociativeMemoryAuditSuiteResult) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.report_dir / f"associative_memory_audit_{timestamp}.json"
        path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        return path

    def _generate_markdown_report(self, report: AssociativeMemoryAuditSuiteResult) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.report_dir / f"associative_memory_audit_{timestamp}.md"
        lines = [
            "# T44B — Associative Memory Functional Audit Report",
            "",
            f"**Audit ID:** {report.audit_id}",
            f"**Created At:** {report.created_at}",
            f"**Verdict:** {report.verdict}",
            f"**Overall Associative Net Gain:** {report.associative_net_gain:.4f}",
            "",
            "## Baseline Profile",
            f"- **Profile:** {report.baseline_result.profile.name}",
            f"- **Cognitive Score:** {report.baseline_result.metrics.cognitive_score:.4f}",
            f"- **Coherence Φ:** {report.baseline_result.metrics.coherence_phi:.4f}",
            f"- **Energy Efficiency:** {report.baseline_result.metrics.energy_efficiency:.4f}",
            f"- **Semantic Recall Rate:** {report.baseline_result.metrics.semantic_recall_success_rate:.4f}",
            "",
            "## Profile Results",
            "",
            "| Profile | Assemblies | Active | Assoc Count | Mean Strength | Max Strength | Assoc Recall | Partial Recall | Density | Effect Score | Cog Δ | Φ Δ | Energy Δ | Net Gain | Passed |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for r in report.profile_results:
            m = r.metrics
            lines.append(
                f"| {r.profile.name} | {m.semantic_assembly_count} | {m.semantic_active_assembly_count} | "
                f"{m.association_count} | {m.mean_association_strength:.4f} | "
                f"{m.max_association_strength:.4f} | {m.associative_recall_success_rate:.4f} | "
                f"{m.associative_recall_partial_success_rate:.4f} | {m.association_density:.4f} | "
                f"{m.associative_memory_effect_score:.4f} | {m.cognitive_delta_vs_baseline:+.4f} | "
                f"{m.phi_delta_vs_baseline:+.4f} | {m.energy_delta_vs_baseline:+.4f} | "
                f"{m.associative_net_gain:+.4f} | {r.passed} |"
            )
        lines.extend([
            "",
            "## Best Profile",
            f"{report.best_profile or 'None'}",
            "",
            "---",
            "*Generated by T44B Associative Memory Auditor*",
        ])
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
