"""CoherenceProposalBuilder — T154-B.

Transforms CoherenceObserver reports into improvement proposals.
Each proposal is tagged, risk-scored, and queued for human approval.
No direct modifications."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional


class CoherenceProposalBuilder:
    """Builds human-review proposals from coherence reports.

    Allowed proposal types:
    - prune_redundant_skills
    - reduce_mutation_rate
    - compress_narrative
    - lower_regulation_density
    - increase_evolutionary_cooldown
    - improve_log_dashboard_order
    - suggest_ui_aesthetic

    Absolute blocks:
    - no safety/auth/governance changes
    - no physical actions
    - no ecosystem self-assimilation
    - no self-replication
    - no shell/internet
    """

    ALLOWED_TYPES = {
        "prune_redundant_skills",
        "reduce_mutation_rate",
        "compress_narrative",
        "lower_regulation_density",
        "increase_evolutionary_cooldown",
        "improve_log_dashboard_order",
        "suggest_ui_aesthetic",
    }

    # Metric thresholds for proposal generation
    THRESHOLDS: Dict[str, float] = {
        "redundancy_efficiency": 0.7,
        "cognitive_entropy": 0.7,
        "mutation_stability": 0.5,
        "narrative_coherence": 0.5,
        "regulation_density": 0.9,
        "modular_coherence": 0.5,
        "functional_elegance": 0.5,
        "causal_clarity": 0.3,
    }

    # Metric → proposal mapping
    METRIC_PROPOSALS: Dict[str, List[str]] = {
        "redundancy_efficiency": ["prune_redundant_skills"],
        "cognitive_entropy": ["compress_narrative", "suggest_ui_aesthetic"],
        "mutation_stability": ["reduce_mutation_rate", "increase_evolutionary_cooldown"],
        "narrative_coherence": ["compress_narrative"],
        "regulation_density": ["lower_regulation_density"],
        "modular_coherence": ["improve_log_dashboard_order"],
        "functional_elegance": ["improve_log_dashboard_order", "suggest_ui_aesthetic"],
        "causal_clarity": ["improve_log_dashboard_order"],
    }

    def __init__(self, data_root: str = "data/analysis/coherence") -> None:
        self._data_root = Path(data_root)
        self._data_root.mkdir(parents=True, exist_ok=True)
        self._proposals_path = self._data_root / "coherence_proposals.jsonl"
        self._proposals: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------ #
    # Build proposals from report
    # ------------------------------------------------------------------ #

    def build_from_report(self, report: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analyze a coherence report and generate proposals."""
        proposals: List[Dict[str, Any]] = []
        metrics = report.get("metrics", {})
        aggregate = report.get("aggregate_coherence")

        for metric, value in metrics.items():
            if value is None:
                continue
            threshold = self.THRESHOLDS.get(metric)
            if threshold is None:
                continue
            if value < threshold:
                for proposal_type in self.METRIC_PROPOSALS.get(metric, []):
                    p = self._create_proposal(
                        proposal_type=proposal_type,
                        trigger_metric=metric,
                        trigger_value=value,
                        threshold=threshold,
                        aggregate_coherence=aggregate,
                    )
                    proposals.append(p)
                    self._proposals[p["proposal_id"]] = p
                    self._persist(p)

        return proposals

    def _create_proposal(
        self,
        proposal_type: str,
        trigger_metric: str,
        trigger_value: float,
        threshold: float,
        aggregate_coherence: Optional[float],
    ) -> Dict[str, Any]:
        pid = f"coh_{uuid.uuid4().hex[:8]}"
        gap = threshold - trigger_value
        risk = min(1.0, max(0.1, gap * 2))

        descriptions: Dict[str, str] = {
            "prune_redundant_skills": "Identifica e propone rimozione skill ridondanti nel registro capacità.",
            "reduce_mutation_rate": "Riduce la frequenza di mutazione genomica per aumentare stabilità.",
            "compress_narrative": "Comprime eventi narrativi vecchi o a bassa importanza.",
            "lower_regulation_density": "Riduce il numero di layer di regolazione sovrapposti.",
            "increase_evolutionary_cooldown": "Aumenta il tempo di cooldown tra cicli evolutivi.",
            "improve_log_dashboard_order": "Riorganizza log e dashboard per maggiore chiarezza.",
            "suggest_ui_aesthetic": "Suggerisce miglioramenti estetici all'interfaccia web.",
        }

        proposal = {
            "proposal_id": pid,
            "proposal_type": proposal_type,
            "status": "pending",
            "trigger_metric": trigger_metric,
            "trigger_value": round(trigger_value, 4),
            "threshold": threshold,
            "gap": round(gap, 4),
            "aggregate_coherence": aggregate_coherence,
            "risk_score": round(risk, 4),
            "description": descriptions.get(proposal_type, "Proposta di miglioramento coerenza."),
            "blocked_categories": [
                "safety",
                "auth",
                "governance",
                "physical_action",
                "ecosystem_assimilation",
                "self_replication",
                "shell",
                "internet",
            ],
            "created_at": time.time(),
            "reviewer": None,
        }
        return proposal

    # ------------------------------------------------------------------ #
    # Query
    # ------------------------------------------------------------------ #

    def list_proposals(self, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        items = list(self._proposals.values())
        if status:
            items = [p for p in items if p.get("status") == status]
        items.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        return items[:limit]

    def get_proposal(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        return self._proposals.get(proposal_id)

    def update_status(self, proposal_id: str, status: str, reviewer: Optional[str] = None) -> bool:
        p = self._proposals.get(proposal_id)
        if not p:
            return False
        p["status"] = status
        if reviewer:
            p["reviewer"] = reviewer
        self._persist(p)
        return True

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _persist(self, proposal: Dict[str, Any]) -> None:
        try:
            with self._proposals_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(proposal, ensure_ascii=False) + "\n")
        except OSError:
            pass
