"""DNAUpdater — proposes genome YAML changes (no auto-apply).

Reads the current genome, identifies candidate knobs (e.g. dormant
``epigenetic_marks``), and emits a *proposal* for human approval. This
module never writes to the genome file directly (T104 governance).
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DNAUpdater:
    """Propose DNA changes; never apply them."""

    def __init__(
        self,
        genome_path: str | Path,
        proposals_log: str | Path = "data/self_improvement/dna_proposals.jsonl",
    ) -> None:
        self.genome_path = Path(genome_path)
        self.proposals_log = Path(proposals_log)
        self.proposals_log.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def read_genome(self) -> Dict[str, Any]:
        """Read the genome YAML or return a stub dict when missing."""
        try:
            import yaml  # type: ignore

        except ImportError:
            yaml = None
        if not self.genome_path.exists():
            return {"_missing": True, "path": str(self.genome_path)}
        try:
            if yaml is not None:
                with self.genome_path.open("r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            # Fallback: very small line-based parser
            data: Dict[str, Any] = {}
            with self.genome_path.open("r", encoding="utf-8") as f:
                for ln in f:
                    ln = ln.strip()
                    if not ln or ln.startswith("#"):
                        continue
                    if ":" in ln:
                        k, _, v = ln.partition(":")
                        data[k.strip()] = v.strip()
            return data
        except (OSError, ValueError) as exc:
            logger.warning("read_genome: %s", exc)
            return {"_error": str(exc)}

    def propose_updates(
        self,
        current_metrics: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Return a list of DNA-update proposals for human review."""
        genome = self.read_genome()
        if not genome or genome.get("_missing") or genome.get("_error"):
            return []
        proposals: List[Dict[str, Any]] = []

        # Heuristic: bump plasticity_rate slightly when coherence is low.
        coherence = float((current_metrics or {}).get("coherence_phi", 0.5))
        if coherence < 0.4:
            proposals.append(
                self._mk_proposal(
                    "dna-bump-plasticity",
                    "Increase base plasticity_rate by +0.01 (coherence low)",
                    target="plasticity_rate",
                    suggested_delta=0.01,
                )
            )

        # Heuristic: enable dormant module flagged in genome.
        for k, v in genome.items():
            if isinstance(v, dict) and v.get("enabled") is False:
                proposals.append(
                    self._mk_proposal(
                        f"dna-enable-{k}",
                        f"Enable dormant module {k}",
                        target=k,
                        suggested_value=True,
                    )
                )

        self._append(proposals)
        return proposals

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _mk_proposal(
        self,
        proposal_id: str,
        title: str,
        target: str,
        suggested_value: Any = None,
        suggested_delta: float = 0.0,
    ) -> Dict[str, Any]:
        return {
            "proposal_id": f"proposal-{uuid.uuid4().hex[:8]}",
            "proposal_kind": proposal_id,
            "title": title,
            "target": target,
            "suggested_value": suggested_value,
            "suggested_delta": suggested_delta,
            "auto_apply": False,
            "status": "pending_human_approval",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "category": "dna_update",
        }

    def _append(self, proposals: List[Dict[str, Any]]) -> None:
        if not proposals:
            return
        try:
            with self.proposals_log.open("a", encoding="utf-8") as f:
                for p in proposals:
                    f.write(json.dumps(p) + "\n")
        except OSError as exc:  # pragma: no cover
            logger.warning("append dna proposals: %s", exc)
