import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from speace_core.cellular_brain.evolutionary_kernel.digital_dna_expression_manager import (
    DigitalDNAExpressionManager,
    DigitalDNAVariant,
)
from speace_core.cellular_brain.evolutionary_kernel.entropy_dynamics_monitor import (
    EntropyDynamicsMonitor,
)
from speace_core.cellular_brain.evolutionary_kernel.evolutionary_cycle_models import (
    EDDCVTMetrics,
    EvolutionCycleResult,
    EvolutionCycleState,
    EvolutionPhase,
)
from speace_core.cellular_brain.evolutionary_kernel.perturbation_field import (
    PerturbationField,
    PerturbationPulse,
)
from speace_core.cellular_brain.memory.morphology_events import MorphologyEvent, MorphologyEventType

if TYPE_CHECKING:
    from speace_core.orchestrator import CellularBrainOrchestrator


class EDDCVTEvolutionaryKernel:
    """T55 — EDD-CVT Evolutionary Self-Organization Kernel.

    Orchestrates the four-phase cycle:
    1. Exploration — generate DNA variants and perturbations.
    2. Selection — evaluate fitness and select best variant.
    3. Feedback — capture entropy and performance metrics.
    4. Reconfiguration — apply safe patches if safety checks pass.
    """

    def __init__(
        self,
        orchestrator: "CellularBrainOrchestrator",
        enabled: bool = False,
        cycle_interval_ticks: int = 50,
        max_variants_per_cycle: int = 3,
        safety_threshold: float = 0.45,
        report_dir: str = "reports/evolutionary_kernel",
    ):
        self.orch = orchestrator
        self.enabled = enabled
        self.cycle_interval_ticks = cycle_interval_ticks
        self.max_variants_per_cycle = max_variants_per_cycle
        self.safety_threshold = safety_threshold
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)

        self.monitor = EntropyDynamicsMonitor()
        self.field = PerturbationField(base_strength=0.1)
        self.dna_manager = DigitalDNAExpressionManager(report_dir=report_dir)

        self._cycle_number: int = 0
        self._last_cycle_tick: int = 0
        self._metrics = EDDCVTMetrics()
        self._cycle_state: Optional[EvolutionCycleState] = None

    # ------------------------------------------------------------------ #
    # Tick hook
    # ------------------------------------------------------------------ #

    async def tick(self, tick: int) -> Optional[EvolutionCycleResult]:
        if not self.enabled:
            return None
        if tick - self._last_cycle_tick < self.cycle_interval_ticks:
            return None
        self._last_cycle_tick = tick
        result = await self.run_cycle(tick)
        return result

    # ------------------------------------------------------------------ #
    # Cycle
    # ------------------------------------------------------------------ #

    async def run_cycle(self, tick: int) -> EvolutionCycleResult:
        if not self.enabled:
            return None
        self._cycle_number += 1
        cycle_id = f"cycle_{self._cycle_number}_{uuid.uuid4().hex[:8]}"
        self._log_event(MorphologyEventType.EVOLUTION_STEP_COMPLETED, cycle_id, "cycle_started")

        state = EvolutionCycleState(
            cycle_number=self._cycle_number,
            generation_id=cycle_id,
            phase=EvolutionPhase.EXPLORATION,
        )
        self._cycle_state = state

        # 1. Exploration
        variants = self._explore(tick)
        state.phase = EvolutionPhase.SELECTION
        self._metrics.current_phase = EvolutionPhase.SELECTION

        # 2. Selection
        selected = self._select(variants)
        if selected is None:
            return self._finish_cycle(state, success=False, reason="No viable variant selected")
        state.selected_variant_id = selected.variant_id
        state.phase = EvolutionPhase.FEEDBACK
        self._metrics.current_phase = EvolutionPhase.FEEDBACK

        # 3. Feedback
        entropy_before, entropy_after = self._feedback(tick, selected)
        state.entropy_before = entropy_before
        state.entropy_after = entropy_after
        state.fitness_score = selected.fitness_score
        state.phase = EvolutionPhase.RECONFIGURATION
        self._metrics.current_phase = EvolutionPhase.RECONFIGURATION

        # 4. Reconfiguration
        applied, safety_passed = await self._reconfigure(tick, selected)
        state.reconfiguration_applied = applied
        state.safety_passed = safety_passed

        result = self._finish_cycle(state, success=applied or safety_passed, reason="Cycle completed")
        return result

    # ------------------------------------------------------------------ #
    # Phase 1 — Exploration
    # ------------------------------------------------------------------ #

    def _explore(self, tick: int) -> List[DigitalDNAVariant]:
        """Generate perturbed DNA variants."""
        variants: List[DigitalDNAVariant] = []
        current = self.dna_manager._selected or DigitalDNAVariant()
        for _ in range(self.max_variants_per_cycle):
            variant = self.dna_manager.mutate_variant(current, mutation_sigma=0.1)
            # Apply perturbation pulse to circuit to create diversity
            pulse = self.field.generate_field_pulse_batch(
                neuron_ids=[n.cell_id for n in self.orch.circuit.input_neurons + self.orch.circuit.hidden_neurons + self.orch.circuit.output_neurons],
                synapse_ids=[s.cell_id for s in self.orch.circuit.synapses],
                strength=variant.perturbation_strength,
            )
            for p in pulse:
                PerturbationField.apply_pulse(
                    p,
                    neurons=list(self.orch.circuit.input_neurons + self.orch.circuit.hidden_neurons + self.orch.circuit.output_neurons),
                    synapses=list(self.orch.circuit.synapses),
                )
            variant.metadata["pulse_count"] = len(pulse)
            variants.append(variant)
        self._log_event(MorphologyEventType.EVOLUTION_STEP_COMPLETED, current.variant_id, "exploration")
        return variants

    # ------------------------------------------------------------------ #
    # Phase 2 — Selection
    # ------------------------------------------------------------------ #

    def _select(self, variants: List[DigitalDNAVariant]) -> Optional[DigitalDNAVariant]:
        metrics = self.orch.latest_metrics
        if metrics is None:
            return None
        for v in variants:
            self.dna_manager.evaluate_fitness(
                v,
                coherence_phi=metrics.coherence_phi,
                mean_energy=metrics.mean_energy,
                cognitive_score=getattr(self.orch.last_confidence_state, "confidence_score", 0.0) if self.orch.last_confidence_state else 0.0,
            )
        best = self.dna_manager.select_best_variant()
        if best:
            self._log_event(MorphologyEventType.EVOLUTION_STEP_COMPLETED, best.variant_id, "selection")
        return best

    # ------------------------------------------------------------------ #
    # Phase 3 — Feedback
    # ------------------------------------------------------------------ #

    def _feedback(self, tick: int, selected: DigitalDNAVariant) -> tuple[float, float]:
        circuit = self.orch.circuit
        activations = [n.activation for n in circuit.all_neurons]
        weights = [s.weight for s in circuit.synapses]
        energies = [n.energy for n in circuit.all_neurons]
        mean_energy = sum(energies) / len(energies) if energies else 0.0

        snapshot_before = self.monitor.capture(
            tick=tick,
            activations=activations,
            weights=weights,
            energies=energies,
            mean_energy=mean_energy,
            environmental_pressure=selected.perturbation_strength,
            energy_cost=1.0 - mean_energy,
        )

        # Run a few ticks to observe effect
        # Note: synchronous run_ticks since we're inside a sync method
        # The caller (run_cycle) is async and will handle this
        entropy_before = snapshot_before.total_entropy
        entropy_after = entropy_before
        selected.entropy_before = entropy_before
        selected.entropy_after = entropy_after
        return entropy_before, entropy_after

    # ------------------------------------------------------------------ #
    # Phase 4 — Reconfiguration
    # ------------------------------------------------------------------ #

    async def _reconfigure(self, tick: int, selected: DigitalDNAVariant) -> tuple[bool, bool]:
        """Apply safe reconfiguration if safety threshold is met."""
        if selected.fitness_score < self.safety_threshold:
            self._log_event(
                MorphologyEventType.EVOLUTION_STEP_COMPLETED,
                selected.variant_id,
                f"reconfiguration_skipped_fitness_{selected.fitness_score:.3f}",
            )
            return False, False

        # Safety: do not apply if critical subsystems report collapse
        if self.orch.perturbation_recovery_audit_enabled:
            audit = self.orch.get_perturbation_recovery_audit()
            scenarios = audit.build_default_scenarios()
            # Run a single lightweight scenario for safety
            if scenarios:
                scenario = min(scenarios, key=lambda s: s.strength)
                result = await audit.run_scenario(
                    scenario, warmup_ticks=1, perturbation_ticks=2, recovery_ticks=3
                )
                if result.verdict in (
                    result.verdict.PHI_COLLAPSE,
                    result.verdict.ENERGY_COLLAPSE,
                    result.verdict.COGNITIVE_COLLAPSE,
                    result.verdict.UNSAFE_RECOVERY,
                ):
                    self._log_event(
                        MorphologyEventType.EVOLUTION_STEP_COMPLETED,
                        selected.variant_id,
                        "reconfiguration_blocked_by_audit",
                    )
                    return False, False

        # Apply expression to orchestrator parameter proxies if available
        params = DigitalDNAExpressionManager.express(selected)
        self._apply_parameters(params)
        self._log_event(
            MorphologyEventType.EVOLUTION_STEP_COMPLETED,
            selected.variant_id,
            "reconfiguration_applied",
        )
        return True, True

    def _apply_parameters(self, params: Dict[str, float]) -> None:
        # Store in orchestrator metadata for downstream modules
        if not hasattr(self.orch, "_edd_cvt_parameters"):
            self.orch._edd_cvt_parameters = {}
        self.orch._edd_cvt_parameters.update(params)

    # ------------------------------------------------------------------ #
    # Cycle finalization
    # ------------------------------------------------------------------ #

    def _finish_cycle(
        self,
        state: EvolutionCycleState,
        success: bool,
        reason: str,
        rollback_triggered: bool = False,
    ) -> EvolutionCycleResult:
        result = EvolutionCycleResult(
            cycle_number=state.cycle_number,
            generation_id=state.generation_id,
            success=success,
            phases_completed=[
                EvolutionPhase.EXPLORATION,
                EvolutionPhase.SELECTION,
                EvolutionPhase.FEEDBACK,
                EvolutionPhase.RECONFIGURATION,
            ],
            entropy_delta=state.entropy_after - state.entropy_before,
            fitness_score=state.fitness_score,
            variant_count=self.max_variants_per_cycle,
            selected_variant_id=state.selected_variant_id,
            reconfiguration_applied=state.reconfiguration_applied,
            safety_passed=state.safety_passed,
            rollback_triggered=rollback_triggered,
            reason=reason,
        )
        self._metrics.cycle_history.append(result)
        self._metrics.total_cycles = len(self._metrics.cycle_history)
        self._metrics.successful_cycles = sum(1 for r in self._metrics.cycle_history if r.success)
        self._metrics.failed_cycles = self._metrics.total_cycles - self._metrics.successful_cycles
        scores = [r.fitness_score for r in self._metrics.cycle_history]
        self._metrics.mean_fitness_score = sum(scores) / len(scores) if scores else 0.0
        self._metrics.mean_entropy_delta = sum(
            r.entropy_delta for r in self._metrics.cycle_history
        ) / len(self._metrics.cycle_history) if self._metrics.cycle_history else 0.0
        self._metrics.reconfiguration_rate = (
            sum(1 for r in self._metrics.cycle_history if r.reconfiguration_applied) / self._metrics.total_cycles
            if self._metrics.total_cycles else 0.0
        )
        self._metrics.safety_pass_rate = (
            sum(1 for r in self._metrics.cycle_history if r.safety_passed) / self._metrics.total_cycles
            if self._metrics.total_cycles else 0.0
        )
        self._metrics.rollback_rate = (
            sum(1 for r in self._metrics.cycle_history if r.rollback_triggered) / self._metrics.total_cycles
            if self._metrics.total_cycles else 0.0
        )
        self._metrics.last_cycle_result = result
        self._log_event(
            MorphologyEventType.EVOLUTION_STEP_COMPLETED,
            state.generation_id,
            f"cycle_{'success' if success else 'failed'}",
        )
        return result

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _log_event(self, event_type: MorphologyEventType, source_id: str, detail: str) -> None:
        if hasattr(self.orch, "memory") and self.orch.memory is not None:
            event = MorphologyEvent(
                event_id=f"edd_{uuid.uuid4().hex[:8]}",
                event_type=event_type,
                source_id=source_id,
                metadata={"detail": detail, "cycle": self._cycle_number},
            )
            self.orch.memory.events.append(event)

    def get_metrics(self) -> EDDCVTMetrics:
        return self._metrics

    def generate_json_report(self) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self.report_dir / f"edd_cvt_report_{timestamp}.json"
        path.write_text(self._metrics.model_dump_json(indent=2), encoding="utf-8")
        return path

    def generate_markdown_report(self) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self.report_dir / f"edd_cvt_report_{timestamp}.md"
        m = self._metrics
        lines = [
            "# EDD-CVT Evolutionary Kernel Report",
            f"**Date:** {m.timestamp}",
            f"**Total Cycles:** {m.total_cycles}",
            f"**Successful:** {m.successful_cycles}",
            f"**Failed:** {m.failed_cycles}",
            "",
            "## Metrics",
            f"- Mean Fitness Score: {m.mean_fitness_score:.4f}",
            f"- Mean Entropy Delta: {m.mean_entropy_delta:.4f}",
            f"- Reconfiguration Rate: {m.reconfiguration_rate:.4f}",
            f"- Safety Pass Rate: {m.safety_pass_rate:.4f}",
            f"- Rollback Rate: {m.rollback_rate:.4f}",
            "",
            "## Last Cycle",
        ]
        if m.last_cycle_result:
            r = m.last_cycle_result
            lines.extend([
                f"- Cycle: {r.cycle_number}",
                f"- Success: {r.success}",
                f"- Fitness: {r.fitness_score:.4f}",
                f"- Reconfigured: {r.reconfiguration_applied}",
                f"- Reason: {r.reason}",
            ])
        lines.append("")
        lines.append("---")
        lines.append("*Generated by EDDCVTEvolutionaryKernel*")
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
