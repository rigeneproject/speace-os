import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.self_organization.criticality_monitor import (
    CriticalityMonitor,
    CriticalityState,
)
from speace_core.cellular_brain.self_organization.emergence_metrics import (
    EmergenceMetrics,
)
from speace_core.cellular_brain.self_organization.perturbation_scheduler import (
    PerturbationResult,
    PerturbationScheduler,
)


class ControlAction(BaseModel):
    action_type: str
    reason: str
    parameter_changes: Dict[str, float] = Field(default_factory=dict)
    perturbation: Optional[PerturbationResult] = None


class SelfOrganizationController:
    """T53 — Maintain SPEACE near the edge of order and chaos."""

    def __init__(
        self,
        enabled: bool = False,
        monitor: Optional[CriticalityMonitor] = None,
        scheduler: Optional[PerturbationScheduler] = None,
        emergence: Optional[EmergenceMetrics] = None,
        report_dir: str = "reports/self_organization",
    ):
        self.enabled = enabled
        self.monitor = monitor or CriticalityMonitor()
        self.scheduler = scheduler or PerturbationScheduler(enabled=enabled)
        self.emergence = emergence or EmergenceMetrics()
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self._actions: List[ControlAction] = []
        self._parameter_state: Dict[str, float] = {
            "mutation_rate": 1.0,
            "routing_gain": 1.0,
            "plasticity_gain": 1.0,
            "inhibition_decay": 1.0,
            "neurogenesis_rate": 1.0,
        }
        self._perturbation_count: int = 0
        self._recovery_scores: List[float] = []

    # ------------------------------------------------------------------ #
    # Parameter modulation
    # ------------------------------------------------------------------ #

    def _modulate_parameters(
        self,
        criticality: CriticalityState,
    ) -> Dict[str, float]:
        state = criticality.state
        changes: Dict[str, float] = {}

        if state == "rigid":
            # Increase exploration
            changes["mutation_rate"] = min(2.0, self._parameter_state["mutation_rate"] * 1.2)
            changes["routing_gain"] = min(2.0, self._parameter_state["routing_gain"] * 1.1)
            changes["plasticity_gain"] = min(2.0, self._parameter_state["plasticity_gain"] * 1.15)
            changes["inhibition_decay"] = max(0.5, self._parameter_state["inhibition_decay"] * 0.9)
            changes["neurogenesis_rate"] = min(2.0, self._parameter_state["neurogenesis_rate"] * 1.1)
        elif state == "chaotic":
            # Increase selection and constraints
            changes["mutation_rate"] = max(0.2, self._parameter_state["mutation_rate"] * 0.7)
            changes["routing_gain"] = max(0.2, self._parameter_state["routing_gain"] * 0.85)
            changes["plasticity_gain"] = max(0.2, self._parameter_state["plasticity_gain"] * 0.8)
            changes["inhibition_decay"] = min(2.0, self._parameter_state["inhibition_decay"] * 1.2)
            changes["neurogenesis_rate"] = max(0.2, self._parameter_state["neurogenesis_rate"] * 0.9)
        elif state == "collapsing":
            # Emergency consolidation
            changes["mutation_rate"] = max(0.1, self._parameter_state["mutation_rate"] * 0.5)
            changes["routing_gain"] = max(0.2, self._parameter_state["routing_gain"] * 0.7)
            changes["plasticity_gain"] = max(0.1, self._parameter_state["plasticity_gain"] * 0.6)
            changes["inhibition_decay"] = min(2.0, self._parameter_state["inhibition_decay"] * 1.3)
            changes["neurogenesis_rate"] = max(0.1, self._parameter_state["neurogenesis_rate"] * 0.5)
        else:
            # Balanced: gentle drift toward center
            for key in self._parameter_state:
                current = self._parameter_state[key]
                if current > 1.05:
                    changes[key] = max(0.9, current * 0.98)
                elif current < 0.95:
                    changes[key] = min(1.1, current * 1.02)
                else:
                    changes[key] = current

        return changes

    def _apply_changes(self, changes: Dict[str, float]) -> None:
        for key, value in changes.items():
            self._parameter_state[key] = round(value, 4)

    # ------------------------------------------------------------------ #
    # Decision logic
    # ------------------------------------------------------------------ #

    def decide_action(self, criticality: CriticalityState) -> ControlAction:
        state = criticality.state
        if state == "rigid":
            return ControlAction(
                action_type="increase_exploration",
                reason=f"system_rigid (entropy={criticality.system_entropy:.3f})",
                parameter_changes=self._modulate_parameters(criticality),
            )
        elif state == "chaotic":
            return ControlAction(
                action_type="increase_selection",
                reason=f"system_chaotic (entropy={criticality.system_entropy:.3f})",
                parameter_changes=self._modulate_parameters(criticality),
            )
        elif state == "collapsing":
            return ControlAction(
                action_type="increase_constraints",
                reason=f"system_collapsing (instability={criticality.instability_mean:.3f})",
                parameter_changes=self._modulate_parameters(criticality),
            )
        else:
            return ControlAction(
                action_type="consolidate",
                reason=f"system_balanced (balance={criticality.order_chaos_balance:.3f})",
                parameter_changes=self._modulate_parameters(criticality),
            )

    def maybe_trigger_perturbation(self, criticality: CriticalityState) -> Optional[PerturbationResult]:
        if not self.enabled:
            return None
        if criticality.state == "rigid":
            return self.scheduler.apply_mutation_pulse(
                target="global", magnitude=0.15 + 0.05 * random.random()
            )
        elif criticality.state == "chaotic":
            return self.scheduler.apply_pathway_suppression(
                target="random", magnitude=0.2 + 0.1 * random.random()
            )
        return None

    # ------------------------------------------------------------------ #
    # Main cycle
    # ------------------------------------------------------------------ #

    def tick(
        self,
        neuron_activations: Optional[List[float]] = None,
        region_activations: Optional[Dict[str, float]] = None,
        inter_region_flow: Optional[Dict[str, float]] = None,
        pathway_strengths: Optional[List[float]] = None,
        previous_pathway_strengths: Optional[List[float]] = None,
        coherence_phi: float = 0.0,
        mean_energy: float = 0.0,
        plasticity_rate: float = 0.0,
        instability_mean: float = 0.0,
    ) -> Dict[str, Any]:
        # Update criticality
        criticality = self.monitor.update(
            neuron_activations=neuron_activations,
            region_activations=region_activations,
            inter_region_flow=inter_region_flow,
            pathway_strengths=pathway_strengths,
            previous_pathway_strengths=previous_pathway_strengths,
            coherence_phi=coherence_phi,
            mean_energy=mean_energy,
            plasticity_rate=plasticity_rate,
            instability_mean=instability_mean,
        )

        action = self.decide_action(criticality)
        self._apply_changes(action.parameter_changes)

        # Optionally trigger perturbation
        perturbation = self.maybe_trigger_perturbation(criticality)
        if perturbation is not None:
            action.perturbation = perturbation
            self._perturbation_count += 1

        # Expire old perturbations
        expired = self.scheduler.tick()
        for p in expired:
            # Compute recovery score placeholder; real integration would measure post-perturbation phi
            recovery = max(0.0, 1.0 - abs(criticality.coherence_phi - self.monitor.phi_baseline))
            p.recovery_score = round(recovery, 4)
            self._recovery_scores.append(recovery)

        self._actions.append(action)
        if len(self._actions) > 100:
            self._actions.pop(0)

        return {
            "criticality": criticality.model_dump(),
            "action": action.model_dump(),
            "parameter_state": dict(self._parameter_state),
            "perturbation_count": self._perturbation_count,
            "active_perturbations": self.scheduler.active_count,
        }

    # ------------------------------------------------------------------ #
    # A/B benchmark helpers
    # ------------------------------------------------------------------ #

    def benchmark_snapshot(self) -> Dict[str, Any]:
        latest = self.monitor.latest_state()
        return {
            "controller_enabled": self.enabled,
            "criticality_state": latest.state if latest else "unknown",
            "system_entropy": latest.system_entropy if latest else 0.0,
            "behavioral_diversity": latest.behavioral_diversity if latest else 0.0,
            "modularity_score": latest.modularity_score if latest else 0.0,
            "order_chaos_balance": latest.order_chaos_balance if latest else 0.0,
            "perturbation_count": self._perturbation_count,
            "recovery_after_perturbation": round(
                sum(self._recovery_scores) / len(self._recovery_scores), 4
            ) if self._recovery_scores else 0.0,
            "mean_recovery_score": round(
                sum(self._recovery_scores) / len(self._recovery_scores), 4
            ) if self._recovery_scores else 0.0,
            "parameter_state": dict(self._parameter_state),
            "self_organization_score": self.emergence.latest().get("self_organization_score", 0.0)
            if self.emergence.latest() else 0.0,
            "emergent_structure_gain": self.emergence.latest().get("modularity_gain", 0.0)
            if self.emergence.latest() else 0.0,
        }

    # ------------------------------------------------------------------ #
    # Report generation
    # ------------------------------------------------------------------ #

    def generate_markdown_report(self) -> str:
        snap = self.benchmark_snapshot()
        lines = [
            "# Self-Organization Controller Report — T53",
            "",
            f"- **Controller Enabled:** {snap['controller_enabled']}",
            f"- **Criticality State:** {snap['criticality_state']}",
            f"- **System Entropy:** {snap['system_entropy']:.4f}",
            f"- **Behavioral Diversity:** {snap['behavioral_diversity']:.4f}",
            f"- **Modularity Score:** {snap['modularity_score']:.4f}",
            f"- **Order/Chaos Balance:** {snap['order_chaos_balance']:.4f}",
            f"- **Perturbation Count:** {snap['perturbation_count']}",
            f"- **Recovery After Perturbation:** {snap['recovery_after_perturbation']:.4f}",
            f"- **Self-Organization Score:** {snap['self_organization_score']:.4f}",
            f"- **Emergent Structure Gain:** {snap['emergent_structure_gain']:.4f}",
            "",
            "## Parameter State",
        ]
        for k, v in snap["parameter_state"].items():
            lines.append(f"- {k}: {v:.4f}")
        lines.extend(["", f"*Generated at {datetime.now(timezone.utc).isoformat()}*"])
        return "\n".join(lines) + "\n"

    def generate_json_report(self) -> str:
        return json.dumps(self.benchmark_snapshot(), indent=2, ensure_ascii=False)

    def save_reports(self) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        base = f"self_organization_{timestamp}"
        md_path = self.report_dir / f"{base}.md"
        md_path.write_text(self.generate_markdown_report(), encoding="utf-8")
        json_path = self.report_dir / f"{base}.json"
        json_path.write_text(self.generate_json_report(), encoding="utf-8")

    # ------------------------------------------------------------------ #
    # Reset
    # ------------------------------------------------------------------ #

    def reset(self) -> None:
        self._actions.clear()
        self._perturbation_count = 0
        self._recovery_scores.clear()
        self._parameter_state = {
            "mutation_rate": 1.0,
            "routing_gain": 1.0,
            "plasticity_gain": 1.0,
            "inhibition_decay": 1.0,
            "neurogenesis_rate": 1.0,
        }
        self.monitor = CriticalityMonitor()
        self.scheduler = PerturbationScheduler(enabled=self.enabled)
        self.emergence = EmergenceMetrics()


import random
