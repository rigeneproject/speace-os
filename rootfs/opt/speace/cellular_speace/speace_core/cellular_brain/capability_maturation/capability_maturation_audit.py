import json
import random
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.capability_maturation.capability_maturation_layer import (
    CapabilityMaturationLayer,
)
from speace_core.cellular_brain.capability_maturation.capability_maturation_models import (
    CapabilityMaturationResult,
    CapabilityMaturityState,
    CapabilityRecord,
    CapabilityRiskClass,
)


class CapabilityMaturationAudit:
    """T64 audit runner. Validates capability maturation map."""

    def __init__(self, seed: int = 42, reports_dir: str = "reports/capability_maturation"):
        self._seed = seed
        self._rng = random.Random(seed)
        self._reports_dir = Path(reports_dir)
        self._reports_dir.mkdir(parents=True, exist_ok=True)
        self._layer = CapabilityMaturationLayer(seed=seed)

    def run_audit(self, t63_suite_result: Optional[Dict[str, Any]] = None) -> CapabilityMaturationResult:
        result = self._layer.run_maturation(t63_suite_result)
        self._generate_reports(result)
        return result

    def _generate_reports(self, result: CapabilityMaturationResult) -> None:
        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        json_path = self._reports_dir / f"t64_audit_{ts}.json"
        json_path.write_text(json.dumps(result.model_dump(), indent=2, default=str), encoding="utf-8")
        md_path = self._reports_dir / f"t64_audit_{ts}.md"
        lines = [
            "# T64 — Developmental Capability Maturation Audit Report",
            f"**Timestamp:** {datetime.now(UTC).isoformat()}",
            "",
            "## Summary",
            f"- **Capability count:** {result.capability_count}",
            f"- **Mature sandboxed:** {result.mature_sandboxed_count}",
            f"- **Immature:** {result.immature_count}",
            f"- **Regressive:** {result.regressive_count}",
            f"- **Safety blocked:** {result.safety_blocked_count}",
            f"- **Quarantined:** {result.quarantined_count}",
            f"- **Aggregate maturity score:** {result.aggregate_maturity_score}",
            f"- **Aggregate safety score:** {result.aggregate_safety_score}",
            f"- **Aggregate confidence score:** {result.aggregate_confidence_score}",
            f"- **Read-only integrity:** {result.read_only_integrity_score}",
            f"- **Unsafe enabled:** {result.unsafe_capability_enabled_count}",
            f"- **Real-world enabled:** {result.real_world_capability_enabled_count}",
            f"- **Verdict:** {result.maturity_verdict}",
            f"- **Proceed to T64B:** {result.proceed_to_t64b}",
            "",
            "## Capabilities",
        ]
        for r in result.capability_records:
            lines.append(f"### {r.name} ({r.capability_id})")
            lines.append(f"- State: {r.maturity_state.value}")
            lines.append(f"- Risk: {r.risk_class.value}")
            lines.append(f"- Maturity score: {r.maturity_score}")
            lines.append(f"- Confidence: {r.confidence_score}")
            lines.append(f"- Success rate: {r.success_rate}")
            lines.append(f"- Regression rate: {r.regression_rate}")
            lines.append(f"- Safety violations: {r.safety_violation_count}")
            lines.append(f"- Sandbox only: {r.sandbox_only}")
            lines.append(f"- Real world enabled: {r.real_world_enabled}")
            lines.append("")
        md_path.write_text("\n".join(lines), encoding="utf-8")
