import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from speace_core.cellular_brain.self_improvement.architecture_rewriter import (
    ArchitectureRewriteProposal,
    SelfImprovementCycleResult,
)


class ProposalStore:
    """JSONL persistence for architecture proposals and cycle results."""

    def __init__(self, base_path: str = "data/self_improvement"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.proposals_path = self.base_path / "proposals.jsonl"
        self.cycles_path = self.base_path / "cycles.jsonl"

    # ------------------------------------------------------------------ #
    # Proposal persistence
    # ------------------------------------------------------------------ #

    def save_proposal(self, proposal: ArchitectureRewriteProposal) -> str:
        record = proposal.model_dump()
        record["_stored_at"] = datetime.now(timezone.utc).isoformat()
        with open(self.proposals_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return proposal.id

    def load_proposal(self, proposal_id: str) -> ArchitectureRewriteProposal:
        if not self.proposals_path.exists():
            raise FileNotFoundError(f"No proposals store at {self.proposals_path}")
        with open(self.proposals_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if record.get("id") == proposal_id:
                    # Remove internal storage metadata before parsing
                    record.pop("_stored_at", None)
                    return ArchitectureRewriteProposal(**record)
        raise KeyError(f"Proposal {proposal_id} not found")

    def list_proposals(
        self, status: Optional[str] = None
    ) -> List[ArchitectureRewriteProposal]:
        results: List[ArchitectureRewriteProposal] = []
        if not self.proposals_path.exists():
            return results
        with open(self.proposals_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                record.pop("_stored_at", None)
                if status is None or record.get("status") == status:
                    results.append(ArchitectureRewriteProposal(**record))
        return results

    # ------------------------------------------------------------------ #
    # Cycle result persistence
    # ------------------------------------------------------------------ #

    def save_cycle_result(self, result: SelfImprovementCycleResult) -> str:
        record = result.model_dump()
        record["_stored_at"] = datetime.now(timezone.utc).isoformat()
        with open(self.cycles_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return result.cycle_id

    def list_cycle_results(self) -> List[SelfImprovementCycleResult]:
        results: List[SelfImprovementCycleResult] = []
        if not self.cycles_path.exists():
            return results
        with open(self.cycles_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                record.pop("_stored_at", None)
                results.append(SelfImprovementCycleResult(**record))
        return results
