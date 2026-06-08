import copy
import math
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.memory.semantic.cell_assembly import (
    AssemblyActivationTrace,
    SemanticMemoryMetrics,
)
from speace_core.cellular_brain.memory.semantic.semantic_memory_store import (
    SemanticMemoryStore,
)
from speace_core.dna.models import SharedGenome
from speace_core.dna.parser import load_genome
from speace_core.orchestrator import CellularBrainOrchestrator


# ------------------------------------------------------------------ #
# Models
# ------------------------------------------------------------------ #

class SemanticStimulus(BaseModel):
    stimulus_id: str
    pattern: List[float]
    label: str
    target_region: str = "hippocampus"
    repetitions: int = 5
    interval_ticks: int = 1
    amplitude: float = 1.0
    noise_level: float = 0.0
    expected_assembly_signature: str | None = None


class SemanticRecallProbe(BaseModel):
    probe_id: str
    cue_pattern: List[float]
    expected_label: str
    partial_cue_ratio: float = 0.5
    noise_level: float = 0.0
    recall_threshold: float = 0.70


class SemanticStimulationProfile(BaseModel):
    profile_name: str
    repeated_stimuli_count: int = 3
    novel_stimuli_count: int = 2
    repetitions_per_stimulus: int = 6
    consolidation_ticks: int = 3
    recall_trials: int = 5
    cue_degradation_ratio: float = 0.5
    stimulation_amplitude: float = 1.0
    semantic_memory_enabled: bool = True
    consolidation_enabled: bool = True
    recall_enabled: bool = True
    reactivation_enabled: bool = False
    pattern_size: int = 10
    pattern_separation: float = 0.5
    seed: int = 42

    model_config = ConfigDict(extra="allow")


class SemanticStimulationMetrics(BaseModel):
    stimulus_count: int = 0
    repeated_stimulus_count: int = 0
    novel_stimulus_count: int = 0
    pattern_separation_mean: float = 0.0
    pattern_separation_min: float = 0.0
    encoding_events: int = 0
    assembly_created_events: int = 0
    assembly_reinforced_events: int = 0
    assembly_consolidated_events: int = 0
    recall_attempts: int = 0
    recall_successes: int = 0
    recall_failures: int = 0
    recall_success_rate: float = 0.0
    partial_cue_success_rate: float = 0.0
    noisy_cue_success_rate: float = 0.0
    mean_assembly_strength: float = 0.0
    mean_assembly_stability: float = 0.0
    mean_recurrence_count: float = 0.0
    semantic_discrimination_score: float = 0.0
    semantic_consolidation_score: float = 0.0
    semantic_stimulation_effectiveness: float = 0.0
    cognitive_delta: float = 0.0
    phi_delta: float = 0.0
    energy_delta: float = 0.0


class SemanticStimulationResult(BaseModel):
    profile: SemanticStimulationProfile
    metrics: SemanticStimulationMetrics = Field(default_factory=SemanticStimulationMetrics)
    passed: bool = True


class SemanticStimulationSuiteResult(BaseModel):
    audit_id: str
    created_at: str
    baseline_result: SemanticStimulationResult = Field(
        default_factory=lambda: SemanticStimulationResult(
            profile=SemanticStimulationProfile(profile_name="baseline")
        )
    )
    profile_results: List[SemanticStimulationResult] = Field(default_factory=list)
    best_profile: Optional[str] = None
    worst_profile: Optional[str] = None
    verdict: str = "INSUFFICIENT_EVIDENCE"
    json_report_path: Optional[str] = None
    markdown_report_path: Optional[str] = None


# ------------------------------------------------------------------ #
# Designer
# ------------------------------------------------------------------ #

class SemanticStimulationDesigner:
    """T43C — Redesign semantic benchmark stimulation for observable encoding,
    consolidation, and recall."""

    def __init__(
        self,
        genome: Optional[Dict[str, Any]] = None,
        report_dir: str = "reports/semantic_stimulation",
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
    # Pattern generation
    # ------------------------------------------------------------------ #

    @staticmethod
    def generate_distinct_patterns(
        count: int, size: int, separation: float = 0.5, seed: int = 42
    ) -> List[List[float]]:
        rng = random.Random(seed)
        patterns: List[List[float]] = []
        max_attempts = count * 100
        attempts = 0

        while len(patterns) < count and attempts < max_attempts:
            attempts += 1
            # Structured binary-ish patterns with some amplitude variation
            base = [1.0 if i % 2 == (len(patterns) % 2) else 0.0 for i in range(size)]
            # Add controlled randomness to make patterns distinct but not chaotic
            candidate = [round(min(1.0, max(0.0, v + rng.uniform(-0.15, 0.15))), 4) for v in base]

            # Check minimum separation against all existing patterns
            ok = True
            for existing in patterns:
                dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(candidate, existing)))
                if dist < separation:
                    ok = False
                    break

            if ok or not patterns:
                patterns.append(candidate)

        # Fallback: if we couldn't generate enough with separation, just generate unique-ish patterns
        while len(patterns) < count:
            idx = len(patterns)
            base = [1.0 if (i + idx) % 3 == 0 else 0.0 for i in range(size)]
            candidate = [round(min(1.0, max(0.0, v + rng.uniform(-0.05, 0.05))), 4) for v in base]
            patterns.append(candidate)

        return patterns[:count]

    @staticmethod
    def compute_pattern_separation(patterns: List[List[float]]) -> Tuple[float, float]:
        if len(patterns) < 2:
            return 0.0, 0.0
        distances = []
        for i in range(len(patterns)):
            for j in range(i + 1, len(patterns)):
                dist = math.sqrt(
                    sum((a - b) ** 2 for a, b in zip(patterns[i], patterns[j]))
                )
                distances.append(dist)
        return sum(distances) / max(1, len(distances)), min(distances) if distances else 0.0

    # ------------------------------------------------------------------ #
    # Orchestrator helpers
    # ------------------------------------------------------------------ #

    def _build_orchestrator(self, profile: SemanticStimulationProfile) -> CellularBrainOrchestrator:
        random.seed(profile.seed)
        genome = SharedGenome(**copy.deepcopy(self.genome))
        orch = CellularBrainOrchestrator.build_mvp(genome)
        orch.semantic_memory_enabled = profile.semantic_memory_enabled
        orch.model_post_init(None)

        if orch._cell_assembly_engine is not None:
            orch._cell_assembly_engine.min_mean_activation = 0.05
            orch._cell_assembly_engine.min_neurons = 2
            orch._cell_assembly_engine.min_phi = 0.0
            orch._cell_assembly_engine.min_confidence = 0.0
            orch._cell_assembly_engine.similarity_threshold = 0.65
            orch._cell_assembly_engine.consolidation_recurrence = 3
            orch._cell_assembly_engine.consolidation_stability = 0.25
            orch._cell_assembly_engine.decay_rate = 0.01

        # Region targeting
        if "hippocampus" in profile.profile_name or "prefrontal" in profile.profile_name:
            for n in orch.circuit.hidden_neurons:
                if not getattr(n, "region", None):
                    n.region = "hippocampus"
            if "prefrontal" in profile.profile_name:
                for n in orch.circuit.hidden_neurons[: len(orch.circuit.hidden_neurons) // 2]:
                    n.region = "prefrontal"

        return orch

    @staticmethod
    def _add_noise(pattern: List[float], noise_level: float, rng: random.Random) -> List[float]:
        if noise_level <= 0.0:
            return list(pattern)
        return [
            round(min(1.0, max(0.0, v + rng.uniform(-noise_level, noise_level))), 4)
            for v in pattern
        ]

    @staticmethod
    def _degrade_cue(pattern: List[float], ratio: float, rng: random.Random) -> List[float]:
        """Partial cue: keep ratio fraction of values, zero out rest."""
        if ratio >= 1.0:
            return list(pattern)
        indices = list(range(len(pattern)))
        rng.shuffle(indices)
        keep_count = max(1, int(len(pattern) * ratio))
        keep_set = set(indices[:keep_count])
        return [v if i in keep_set else 0.0 for i, v in enumerate(pattern)]

    # ------------------------------------------------------------------ #
    # Stimulus builders
    # ------------------------------------------------------------------ #

    def build_stimulus_sequence(
        self, profile: SemanticStimulationProfile
    ) -> List[SemanticStimulus]:
        rng = random.Random(profile.seed)
        repeated_patterns = self.generate_distinct_patterns(
            profile.repeated_stimuli_count, profile.pattern_size, profile.pattern_separation, profile.seed
        )
        novel_patterns = self.generate_distinct_patterns(
            profile.novel_stimuli_count,
            profile.pattern_size,
            profile.pattern_separation,
            profile.seed + 1000,
        )

        stimuli: List[SemanticStimulus] = []
        for idx, pat in enumerate(repeated_patterns):
            stimuli.append(
                SemanticStimulus(
                    stimulus_id=f"rep_{idx}",
                    pattern=pat,
                    label=f"repeated_{idx}",
                    repetitions=profile.repetitions_per_stimulus,
                    amplitude=profile.stimulation_amplitude,
                    noise_level=0.0 if "noisy" not in profile.profile_name else 0.1,
                )
            )
        for idx, pat in enumerate(novel_patterns):
            stimuli.append(
                SemanticStimulus(
                    stimulus_id=f"nov_{idx}",
                    pattern=pat,
                    label=f"novel_{idx}",
                    repetitions=1,
                    amplitude=profile.stimulation_amplitude,
                )
            )
        return stimuli

    def build_recall_probes(
        self, stimuli: List[SemanticStimulus], profile: SemanticStimulationProfile
    ) -> List[SemanticRecallProbe]:
        rng = random.Random(profile.seed + 500)
        probes: List[SemanticRecallProbe] = []
        for stim in stimuli:
            if not stim.stimulus_id.startswith("rep_"):
                continue
            cue = self._degrade_cue(stim.pattern, profile.cue_degradation_ratio, rng)
            cue = self._add_noise(cue, 0.05, rng)
            probes.append(
                SemanticRecallProbe(
                    probe_id=f"probe_{stim.stimulus_id}",
                    cue_pattern=cue,
                    expected_label=stim.label,
                    partial_cue_ratio=profile.cue_degradation_ratio,
                    noise_level=0.05,
                    recall_threshold=0.60,
                )
            )
        return probes

    # ------------------------------------------------------------------ #
    # Phase runners
    # ------------------------------------------------------------------ #

    @staticmethod
    def inject_semantic_stimulus(
        orchestrator: CellularBrainOrchestrator, stimulus: SemanticStimulus
    ) -> None:
        pattern = [min(1.0, max(0.0, v * stimulus.amplitude)) for v in stimulus.pattern]
        orchestrator.inject(pattern)

    async def run_encoding_phase(
        self, orchestrator: CellularBrainOrchestrator, stimuli: List[SemanticStimulus], profile: SemanticStimulationProfile
    ) -> None:
        for stim in stimuli:
            for _ in range(stim.repetitions):
                self.inject_semantic_stimulus(orchestrator, stim)
                await orchestrator.run_ticks(1)
                if profile.semantic_memory_enabled and orchestrator._cell_assembly_engine is not None:
                    # Manual semantic cycle (same as auditor)
                    trace = orchestrator._cell_assembly_engine.observe_activation(orchestrator)
                    matched = orchestrator._cell_assembly_engine.match_existing_assembly(trace)
                    if matched is not None:
                        orchestrator._cell_assembly_engine.reinforce_assembly(matched, trace)
                        if orchestrator.memory is not None:
                            orchestrator.memory.create_event(
                                event_type=MorphologyEventType.CELL_ASSEMBLY_REINFORCED,
                                source_id="designer",
                                target_id=matched.assembly_id,
                            )
                    else:
                        candidate = orchestrator._cell_assembly_engine.detect_candidate_assembly(trace)
                        if candidate is not None:
                            if orchestrator._semantic_memory_store is not None:
                                orchestrator._semantic_memory_store.save(candidate)
                            if orchestrator.memory is not None:
                                orchestrator.memory.create_event(
                                    event_type=MorphologyEventType.CELL_ASSEMBLY_CREATED,
                                    source_id="designer",
                                    target_id=candidate.assembly_id,
                                )

    async def run_consolidation_phase(
        self, orchestrator: CellularBrainOrchestrator, profile: SemanticStimulationProfile
    ) -> None:
        if not profile.semantic_memory_enabled or profile.consolidation_enabled is False:
            return
        engine = orchestrator._cell_assembly_engine
        if engine is None:
            return
        for _ in range(profile.consolidation_ticks):
            await orchestrator.run_ticks(1)
            trace = engine.observe_activation(orchestrator)
            matched = engine.match_existing_assembly(trace)
            if matched is not None:
                engine.reinforce_assembly(matched, trace)
            engine.decay_assemblies()
            engine.consolidate_assemblies()

    async def run_recall_phase(
        self,
        orchestrator: CellularBrainOrchestrator,
        probes: List[SemanticRecallProbe],
        profile: SemanticStimulationProfile,
    ) -> Tuple[int, int, int, int, int]:
        successes = 0
        failures = 0
        partial_successes = 0
        noisy_successes = 0
        attempts = 0

        if not profile.recall_enabled or not profile.semantic_memory_enabled:
            return 0, 0, 0, 0, 0

        engine = orchestrator._semantic_recall_engine
        if engine is None:
            return 0, 0, 0, 0, 0

        for probe in probes:
            # Present cue, let circuit settle, then recall from full activation vector
            orchestrator.inject(probe.cue_pattern)
            await orchestrator.run_ticks(1)
            trace = engine._extract_trace_from_orchestrator(orchestrator)
            result = engine.recall(trace.activation_vector)
            attempts += 1

            if result is not None and result.recall_success:
                successes += 1
                if orchestrator.memory is not None:
                    orchestrator.memory.create_event(
                        event_type=MorphologyEventType.SEMANTIC_RECALL_SUCCEEDED,
                        source_id="designer",
                        target_id=result.best_match_id or "",
                    )
            else:
                failures += 1
                if orchestrator.memory is not None:
                    orchestrator.memory.create_event(
                        event_type=MorphologyEventType.SEMANTIC_RECALL_FAILED,
                        source_id="designer",
                    )

        # Noisy recall variant: add extra noise to probes and try again
        rng = random.Random(profile.seed + 999)
        for probe in probes[: min(3, len(probes))]:
            noisy_cue = self._add_noise(probe.cue_pattern, 0.15, rng)
            orchestrator.inject(noisy_cue)
            await orchestrator.run_ticks(1)
            trace = engine._extract_trace_from_orchestrator(orchestrator)
            result = engine.recall(trace.activation_vector)
            if result is not None and result.recall_success:
                noisy_successes += 1

        # Partial cue is already what probes use
        partial_successes = successes

        return attempts, successes, failures, partial_successes, noisy_successes

    # ------------------------------------------------------------------ #
    # Profile runner
    # ------------------------------------------------------------------ #

    async def run_profile(self, profile: SemanticStimulationProfile) -> SemanticStimulationResult:
        orch = self._build_orchestrator(profile)
        stimuli = self.build_stimulus_sequence(profile)

        # Baseline metrics before stimulation
        baseline_metrics = orch.latest_metrics
        baseline_cognitive = self._compute_cognitive_score(orch)
        baseline_phi = baseline_metrics.coherence_phi if baseline_metrics else 0.0
        baseline_energy = baseline_metrics.mean_energy if baseline_metrics else 0.0

        # Encoding
        await self.run_encoding_phase(orch, stimuli, profile)

        # Consolidation
        await self.run_consolidation_phase(orch, profile)

        # Build probes and recall
        probes = self.build_recall_probes(stimuli, profile)
        attempts, successes, failures, partial_successes, noisy_successes = (
            await self.run_recall_phase(orch, probes, profile)
        )

        # Reactivation if enabled
        reactivation_count = 0
        if (
            profile.reactivation_enabled
            and orch._semantic_recall_engine is not None
            and orch._semantic_memory_store is not None
        ):
            for asm in orch._semantic_memory_store.list_active():
                orch._semantic_recall_engine.reactivate_assembly(asm.assembly_id, orch)
                reactivation_count += 1

        # Collect metrics
        metrics = self._collect_metrics(
            orch,
            stimuli,
            probes,
            attempts,
            successes,
            failures,
            partial_successes,
            noisy_successes,
            reactivation_count,
            baseline_cognitive,
            baseline_phi,
            baseline_energy,
        )

        return SemanticStimulationResult(profile=profile, metrics=metrics, passed=True)

    # ------------------------------------------------------------------ #
    # Metrics
    # ------------------------------------------------------------------ #

    @staticmethod
    def _compute_cognitive_score(orch: CellularBrainOrchestrator) -> float:
        outputs = orch.circuit.output_neurons
        if not outputs:
            return 0.0
        clamped = [min(1.0, max(0.0, n.activation)) for n in outputs]
        # Proxy: variance of outputs (higher variance = more differentiated response)
        mean_out = sum(clamped) / len(clamped)
        variance = sum((v - mean_out) ** 2 for v in clamped) / len(clamped)
        return round(min(1.0, variance * 4.0), 4)

    def _collect_metrics(
        self,
        orch: CellularBrainOrchestrator,
        stimuli: List[SemanticStimulus],
        probes: List[SemanticRecallProbe],
        attempts: int,
        successes: int,
        failures: int,
        partial_successes: int,
        noisy_successes: int,
        reactivation_count: int,
        baseline_cognitive: float,
        baseline_phi: float,
        baseline_energy: float,
    ) -> SemanticStimulationMetrics:
        store = orch._semantic_memory_store
        all_assemblies = list(store._assemblies.values()) if store else []
        active_assemblies = [a for a in all_assemblies if a.active]
        consolidated_assemblies = [a for a in all_assemblies if a.consolidated]

        n_asm = len(all_assemblies)
        mean_strength = sum(a.strength for a in all_assemblies) / max(1, n_asm) if n_asm else 0.0
        mean_stability = sum(a.stability for a in all_assemblies) / max(1, n_asm) if n_asm else 0.0
        mean_recurrence = sum(a.recurrence_count for a in all_assemblies) / max(1, n_asm) if n_asm else 0.0

        # Pattern separation among repeated stimuli
        repeated_patterns = [s.pattern for s in stimuli if s.stimulus_id.startswith("rep_")]
        sep_mean, sep_min = self.compute_pattern_separation(repeated_patterns)

        # Event counts
        events = orch.memory.events if orch.memory is not None else []
        event_counts: Dict[str, int] = {}
        for e in events:
            key = e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type)
            event_counts[key] = event_counts.get(key, 0) + 1

        # Discrimination score: how well separated are assembly signatures
        discrimination = 0.0
        if n_asm >= 2:
            from speace_core.cellular_brain.memory.semantic.semantic_recall_engine import (
                SemanticRecallEngine,
            )
            sigs = [a.activation_signature for a in all_assemblies if a.activation_signature]
            distances = []
            for i in range(len(sigs)):
                for j in range(i + 1, len(sigs)):
                    sim = SemanticRecallEngine.compute_similarity(sigs[i], sigs[j])
                    distances.append(1.0 - sim)
            discrimination = sum(distances) / max(1, len(distances)) if distances else 0.0

        # Consolidation score
        consolidation_score = len(consolidated_assemblies) / max(1, n_asm) if n_asm else 0.0

        # Cognitive/phi/energy after stimulation
        latest = orch.latest_metrics
        final_cognitive = self._compute_cognitive_score(orch)
        final_phi = latest.coherence_phi if latest else 0.0
        final_energy = latest.mean_energy if latest else 0.0

        recall_rate = successes / max(1, attempts)
        partial_rate = partial_successes / max(1, attempts)
        noisy_rate = noisy_successes / max(1, min(3, len(probes)))

        effectiveness = round(
            0.25 * recall_rate
            + 0.20 * discrimination
            + 0.20 * consolidation_score
            + 0.15 * mean_stability
            + 0.10 * max(0.0, final_phi - baseline_phi)
            + 0.10 * max(0.0, final_cognitive - baseline_cognitive),
            4,
        )
        effectiveness = max(0.0, min(1.0, effectiveness))

        return SemanticStimulationMetrics(
            stimulus_count=len(stimuli),
            repeated_stimulus_count=len(repeated_patterns),
            novel_stimulus_count=len(stimuli) - len(repeated_patterns),
            pattern_separation_mean=round(sep_mean, 4),
            pattern_separation_min=round(sep_min, 4),
            encoding_events=len(stimuli),
            assembly_created_events=event_counts.get("cell_assembly_created", 0),
            assembly_reinforced_events=event_counts.get("cell_assembly_reinforced", 0),
            assembly_consolidated_events=event_counts.get("cell_assembly_consolidated", 0),
            recall_attempts=attempts,
            recall_successes=successes,
            recall_failures=failures,
            recall_success_rate=round(recall_rate, 4),
            partial_cue_success_rate=round(partial_rate, 4),
            noisy_cue_success_rate=round(noisy_rate, 4),
            mean_assembly_strength=round(mean_strength, 4),
            mean_assembly_stability=round(mean_stability, 4),
            mean_recurrence_count=round(mean_recurrence, 4),
            semantic_discrimination_score=round(discrimination, 4),
            semantic_consolidation_score=round(consolidation_score, 4),
            semantic_stimulation_effectiveness=effectiveness,
            cognitive_delta=round(final_cognitive - baseline_cognitive, 4),
            phi_delta=round(final_phi - baseline_phi, 4),
            energy_delta=round(final_energy - baseline_energy, 4),
        )

    # ------------------------------------------------------------------ #
    # Suite runner
    # ------------------------------------------------------------------ #

    @staticmethod
    def default_profiles() -> List[SemanticStimulationProfile]:
        return [
            SemanticStimulationProfile(
                profile_name="semantic_off_control",
                semantic_memory_enabled=False,
                repetitions_per_stimulus=1,
                recall_enabled=False,
            ),
            SemanticStimulationProfile(
                profile_name="weak_repetition",
                repetitions_per_stimulus=2,
                consolidation_ticks=1,
            ),
            SemanticStimulationProfile(
                profile_name="strong_repetition",
                repetitions_per_stimulus=8,
                consolidation_ticks=5,
            ),
            SemanticStimulationProfile(
                profile_name="high_separation_patterns",
                pattern_separation=0.8,
                repetitions_per_stimulus=6,
            ),
            SemanticStimulationProfile(
                profile_name="partial_cue_recall",
                cue_degradation_ratio=0.3,
                repetitions_per_stimulus=6,
            ),
            SemanticStimulationProfile(
                profile_name="noisy_recall",
                cue_degradation_ratio=0.5,
                repetitions_per_stimulus=6,
            ),
            SemanticStimulationProfile(
                profile_name="consolidation_heavy",
                repetitions_per_stimulus=8,
                consolidation_ticks=8,
            ),
            SemanticStimulationProfile(
                profile_name="hippocampus_targeted",
                repetitions_per_stimulus=6,
                consolidation_ticks=3,
            ),
            SemanticStimulationProfile(
                profile_name="hippocampus_prefrontal_reactivation",
                repetitions_per_stimulus=6,
                consolidation_ticks=3,
                reactivation_enabled=True,
            ),
            SemanticStimulationProfile(
                profile_name="full_semantic_stimulation",
                repetitions_per_stimulus=8,
                consolidation_ticks=5,
                cue_degradation_ratio=0.4,
                reactivation_enabled=True,
            ),
        ]

    async def run_suite(
        self, profiles: Optional[List[SemanticStimulationProfile]] = None
    ) -> SemanticStimulationSuiteResult:
        if profiles is None:
            profiles = self.default_profiles()

        audit_id = f"t43c-{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()

        baseline_profile = profiles[0]
        baseline_result = await self.run_profile(baseline_profile)

        profile_results: List[SemanticStimulationResult] = []
        for profile in profiles[1:]:
            result = await self.run_profile(profile)
            profile_results.append(result)

        best_profile, worst_profile = self._select_best_and_worst(profile_results)
        verdict = self._compute_verdict(baseline_result, profile_results)

        suite = SemanticStimulationSuiteResult(
            audit_id=audit_id,
            created_at=created_at,
            baseline_result=baseline_result,
            profile_results=profile_results,
            best_profile=best_profile,
            worst_profile=worst_profile,
            verdict=verdict,
        )

        suite.json_report_path = str(self._generate_json_report(suite))
        suite.markdown_report_path = str(self._generate_markdown_report(suite))
        return suite

    # ------------------------------------------------------------------ #
    # Verdict & scoring
    # ------------------------------------------------------------------ #

    @staticmethod
    def _select_best_and_worst(
        profile_results: List[SemanticStimulationResult],
    ) -> Tuple[Optional[str], Optional[str]]:
        scored = []
        for r in profile_results:
            if not r.passed:
                continue
            score = (
                r.metrics.semantic_stimulation_effectiveness * 0.35
                + r.metrics.recall_success_rate * 0.30
                + r.metrics.mean_assembly_stability * 0.20
                + r.metrics.semantic_consolidation_score * 0.15
            )
            scored.append((score, r.profile.profile_name))
        if not scored:
            return None, None
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1], scored[-1][1]

    @staticmethod
    def _compute_verdict(
        baseline: SemanticStimulationResult,
        profile_results: List[SemanticStimulationResult],
    ) -> str:
        if not profile_results:
            return "INSUFFICIENT_EVIDENCE"

        enabled = [r for r in profile_results if r.profile.semantic_memory_enabled]
        if not enabled:
            return "INSUFFICIENT_EVIDENCE"

        avg_recall = sum(r.metrics.recall_success_rate for r in enabled) / max(1, len(enabled))
        avg_effectiveness = sum(
            r.metrics.semantic_stimulation_effectiveness for r in enabled
        ) / max(1, len(enabled))
        avg_consolidation = sum(
            r.metrics.semantic_consolidation_score for r in enabled
        ) / max(1, len(enabled))

        # Check for overactivation
        overactivation = any(
            r.metrics.energy_delta < -0.3 for r in enabled
        )
        if overactivation:
            return "SEMANTIC_OVERACTIVATION"

        # Check for global no effect
        all_same_cognitive = all(
            abs(r.metrics.cognitive_delta) < 0.01 for r in enabled
        )
        all_same_phi = all(
            abs(r.metrics.phi_delta) < 0.01 for r in enabled
        )
        has_assemblies = any(r.metrics.assembly_created_events > 0 for r in enabled)
        if has_assemblies and all_same_cognitive and all_same_phi and avg_recall == 0:
            return "SEMANTIC_GLOBAL_NO_EFFECT"

        # Check for discrimination failure
        discrimination_fail = all(
            r.metrics.semantic_discrimination_score < 0.1
            and r.metrics.assembly_created_events > 1
            for r in enabled
        )
        if discrimination_fail:
            return "SEMANTIC_DISCRIMINATION_FAILURE"

        # Check for consolidation weak
        consolidation_weak = all(
            r.metrics.assembly_consolidated_events == 0
            and r.metrics.assembly_created_events > 0
            for r in enabled
        )

        # Verdict ordering
        if avg_recall > 0.2 and avg_effectiveness > 0.25:
            # But check for regression
            cognitive_regression = any(
                r.metrics.cognitive_delta < -0.15 for r in enabled
            )
            phi_regression = any(
                r.metrics.phi_delta < -0.15 for r in enabled
            )
            if not cognitive_regression and not phi_regression:
                return "SEMANTIC_STIMULATION_VALIDATED"

        if consolidation_weak:
            return "SEMANTIC_CONSOLIDATION_WEAK"

        if 0 < avg_recall < 0.2:
            return "SEMANTIC_RECALL_WEAK"

        if has_assemblies and avg_recall == 0:
            return "SEMANTIC_ENCODING_ONLY"

        return "INSUFFICIENT_EVIDENCE"

    # ------------------------------------------------------------------ #
    # Reports
    # ------------------------------------------------------------------ #

    def _generate_json_report(self, suite: SemanticStimulationSuiteResult) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.report_dir / f"semantic_stimulation_{timestamp}.json"
        path.write_text(suite.model_dump_json(indent=2), encoding="utf-8")
        return path

    def _generate_markdown_report(self, suite: SemanticStimulationSuiteResult) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.report_dir / f"semantic_stimulation_{timestamp}.md"
        lines = [
            "# T43C — Semantic Benchmark Stimulation Redesign Report",
            "",
            f"**Audit ID:** {suite.audit_id}",
            f"**Created At:** {suite.created_at}",
            f"**Verdict:** {suite.verdict}",
            f"**Best Profile:** {suite.best_profile or 'None'}",
            f"**Worst Profile:** {suite.worst_profile or 'None'}",
            "",
            "## Baseline Profile",
            f"- **Profile:** {suite.baseline_result.profile.profile_name}",
            f"- **Assembly Created Events:** {suite.baseline_result.metrics.assembly_created_events}",
            f"- **Recall Success Rate:** {suite.baseline_result.metrics.recall_success_rate:.4f}",
            "",
            "## Profile Results",
            "",
            "| Profile | Created | Reinforced | Consolidated | Recall Rate | Partial | Stability | Discrim | Consolidation | Effectiveness | Cog Δ | Phi Δ | Passed |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for r in suite.profile_results:
            m = r.metrics
            lines.append(
                f"| {r.profile.profile_name} | {m.assembly_created_events} | {m.assembly_reinforced_events} | "
                f"{m.assembly_consolidated_events} | {m.recall_success_rate:.4f} | {m.partial_cue_success_rate:.4f} | "
                f"{m.mean_assembly_stability:.4f} | {m.semantic_discrimination_score:.4f} | "
                f"{m.semantic_consolidation_score:.4f} | {m.semantic_stimulation_effectiveness:.4f} | "
                f"{m.cognitive_delta:+.4f} | {m.phi_delta:+.4f} | {r.passed} |"
            )
        lines.extend([
            "",
            "---",
            "*Generated by T43C Semantic Stimulation Designer*",
        ])
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
