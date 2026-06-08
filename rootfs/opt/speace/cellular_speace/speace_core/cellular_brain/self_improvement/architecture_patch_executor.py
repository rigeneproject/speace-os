import copy
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.memory.morphology_events import MorphologyEvent, MorphologyEventType
from speace_core.cellular_brain.self_improvement.patch_snapshot_store import PatchSnapshot, PatchSnapshotStore


class ArchitecturePatch(BaseModel):
    patch_id: str
    proposal_id: str
    limitation_type: str
    patch_type: str
    target_path: str
    operation: str  # "set", "scale", "enable", "disable", "profile_select"
    old_value: Any = None
    new_value: Any = None
    safety_class: str = "low"
    requires_guard: bool = True


class PatchExecutionResult(BaseModel):
    patch_id: str
    proposal_id: str
    applied: bool = False
    confirmed: bool = False
    rolled_back: bool = False
    verdict: str = "PATCH_NEEDS_MORE_EVIDENCE"
    pre_score: float = 0.0
    post_score: float = 0.0
    delta_score: float = 0.0
    delta_phi: float = 0.0
    delta_energy: float = 0.0
    regression_flags: List[str] = Field(default_factory=list)
    report_path: Optional[str] = None


class ArchitecturePatchExecutor:
    """T50 — Safe Architecture Patch Execution with snapshot and rollback."""

    ALLOWED_FLAGS = {
        "semantic_memory_enabled",
        "associative_memory_enabled",
        "episodic_policy_enabled",
        "counterfactual_sandbox_enabled",
        "brainstem_controller_enabled",
        "region_stability_controller_enabled",
        "architecture_patch_execution_enabled",
    }

    ALLOWED_PROFILES = {
        "recovery_policy_profile",
        "energy_control_profile",
        "brainstem_gain_profile",
        "routing_profile",
        "plasticity_tuning_profile",
    }

    ALLOWED_NUMERIC = {
        "learning_rate",
        "plasticity_rate",
        "decay_rate",
        "routing_gain",
        "inhibition_decay",
        "semantic_similarity_threshold",
        "assembly_consolidation_threshold",
    }

    def __init__(
        self,
        orchestrator=None,
        benchmark=None,
        regression_guard=None,
        snapshot_store: Optional[PatchSnapshotStore] = None,
        memory=None,
    ):
        self.orchestrator = orchestrator
        self.benchmark = benchmark
        self.regression_guard = regression_guard
        self.snapshot_store = snapshot_store or PatchSnapshotStore()
        self.memory = memory

    # ------------------------------------------------------------------ #
    # Build patch from proposal
    # ------------------------------------------------------------------ #

    def build_patch_from_proposal(self, proposal) -> ArchitecturePatch:
        patch_type = self._infer_patch_type(proposal)
        target_path = self._infer_target_path(proposal)
        operation = self._infer_operation(proposal)
        new_value = self._infer_new_value(proposal)

        return ArchitecturePatch(
            patch_id=f"patch-{uuid.uuid4().hex[:8]}",
            proposal_id=getattr(proposal, "id", "unknown"),
            limitation_type=getattr(proposal, "primary_category", "unknown") if hasattr(proposal, "primary_category") else getattr(proposal, "limitation_type", "unknown"),
            patch_type=patch_type,
            target_path=target_path,
            operation=operation,
            old_value=None,
            new_value=new_value,
            safety_class="low" if patch_type in ("flag", "numeric") else "medium",
            requires_guard=True,
        )

    def _infer_patch_type(self, proposal) -> str:
        ptype = getattr(proposal, "proposal_type", "parameter_tuning")
        if ptype in ("parameter_tuning", "module_refactor"):
            return "flag"
        if ptype == "module_addition":
            return "profile_select"
        if ptype in ("routing_redesign", "plasticity_redesign"):
            return "profile_select"
        return "flag"

    def _infer_target_path(self, proposal) -> str:
        modules = getattr(proposal, "target_modules", [])
        if not modules:
            return "unknown"
        first = modules[0]
        if "energy" in first:
            return "energy_control_enabled"
        if "routing" in first or "router" in first:
            return "region_signal_routing_enabled"
        if "stability" in first:
            return "region_stability_controller_enabled"
        if "brainstem" in first:
            return "brainstem_controller_enabled"
        if "semantic" in first:
            return "semantic_memory_enabled"
        if "plasticity" in first:
            return "plasticity_rate"
        return modules[0]

    def _infer_operation(self, proposal) -> str:
        ptype = getattr(proposal, "proposal_type", "parameter_tuning")
        if ptype == "parameter_tuning":
            return "scale"
        if ptype == "module_addition":
            return "enable"
        if ptype == "module_refactor":
            return "set"
        return "set"

    def _infer_new_value(self, proposal) -> Any:
        benefits = getattr(proposal, "expected_benefits", {})
        if benefits:
            return round(list(benefits.values())[0], 4)
        return True

    # ------------------------------------------------------------------ #
    # Safety validation
    # ------------------------------------------------------------------ #

    def validate_patch_safety(self, patch: ArchitecturePatch) -> bool:
        if patch.operation in ("set", "scale", "enable", "disable"):
            if patch.target_path in self.ALLOWED_FLAGS or patch.target_path in self.ALLOWED_NUMERIC:
                return True
        if patch.operation == "profile_select" and patch.target_path in self.ALLOWED_PROFILES:
            return True
        if patch.safety_class not in {"low", "medium"}:
            return False
        return False

    # ------------------------------------------------------------------ #
    # Snapshot creation
    # ------------------------------------------------------------------ #

    def create_pre_patch_snapshot(self, patch: ArchitecturePatch) -> PatchSnapshot:
        orch = self.orchestrator
        flags = {}
        if orch is not None:
            for attr in self.ALLOWED_FLAGS:
                if hasattr(orch, attr):
                    flags[attr] = getattr(orch, attr)
            for attr in self.ALLOWED_NUMERIC:
                if hasattr(orch, attr):
                    flags[attr] = getattr(orch, attr)

        benchmark_baseline = {}
        if self.benchmark is not None:
            bm = getattr(orch, "latest_metrics", None)
            if bm is not None:
                benchmark_baseline = {
                    "coherence_phi": getattr(bm, "coherence_phi", 0.0),
                    "mean_energy": getattr(bm, "mean_energy", 0.0),
                    "accuracy": getattr(bm, "accuracy", 0.0),
                }

        snapshot = PatchSnapshot(
            snapshot_id=f"snap-{uuid.uuid4().hex[:8]}",
            patch_id=patch.patch_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            genome_snapshot={},
            orchestrator_flags=flags,
            region_state={},
            energy_state={},
            benchmark_baseline=benchmark_baseline,
        )
        self.snapshot_store.save_snapshot(snapshot)
        self._log_event(
            MorphologyEventType.ARCHITECTURE_PATCH_SNAPSHOT_CREATED,
            {"patch_id": patch.patch_id, "snapshot_id": snapshot.snapshot_id},
        )
        return snapshot

    # ------------------------------------------------------------------ #
    # Apply patch
    # ------------------------------------------------------------------ #

    def apply_patch(self, patch: ArchitecturePatch) -> bool:
        if not self.validate_patch_safety(patch):
            return False
        orch = self.orchestrator
        if orch is None:
            return False

        target = patch.target_path
        if patch.operation == "set":
            if hasattr(orch, target):
                setattr(orch, target, patch.new_value)
                return True
        elif patch.operation == "scale":
            if hasattr(orch, target):
                current = getattr(orch, target)
                if type(current) in (int, float) and type(patch.new_value) in (int, float):
                    setattr(orch, target, current * patch.new_value)
                    return True
        elif patch.operation == "enable":
            if hasattr(orch, target) and isinstance(getattr(orch, target), bool):
                setattr(orch, target, True)
                return True
        elif patch.operation == "disable":
            if hasattr(orch, target) and isinstance(getattr(orch, target), bool):
                setattr(orch, target, False)
                return True
        elif patch.operation == "profile_select":
            if target in self.ALLOWED_PROFILES:
                setattr(orch, target, patch.new_value)
                return True
        return False

    # ------------------------------------------------------------------ #
    # Post-patch validation
    # ------------------------------------------------------------------ #

    def run_post_patch_validation(self, patch: ArchitecturePatch) -> PatchExecutionResult:
        pre_score = 0.0
        pre_phi = 0.0
        pre_energy = 0.0
        snapshot = self.snapshot_store.load_snapshot(patch.patch_id)
        if snapshot is not None:
            baseline = snapshot.benchmark_baseline
            pre_score = baseline.get("accuracy", 0.0)
            pre_phi = baseline.get("coherence_phi", 0.0)
            pre_energy = baseline.get("mean_energy", 0.0)

        post_score = 0.0
        post_phi = 0.0
        post_energy = 0.0
        orch = self.orchestrator
        if orch is not None:
            bm = getattr(orch, "latest_metrics", None)
            if bm is not None:
                post_score = getattr(bm, "accuracy", 0.0)
                post_phi = getattr(bm, "coherence_phi", 0.0)
                post_energy = getattr(bm, "mean_energy", 0.0)

        delta_score = round(post_score - pre_score, 4)
        delta_phi = round(post_phi - pre_phi, 4)
        delta_energy = round(post_energy - pre_energy, 4)

        regression_flags: List[str] = []
        rg_verdict = "POLICY_SAFE"
        if self.regression_guard is not None and hasattr(self.regression_guard, "evaluate"):
            try:
                rg_result = self.regression_guard.evaluate({
                    "cognitive_score_delta": delta_score,
                    "coherence_phi_delta": delta_phi,
                    "energy_efficiency_delta": delta_energy,
                })
                rg_verdict = getattr(rg_result, "verdict", "POLICY_SAFE")
            except Exception:
                rg_verdict = "POLICY_SAFE"
        if rg_verdict == "POLICY_UNSAFE":
            regression_flags.append("POLICY_UNSAFE")

        if delta_score < -0.05:
            regression_flags.append("SCORE_REGRESSION")
        if delta_phi < -0.05:
            regression_flags.append("PHI_REGRESSION")
        if delta_energy < -0.1:
            regression_flags.append("ENERGY_REGRESSION")

        verdict = self._compute_verdict(delta_score, delta_phi, delta_energy, regression_flags)

        return PatchExecutionResult(
            patch_id=patch.patch_id,
            proposal_id=patch.proposal_id,
            applied=True,
            confirmed=verdict == "PATCH_CONFIRMED",
            rolled_back=verdict == "PATCH_ROLLED_BACK",
            verdict=verdict,
            pre_score=round(pre_score, 4),
            post_score=round(post_score, 4),
            delta_score=delta_score,
            delta_phi=delta_phi,
            delta_energy=delta_energy,
            regression_flags=regression_flags,
        )

    @staticmethod
    def _compute_verdict(
        delta_score: float,
        delta_phi: float,
        delta_energy: float,
        regression_flags: List[str],
    ) -> str:
        if "POLICY_UNSAFE" in regression_flags:
            return "PATCH_ROLLED_BACK"
        if "SCORE_REGRESSION" in regression_flags or "PHI_REGRESSION" in regression_flags or "ENERGY_REGRESSION" in regression_flags:
            return "PATCH_ROLLED_BACK"
        if delta_score >= 0.01 or delta_phi >= 0.01 or delta_energy >= 0.01:
            return "PATCH_CONFIRMED"
        if delta_score >= 0.0 and delta_phi >= -0.02 and delta_energy >= -0.05:
            return "PATCH_NEEDS_MORE_EVIDENCE"
        return "PATCH_ROLLED_BACK"

    # ------------------------------------------------------------------ #
    # Rollback
    # ------------------------------------------------------------------ #

    def rollback_patch(self, patch: ArchitecturePatch, snapshot: PatchSnapshot) -> bool:
        orch = self.orchestrator
        if orch is None:
            return False
        flags = snapshot.orchestrator_flags
        for attr, value in flags.items():
            if hasattr(orch, attr):
                setattr(orch, attr, value)
        return True

    # ------------------------------------------------------------------ #
    # Execute full pipeline
    # ------------------------------------------------------------------ #

    def execute_patch(self, proposal) -> PatchExecutionResult:
        patch = self.build_patch_from_proposal(proposal)
        self._log_event(
            MorphologyEventType.ARCHITECTURE_PATCH_PROPOSED,
            {"patch_id": patch.patch_id, "proposal_id": patch.proposal_id, "target_path": patch.target_path},
        )

        if not self.validate_patch_safety(patch):
            self._log_event(
                MorphologyEventType.ARCHITECTURE_PATCH_REJECTED,
                {"patch_id": patch.patch_id, "reason": "safety_validation_failed"},
            )
            return PatchExecutionResult(
                patch_id=patch.patch_id,
                proposal_id=patch.proposal_id,
                applied=False,
                confirmed=False,
                rolled_back=False,
                verdict="PATCH_REJECTED_UNSAFE",
            )

        self._log_event(
            MorphologyEventType.ARCHITECTURE_PATCH_VALIDATED,
            {"patch_id": patch.patch_id},
        )

        snapshot = self.create_pre_patch_snapshot(patch)
        applied = self.apply_patch(patch)
        if not applied:
            self._log_event(
                MorphologyEventType.ARCHITECTURE_PATCH_FAILED,
                {"patch_id": patch.patch_id, "reason": "apply_failed"},
            )
            return PatchExecutionResult(
                patch_id=patch.patch_id,
                proposal_id=patch.proposal_id,
                applied=False,
                confirmed=False,
                rolled_back=False,
                verdict="PATCH_FAILED",
            )

        self._log_event(
            MorphologyEventType.ARCHITECTURE_PATCH_APPLIED,
            {"patch_id": patch.patch_id, "target_path": patch.target_path, "new_value": str(patch.new_value)},
        )

        result = self.run_post_patch_validation(patch)
        if result.verdict == "PATCH_CONFIRMED":
            self._log_event(
                MorphologyEventType.ARCHITECTURE_PATCH_CONFIRMED,
                {"patch_id": patch.patch_id, "delta_score": result.delta_score},
            )
        elif result.verdict == "PATCH_ROLLED_BACK":
            rolled_back = self.rollback_patch(patch, snapshot)
            result.rolled_back = rolled_back
            self._log_event(
                MorphologyEventType.ARCHITECTURE_PATCH_ROLLED_BACK,
                {"patch_id": patch.patch_id, "delta_score": result.delta_score, "flags": result.regression_flags},
            )
        elif result.verdict == "PATCH_NEEDS_MORE_EVIDENCE":
            self._log_event(
                MorphologyEventType.ARCHITECTURE_PATCH_CONFIRMED,
                {"patch_id": patch.patch_id, "delta_score": result.delta_score, "note": "needs_more_evidence"},
            )

        report_path = self._save_report(patch, result)
        result.report_path = str(report_path) if report_path else None
        return result

    def _save_report(self, patch: ArchitecturePatch, result: PatchExecutionResult) -> Optional[Path]:
        reports_dir = Path("reports/architecture_patches")
        reports_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"patch_{patch.patch_id}_{timestamp}.json"
        path = reports_dir / filename
        path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        return path

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _log_event(self, event_type: MorphologyEventType, metadata: Dict[str, Any]) -> None:
        if self.memory is None or not hasattr(self.memory, "log_event"):
            return
        try:
            event = MorphologyEvent(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                event_type=event_type,
                timestamp=datetime.now(timezone.utc).timestamp(),
                metadata=metadata,
            )
            self.memory.log_event(event)
        except Exception:
            pass
