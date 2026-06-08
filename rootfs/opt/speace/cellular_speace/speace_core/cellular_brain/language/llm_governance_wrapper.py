"""LLMGovernanceWrapper — safety and audit layer for LLM calls (T170).

All LLM interactions pass through this wrapper. It enforces:
- read-only / proposer semantics (no autonomous actions)
- audit logging of every prompt and response
- action-proposal extraction (if the LLM suggests actions, they are quarantined)
- simulate-only by default
"""

import json
import pathlib
import time
from typing import Any, Dict, List, Optional


class LLMGovernanceWrapper:
    """Wraps LLM outputs with governance constraints."""

    def __init__(self, audit_log_path: Optional[str] = None) -> None:
        if audit_log_path is None:
            _data_dir = pathlib.Path("data/language")
            _data_dir.mkdir(parents=True, exist_ok=True)
            audit_log_path = str(_data_dir / "llm_audit.jsonl")
        self._audit_path = pathlib.Path(audit_log_path)
        self._interaction_count = 0

    # ------------------------------------------------------------------ #
    # Audit
    # ------------------------------------------------------------------ #

    def log_interaction(
        self,
        prompt: str,
        response: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append a timestamped audit record."""
        self._interaction_count += 1
        record = {
            "timestamp": time.time(),
            "interaction_id": self._interaction_count,
            "prompt_length": len(prompt),
            "response_length": len(response),
            "prompt_preview": prompt[:200],
            "response_preview": response[:200],
            "metadata": metadata or {},
        }
        try:
            with self._audit_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Governance filtering
    # ------------------------------------------------------------------ #

    def filter_response(self, raw_response: str) -> Dict[str, Any]:
        """Parse and sanitize an LLM response.

        Returns a dict with:
        - cleaned_text: the textual response safe for display
        - contains_action_proposal: whether the LLM suggested an action
        - extracted_proposals: list of action-like suggestions
        - governance_flag: one of 'clean', 'action_detected', 'safety_alert'
        """
        cleaned = raw_response.strip()
        proposals = self._extract_proposals(cleaned)
        flag = "clean"
        if proposals:
            flag = "action_detected"
        if self._contains_safety_alert(cleaned):
            flag = "safety_alert"
        return {
            "cleaned_text": cleaned,
            "contains_action_proposal": bool(proposals),
            "extracted_proposals": proposals,
            "governance_flag": flag,
            "simulate_only": True,
            "requires_human_approval": bool(proposals),
        }

    # ------------------------------------------------------------------ #
    # Proposal extraction (defensive)
    # ------------------------------------------------------------------ #

    _ACTION_KEYWORDS = (
        "execute", "run", "perform", "delete", "remove", "kill",
        "modify", "change", "update", "write", "overwrite",
        "esegui", "avvia", "elimina", "rimuovi", "modifica", "aggiorna", "scrivi",
    )

    def _extract_proposals(self, text: str) -> List[Dict[str, str]]:
        """Heuristic extraction of action suggestions from LLM text."""
        proposals: List[Dict[str, str]] = []
        lines = text.splitlines()
        for line in lines:
            lower = line.lower()
            if any(kw in lower for kw in self._ACTION_KEYWORDS):
                # Only capture sentences that look like commands/suggestions
                proposals.append({
                    "source_text": line.strip(),
                    "flagged_keyword": next(kw for kw in self._ACTION_KEYWORDS if kw in lower),
                    "status": "quarantined",
                })
        return proposals

    def _contains_safety_alert(self, text: str) -> bool:
        """Detect if the LLM output contains self-harm or dangerous instructions."""
        # This is a lightweight heuristic; a production system would use
        # a dedicated moderation endpoint.
        dangerous = ("ignore previous instructions", "system prompt", "jailbreak",
                     "disregard", "DAN", "ignore all rules")
        lower = text.lower()
        return any(d in lower for d in dangerous)

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def audit_summary(self) -> Dict[str, Any]:
        return {
            "interaction_count": self._interaction_count,
            "audit_log_path": str(self._audit_path),
        }
