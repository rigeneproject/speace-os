from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.memory.morphology_events import (
    MorphologyEvent,
    MorphologyEventType,
)

if TYPE_CHECKING:
    from speace_core.orchestrator import CellularBrainOrchestrator


class PerturbationKind(str, Enum):
    ACTIVATION_SPIKE = "activation_spike"
    ENERGY_SCARCITY = "energy_scarcity"
    ROUTING_OVERLOAD = "routing_overload"
    PLASTICITY_OVERDRIVE = "plasticity_overdrive"
    SEMANTIC_NOISE = "semantic_noise"
    MIXED_STRESS = "mixed_stress"


class PerturbationScenario(BaseModel):
    name: str
    kind: PerturbationKind
    strength: float = Field(default=0.5, ge=0.0, le=1.0)
    duration_ticks: int = Field(default=5, ge=1)
    target_region: Optional[str] = None
    target_metric: Optional[str] = None
    reversible: bool = True
    metadata: Dict[str, float] = Field(default_factory=dict)


class PerturbationTracePoint(BaseModel):
    tick: int
    coherence_phi: float = 0.0
    energy_efficiency: float = 0.0
    cognitive_score: float = 0.0
    criticality_score: float = 0.0
    instability_score: float = 0.0
    mean_activation: float = 0.0
    suppression_level: float = 0.0
    recovery_policy_state: Optional[str] = None


class PerturbationVerdict(str, Enum):
    PERTURBATION_RECOVERY_VALIDATED = "PERTURBATION_RECOVERY_VALIDATED"
    RECOVERY_PARTIAL = "RECOVERY_PARTIAL"
    RECOVERY_SLOW = "RECOVERY_SLOW"
    PHI_COLLAPSE = "PHI_COLLAPSE"
    ENERGY_COLLAPSE = "ENERGY_COLLAPSE"
    COGNITIVE_COLLAPSE = "COGNITIVE_COLLAPSE"
    OVER_SUPPRESSION = "OVER_SUPPRESSION"
    PERTURBATION_NO_EFFECT = "PERTURBATION_NO_EFFECT"
    UNSAFE_RECOVERY = "UNSAFE_RECOVERY"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class PerturbationRecoveryResult(BaseModel):
    scenario_name: str
    baseline_phi: float = 0.0
    final_phi: float = 0.0
    baseline_energy: float = 0.0
    final_energy: float = 0.0
    baseline_cognitive: float = 0.0
    final_cognitive: float = 0.0
    instability_peak: float = 0.0
    recovery_latency_ticks: int = 0
    phi_recovery_score: float = 0.0
    energy_recovery_score: float = 0.0
    cognitive_preservation_score: float = 0.0
    criticality_return_score: float = 0.0
    suppression_cost: float = 0.0
    post_perturbation_recovery_score: float = 0.0
    rollback_needed: bool = False
    collapse_detected: bool = False
    verdict: PerturbationVerdict = PerturbationVerdict.INSUFFICIENT_EVIDENCE
    trace: List[PerturbationTracePoint] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ControlledPerturbationRecoveryAudit:
    """Audit that subjects SPEACE to controlled perturbations and measures recovery."""

    def __init__(self, orchestrator: "CellularBrainOrchestrator", seed: int = 42):
        self.orch = orchestrator
        self.seed = seed
        self._results: List[PerturbationRecoveryResult] = []

    # ------------------------------------------------------------------ #
    # Scenario factory
    # ------------------------------------------------------------------ #

    def build_default_scenarios(self) -> List[PerturbationScenario]:
        return [
            PerturbationScenario(
                name="activation_spike_default",
                kind=PerturbationKind.ACTIVATION_SPIKE,
                strength=0.7,
                duration_ticks=5,
                target_region=None,
                reversible=True,
            ),
            PerturbationScenario(
                name="energy_scarcity_default",
                kind=PerturbationKind.ENERGY_SCARCITY,
                strength=0.6,
                duration_ticks=5,
                reversible=True,
            ),
            PerturbationScenario(
                name="routing_overload_default",
                kind=PerturbationKind.ROUTING_OVERLOAD,
                strength=0.6,
                duration_ticks=5,
                reversible=True,
            ),
            PerturbationScenario(
                name="plasticity_overdrive_default",
                kind=PerturbationKind.PLASTICITY_OVERDRIVE,
                strength=0.5,
                duration_ticks=5,
                reversible=True,
            ),
            PerturbationScenario(
                name="semantic_noise_default",
                kind=PerturbationKind.SEMANTIC_NOISE,
                strength=0.4,
                duration_ticks=5,
                reversible=True,
            ),
            PerturbationScenario(
                name="mixed_stress_default",
                kind=PerturbationKind.MIXED_STRESS,
                strength=0.7,
                duration_ticks=7,
                reversible=True,
            ),
        ]

    # ------------------------------------------------------------------ #
    # Perturbation application
    # ------------------------------------------------------------------ #

    def apply_perturbation(self, scenario: PerturbationScenario) -> None:
        circuit = self.orch.circuit
        if scenario.kind == PerturbationKind.ACTIVATION_SPIKE:
            for n in circuit.hidden_neurons:
                n.activation = min(1.0, n.activation + scenario.strength)
        elif scenario.kind == PerturbationKind.ENERGY_SCARCITY:
            for n in circuit.input_neurons + circuit.hidden_neurons + circuit.output_neurons:
                n.energy = max(0.1, n.energy - scenario.strength)
        elif scenario.kind == PerturbationKind.ROUTING_OVERLOAD:
            if self.orch.region_signal_routing_enabled and self.orch._region_signal_router is not None:
                router = self.orch._region_signal_router
                original = getattr(router, "_overload_injected", False)
                if not original:
                    router._overload_injected = True
                    router._overload_strength = scenario.strength
        elif scenario.kind == PerturbationKind.PLASTICITY_OVERDRIVE:
            for s in circuit.synapses:
                s.weight = min(1.0, s.weight + scenario.strength * 0.1)
        elif scenario.kind == PerturbationKind.SEMANTIC_NOISE:
            store = getattr(self.orch, "_semantic_memory_store", None)
            if store is not None:
                from speace_core.cellular_brain.memory.semantic.cell_assembly import CellAssembly
                noise_assembly = CellAssembly(
                    assembly_id=f"noise_{scenario.name}",
                    signature=[0.1] * 10,
                    strength=scenario.strength,
                )
                store._assemblies[noise_assembly.assembly_id] = noise_assembly
        elif scenario.kind == PerturbationKind.MIXED_STRESS:
            for n in circuit.hidden_neurons:
                n.activation = min(1.0, n.activation + scenario.strength * 0.5)
                n.energy = max(0.1, n.energy - scenario.strength * 0.3)
            for s in circuit.synapses:
                s.weight = min(1.0, s.weight + scenario.strength * 0.05)

    def reverse_perturbation(self, scenario: PerturbationScenario) -> None:
        if not scenario.reversible:
            return
        circuit = self.orch.circuit
        if scenario.kind == PerturbationKind.ACTIVATION_SPIKE:
            for n in circuit.hidden_neurons:
                n.activation = max(0.0, n.activation - scenario.strength)
        elif scenario.kind == PerturbationKind.ENERGY_SCARCITY:
            for n in circuit.input_neurons + circuit.hidden_neurons + circuit.output_neurons:
                n.energy = min(1.0, n.energy + scenario.strength)
        elif scenario.kind == PerturbationKind.ROUTING_OVERLOAD:
            if self.orch.region_signal_routing_enabled and self.orch._region_signal_router is not None:
                router = self.orch._region_signal_router
                if getattr(router, "_overload_injected", False):
                    router._overload_injected = False
                    router._overload_strength = 0.0
        elif scenario.kind == PerturbationKind.PLASTICITY_OVERDRIVE:
            for s in circuit.synapses:
                s.weight = max(0.0, s.weight - scenario.strength * 0.1)
        elif scenario.kind == PerturbationKind.SEMANTIC_NOISE:
            store = getattr(self.orch, "_semantic_memory_store", None)
            if store is not None:
                key = f"noise_{scenario.name}"
                store._assemblies.pop(key, None)
        elif scenario.kind == PerturbationKind.MIXED_STRESS:
            for n in circuit.hidden_neurons:
                n.activation = max(0.0, n.activation - scenario.strength * 0.5)
                n.energy = min(1.0, n.energy + scenario.strength * 0.3)
            for s in circuit.synapses:
                s.weight = max(0.0, s.weight - scenario.strength * 0.05)

    # ------------------------------------------------------------------ #
    # Capture
    # ------------------------------------------------------------------ #

    def capture_trace_point(self, tick: int) -> PerturbationTracePoint:
        metrics = self.orch.latest_metrics
        phi = metrics.coherence_phi if metrics else 0.0
        energy = metrics.mean_energy if metrics else 0.0
        all_neurons = (
            self.orch.circuit.input_neurons
            + self.orch.circuit.hidden_neurons
            + self.orch.circuit.output_neurons
        )
        mean_activation = sum(n.activation for n in all_neurons) / len(all_neurons) if all_neurons else 0.0
        suppression = 0.0
        if self.orch.brainstem_controller_enabled and self.orch._brainstem_controller is not None:
            last = getattr(self.orch, "_last_brainstem_result", None)
            if last is not None:
                suppression = getattr(last.decision, "routing_suppression_multiplier", 1.0)
        criticality = 0.0
        if self.orch.community_detection_enabled and self.orch.last_community_result is not None:
            criticality = getattr(self.orch.last_community_result, "modularity_proxy", 0.0)
        instability = 0.0
        if self.orch.region_stability_controller_enabled and self.orch._region_stability_controller is not None:
            summary = self.orch._region_stability_controller.summarize_stability()
            instability = summary.get("mean_instability", 0.0)
        return PerturbationTracePoint(
            tick=tick,
            coherence_phi=phi,
            energy_efficiency=energy,
            cognitive_score=getattr(self.orch.last_confidence_state, "confidence_score", 0.0) if self.orch.last_confidence_state else 0.0,
            criticality_score=criticality,
            instability_score=instability,
            mean_activation=mean_activation,
            suppression_level=suppression,
            recovery_policy_state=None,
        )

    # ------------------------------------------------------------------ #
    # Run scenario
    # ------------------------------------------------------------------ #

    async def run_scenario(
        self,
        scenario: PerturbationScenario,
        warmup_ticks: int = 3,
        perturbation_ticks: int = 5,
        recovery_ticks: int = 12,
    ) -> PerturbationRecoveryResult:
        trace: List[PerturbationTracePoint] = []

        # Warmup
        for _ in range(warmup_ticks):
            await self.orch.run_ticks(1)
            trace.append(self.capture_trace_point(self.orch.current_tick))

        baseline = trace[-1] if trace else self.capture_trace_point(self.orch.current_tick)

        # Perturbation
        self.apply_perturbation(scenario)
        for i in range(perturbation_ticks):
            await self.orch.run_ticks(1)
            trace.append(self.capture_trace_point(self.orch.current_tick))

        # Reverse + recovery
        self.reverse_perturbation(scenario)
        for _ in range(recovery_ticks):
            await self.orch.run_ticks(1)
            trace.append(self.capture_trace_point(self.orch.current_tick))

        final = trace[-1] if trace else self.capture_trace_point(self.orch.current_tick)

        instability_peak = max((t.instability_score for t in trace), default=0.0)
        suppression_cost = sum(t.suppression_level for t in trace) / len(trace) if trace else 0.0

        phi_recovery_score = max(0.0, 1.0 - abs(final.coherence_phi - baseline.coherence_phi))
        energy_recovery_score = max(0.0, 1.0 - abs(final.energy_efficiency - baseline.energy_efficiency))
        cognitive_preservation_score = (
            final.cognitive_score / baseline.cognitive_score if baseline.cognitive_score > 0 else 0.0
        )
        criticality_return_score = max(0.0, 1.0 - abs(final.criticality_score - baseline.criticality_score))

        post_perturbation_recovery_score = (
            0.30 * phi_recovery_score
            + 0.25 * energy_recovery_score
            + 0.25 * cognitive_preservation_score
            + 0.15 * criticality_return_score
            - 0.05 * suppression_cost
        )
        post_perturbation_recovery_score = max(0.0, min(1.0, post_perturbation_recovery_score))

        collapse_detected = (
            final.coherence_phi < baseline.coherence_phi * 0.60
            or final.energy_efficiency < baseline.energy_efficiency * 0.60
        )

        recovery_latency = 0
        for i, t in enumerate(trace):
            if t.coherence_phi >= baseline.coherence_phi * 0.90:
                recovery_latency = max(0, i - warmup_ticks)
                break

        verdict = self.compute_verdict(
            post_perturbation_recovery_score=post_perturbation_recovery_score,
            collapse_detected=collapse_detected,
            baseline_phi=baseline.coherence_phi,
            final_phi=final.coherence_phi,
            baseline_cognitive=baseline.cognitive_score,
            final_cognitive=final.cognitive_score,
            suppression_cost=suppression_cost,
        )

        result = PerturbationRecoveryResult(
            scenario_name=scenario.name,
            baseline_phi=baseline.coherence_phi,
            final_phi=final.coherence_phi,
            baseline_energy=baseline.energy_efficiency,
            final_energy=final.energy_efficiency,
            baseline_cognitive=baseline.cognitive_score,
            final_cognitive=final.cognitive_score,
            instability_peak=instability_peak,
            recovery_latency_ticks=recovery_latency,
            phi_recovery_score=phi_recovery_score,
            energy_recovery_score=energy_recovery_score,
            cognitive_preservation_score=cognitive_preservation_score,
            criticality_return_score=criticality_return_score,
            suppression_cost=suppression_cost,
            post_perturbation_recovery_score=post_perturbation_recovery_score,
            rollback_needed=False,
            collapse_detected=collapse_detected,
            verdict=verdict,
            trace=trace,
        )
        self._results.append(result)
        return result

    # ------------------------------------------------------------------ #
    # Verdict
    # ------------------------------------------------------------------ #

    @staticmethod
    def compute_verdict(
        post_perturbation_recovery_score: float,
        collapse_detected: bool,
        baseline_phi: float,
        final_phi: float,
        baseline_cognitive: float,
        final_cognitive: float,
        suppression_cost: float,
    ) -> PerturbationVerdict:
        if collapse_detected:
            if final_phi < baseline_phi * 0.60:
                return PerturbationVerdict.PHI_COLLAPSE
            return PerturbationVerdict.ENERGY_COLLAPSE
        if post_perturbation_recovery_score >= 0.65 and not collapse_detected:
            if final_phi >= baseline_phi * 0.85 and final_cognitive >= baseline_cognitive * 0.85:
                return PerturbationVerdict.PERTURBATION_RECOVERY_VALIDATED
        if post_perturbation_recovery_score >= 0.45 and not collapse_detected:
            return PerturbationVerdict.RECOVERY_PARTIAL
        cognitive_preservation_score = (
            final_cognitive / baseline_cognitive if baseline_cognitive > 0 else 0.0
        )
        if cognitive_preservation_score < 0.75 and suppression_cost > 1.2:
            return PerturbationVerdict.OVER_SUPPRESSION
        if post_perturbation_recovery_score < 0.05:
            return PerturbationVerdict.PERTURBATION_NO_EFFECT
        return PerturbationVerdict.INSUFFICIENT_EVIDENCE

    # ------------------------------------------------------------------ #
    # Suite
    # ------------------------------------------------------------------ #

    async def run_audit_suite(self) -> List[PerturbationRecoveryResult]:
        scenarios = self.build_default_scenarios()
        results: List[PerturbationRecoveryResult] = []
        for scenario in scenarios:
            result = await self.run_scenario(scenario)
            results.append(result)
        return results

    # ------------------------------------------------------------------ #
    # Reports
    # ------------------------------------------------------------------ #

    def generate_json_report(self, results: List[PerturbationRecoveryResult]) -> str:
        data = [r.model_dump() for r in results]
        import json
        return json.dumps(data, indent=2)

    def generate_markdown_report(self, results: List[PerturbationRecoveryResult]) -> str:
        lines = [
            "# Controlled Perturbation & Recovery Audit Report",
            f"**Date:** {datetime.now(timezone.utc).isoformat()}",
            f"**Scenarios:** {len(results)}",
            "",
            "## Summary",
            "| Scenario | Verdict | Recovery Score | Phi (base→final) | Energy (base→final) |",
            "|---|---|---|---|---|",
        ]
        for r in results:
            lines.append(
                f"| {r.scenario_name} | {r.verdict.value} | {r.post_perturbation_recovery_score:.3f} |"
                f" {r.baseline_phi:.3f} → {r.final_phi:.3f} | {r.baseline_energy:.3f} → {r.final_energy:.3f} |"
            )
        lines.append("")
        lines.append("## Details")
        for r in results:
            lines.extend([
                f"### {r.scenario_name}",
                f"- Verdict: {r.verdict.value}",
                f"- Recovery Score: {r.post_perturbation_recovery_score:.4f}",
                f"- Phi Recovery: {r.phi_recovery_score:.4f}",
                f"- Energy Recovery: {r.energy_recovery_score:.4f}",
                f"- Cognitive Preservation: {r.cognitive_preservation_score:.4f}",
                f"- Instability Peak: {r.instability_peak:.4f}",
                f"- Recovery Latency: {r.recovery_latency_ticks} ticks",
                f"- Collapse Detected: {r.collapse_detected}",
                "",
            ])
        lines.append("---")
        lines.append("*Generated by ControlledPerturbationRecoveryAudit*")
        return "\n".join(lines)
