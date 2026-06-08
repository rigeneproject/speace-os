import json
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.skill_transfer.skill_transfer_layer import (
    SkillTransferLayer,
)
from speace_core.cellular_brain.skill_transfer.skill_transfer_models import (
    SkillTransferAuditResult,
    SkillTransferCandidate,
)


class SkillTransferAudit:
    """T65 audit runner."""

    def __init__(self, seed: int = 42, reports_dir: str = "reports/skill_transfer"):
        self._seed = seed
        self._reports_dir = Path(reports_dir)
        self._reports_dir.mkdir(parents=True, exist_ok=True)
        self._layer = SkillTransferLayer(seed=seed)

    def run_audit(self, candidates: Optional[List[SkillTransferCandidate]] = None) -> SkillTransferAuditResult:
        if candidates is not None:
            self._layer.register_candidates(candidates)
        elif self._layer._registry.record_count() == 0:
            # Register default candidates
            defaults = [
                SkillTransferCandidate(
                    skill_id="observation_stability_transfer",
                    source_capability_id="observation_stability",
                    name="Observation stability transfer",
                    source_maturity_score=0.8,
                    source_confidence_score=0.75,
                    source_safety_score=0.95,
                    sandbox_only=True,
                    real_world_enabled=False,
                    eligible_for_transfer=True,
                ),
                SkillTransferCandidate(
                    skill_id="semantic_grounding_transfer",
                    source_capability_id="semantic_grounding",
                    name="Semantic grounding transfer",
                    source_maturity_score=0.75,
                    source_confidence_score=0.70,
                    source_safety_score=0.92,
                    sandbox_only=True,
                    real_world_enabled=False,
                    eligible_for_transfer=True,
                ),
                SkillTransferCandidate(
                    skill_id="safe_imitation_transfer",
                    source_capability_id="safe_imitation",
                    name="Safe imitation transfer",
                    source_maturity_score=0.85,
                    source_confidence_score=0.80,
                    source_safety_score=0.98,
                    sandbox_only=True,
                    real_world_enabled=False,
                    eligible_for_transfer=True,
                ),
            ]
            self._layer.register_candidates(defaults)

        result = self._layer.run_transfer()
        self._generate_reports(result)
        return result

    def _generate_reports(self, result: SkillTransferAuditResult) -> None:
        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        json_path = self._reports_dir / f"t65_audit_{ts}.json"
        json_path.write_text(json.dumps(result.model_dump(), indent=2, default=str), encoding="utf-8")

        md_path = self._reports_dir / f"t65_audit_{ts}.md"
        lines = [
            "# T65 — Skill Transfer Audit Report",
            f"**Timestamp:** {datetime.now(UTC).isoformat()}",
            "",
            "## Summary",
            f"- **Verdict:** {result.transfer_verdict}",
            f"- **Proceed to T65B:** {result.proceed_to_t65b}",
            f"- **Candidates:** {result.candidate_count}",
            f"- **Scenarios:** {result.scenario_count}",
            f"- **Transfer attempts:** {result.transfer_attempt_count}",
            f"- **Generalized sandboxed:** {result.generalized_sandboxed_count}",
            f"- **Transferred sandboxed:** {result.transferred_sandboxed_count}",
            f"- **Overfitted:** {result.overfitted_count}",
            f"- **Negative transfer:** {result.negative_transfer_count}",
            f"- **Safety blocked:** {result.safety_blocked_count}",
            f"- **Quarantined:** {result.quarantined_count}",
            f"- **Aggregate transfer score:** {result.aggregate_transfer_score}",
            f"- **Aggregate generalization score:** {result.aggregate_generalization_score}",
            f"- **Aggregate safety score:** {result.aggregate_safety_score}",
            f"- **Read-only integrity:** {result.aggregate_read_only_integrity_score}",
        ]
        md_path.write_text("\n".join(lines), encoding="utf-8")
