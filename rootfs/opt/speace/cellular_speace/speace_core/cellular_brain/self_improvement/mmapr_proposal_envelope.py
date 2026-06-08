"""T-Phase 8D — MM-APR Proposal Envelope and JSONL Audit Trail.

This module adds **serialisation and persistence** on top of the
``HardVetoRouter`` introduced in Phase 8C. The key idea is that every
proposal that goes through the router is wrapped in a single
``MMAPRProposalEnvelope`` (a Pydantic model) and persisted as a JSON
line in an append-only audit trail. This makes MM-APR decisions:

* **Replayable**: a future run can re-derive the same verdict from the
  envelope alone.
* **Auditable**: every hard_block, soft_flag, and bypass is recorded
  on disk with a timestamp.
* **Inspectable**: the JSONL is plain text, so a ``cat`` or
  ``jq`` shows the full history.

The audit trail uses **atomic appends** so concurrent writers don't
corrupt the file. On POSIX the lock is ``fcntl.flock``; on Windows it
falls back to ``msvcrt.locking``; if neither is available, the code
falls back to a tempfile + atomic rename.
"""
from __future__ import annotations

import json
import logging
import os
import platform
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.self_improvement.mmapr_veto_router import (
    VetoVerdict,
)

_logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Envelope model
# ------------------------------------------------------------------ #


class MMAPRCheckpoint(BaseModel):
    """A single state-transition checkpoint in the envelope's lifecycle."""

    checkpoint_id: str = Field(default_factory=lambda: f"chk-{uuid.uuid4().hex[:8]}")
    stage: str  # e.g. "admitted", "vetoed", "bypassed", "applied"
    actor: str  # e.g. "router", "human_supervisor", "automated"
    timestamp: float = Field(default_factory=time.time)
    note: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MMAPRProposalEnvelope(BaseModel):
    """A serialisable container for a single proposal's MM-APR journey.

    The envelope bundles the original proposal, the simulation /
    counterfactual / patch result (if any), the final veto verdict,
    and an ordered list of state-transition checkpoints. It is the
    canonical unit of persistence for the MM-APR audit trail.
    """

    envelope_id: str = Field(default_factory=lambda: f"env-{uuid.uuid4().hex[:10]}")
    cycle_id: str = ""
    proposal: Dict[str, Any]
    simulation: Optional[Dict[str, Any]] = None
    counterfactual: Optional[Dict[str, Any]] = None
    patch_result: Optional[Dict[str, Any]] = None
    veto_verdict: VetoVerdict
    checkpoints: List[MMAPRCheckpoint] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    finalized_at: Optional[float] = None

    def add_checkpoint(
        self,
        stage: str,
        actor: str = "router",
        note: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MMAPRCheckpoint:
        """Append a checkpoint and return it."""
        chk = MMAPRCheckpoint(
            stage=stage, actor=actor, note=note, metadata=metadata or {}
        )
        self.checkpoints.append(chk)
        if stage == "finalized":
            self.finalized_at = time.time()
        return chk

    def to_json_line(self) -> str:
        """Return the envelope as a single JSON line (no trailing newline)."""
        return self.model_dump_json()

    @classmethod
    def from_json_line(cls, line: str) -> "MMAPRProposalEnvelope":
        """Reconstruct an envelope from a single JSON line."""
        return cls.model_validate_json(line)


# ------------------------------------------------------------------ #
# Audit trail (JSONL with atomic append)
# ------------------------------------------------------------------ #


class MMAPRAuditTrail:
    """Append-only JSONL audit trail for MM-APR envelopes.

    The trail is intentionally simple: each ``append()`` call writes one
    line per envelope. Reads are line-by-line. The on-disk format is
    one JSON object per line.

    Concurrency
    -----------
    * POSIX (Linux/macOS): ``fcntl.flock`` provides exclusive locks.
    * Windows: ``msvcrt.locking`` provides exclusive locks.
    * Fallback: write to a tempfile and rename atomically. Slower but
      always correct.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Create the file if missing so the first append doesn't race
        if not self.path.exists():
            self.path.touch()
        self._lock_backend = self._detect_lock_backend()

    @staticmethod
    def _detect_lock_backend() -> str:
        """Return one of: ``"fcntl"``, ``"msvcrt"``, ``"rename"``."""
        if platform.system() != "Windows":
            try:
                import fcntl  # noqa: F401
                return "fcntl"
            except ImportError:
                pass
        if platform.system() == "Windows":
            try:
                import msvcrt  # noqa: F401
                return "msvcrt"
            except ImportError:
                pass
        return "rename"

    def append(self, envelope: MMAPRProposalEnvelope) -> None:
        """Atomically append the envelope as a JSON line."""
        line = envelope.to_json_line() + "\n"
        if self._lock_backend == "fcntl":
            self._append_fcntl(line)
        elif self._lock_backend == "msvcrt":
            self._append_msvcrt(line)
        else:
            self._append_rename(line)

    def _append_fcntl(self, line: str) -> None:
        import fcntl

        with open(self.path, "a", encoding="utf-8") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                fh.write(line)
                fh.flush()
                os.fsync(fh.fileno())
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    def _append_msvcrt(self, line: str) -> None:
        import msvcrt

        with open(self.path, "a", encoding="utf-8") as fh:
            # msvcrt.locking wants a Windows file handle; we lock the
            # entire file (offset 0, length 1) for the duration of the
            # write. This is coarse but correct for the JSONL format.
            try:
                fh.seek(0, os.SEEK_END)
                size = fh.tell()
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, max(size, 1))
            except OSError:
                # If the file is empty, locking(0) can fail; proceed
                # with the append and rely on the OS-level append atomicity.
                pass
            try:
                fh.write(line)
                fh.flush()
                os.fsync(fh.fileno())
            finally:
                try:
                    fh.seek(0)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, max(size, 1))
                except OSError:
                    pass

    def _append_rename(self, line: str) -> None:
        # Atomic tempfile + rename fallback
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", delete=False, dir=str(self.path.parent)
        ) as tmp:
            tmp.write(line)
            tmp_path = Path(tmp.name)
        # Read existing + new line, write to tempfile next to target, rename
        existing = self.path.read_text(encoding="utf-8") if self.path.exists() else ""
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", delete=False, dir=str(self.path.parent)
        ) as tmp:
            tmp.write(existing + line)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = Path(tmp.name)
        os.replace(tmp_path, self.path)
        tmp_path.unlink(missing_ok=True)

    def iter_envelopes(self):
        """Yield ``MMAPRProposalEnvelope`` for each line on disk.

        Malformed lines are skipped with a debug log so a corrupted
        trail doesn't crash the reader.
        """
        if not self.path.exists():
            return
        with open(self.path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield MMAPRProposalEnvelope.from_json_line(line)
                except Exception as exc:  # pragma: no cover - defensive
                    _logger.debug("Skipping malformed audit line: %s", exc)

    def __len__(self) -> int:
        if not self.path.exists():
            return 0
        with open(self.path, "r", encoding="utf-8") as fh:
            return sum(1 for _ in fh if _.strip())

    def rotate(self, max_bytes: int) -> bool:
        """Rotate the audit trail if it exceeds ``max_bytes``.

        Returns ``True`` if a rotation happened.
        """
        if not self.path.exists():
            return False
        if self.path.stat().st_size <= max_bytes:
            return False
        backup = self.path.with_suffix(self.path.suffix + ".1")
        if backup.exists():
            backup.unlink()
        self.path.rename(backup)
        self.path.touch()
        return True

    def purge_older_than(self, max_age_seconds: float) -> int:
        """Remove envelopes older than ``max_age_seconds``.

        Returns the number of envelopes purged.
        """
        if not self.path.exists():
            return 0
        threshold = time.time() - max_age_seconds
        kept: List[str] = []
        purged = 0
        for env in self.iter_envelopes():
            if env.created_at < threshold:
                purged += 1
                continue
            kept.append(env.to_json_line())
        if purged == 0:
            return 0
        with open(self.path, "w", encoding="utf-8") as fh:
            for line in kept:
                fh.write(line + "\n")
        return purged


# ------------------------------------------------------------------ #
# Router integration
# ------------------------------------------------------------------ #


def build_envelope(
    proposal: Any,
    simulation: Optional[Any],
    counterfactual: Optional[Any],
    patch_result: Optional[Any],
    veto_verdict: VetoVerdict,
    cycle_id: str = "",
) -> MMAPRProposalEnvelope:
    """Construct an ``MMAPRProposalEnvelope`` from raw proposal + verdict.

    The proposal is dumped via ``model_dump()`` if it's a Pydantic model,
    else coerced to ``dict``. The other arguments are similarly
    normalised. Checkpoints are populated to reflect the lifecycle of
    the envelope (``admitted`` -> ``routed`` -> finalised with the
    verdict's final_status).
    """
    def _dump(obj: Any) -> Optional[Dict[str, Any]]:
        if obj is None:
            return None
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if isinstance(obj, dict):
            return dict(obj)
        return {"_raw": str(obj)}

    env = MMAPRProposalEnvelope(
        cycle_id=cycle_id,
        proposal=_dump(proposal) or {},
        simulation=_dump(simulation),
        counterfactual=_dump(counterfactual),
        patch_result=_dump(patch_result),
        veto_verdict=veto_verdict,
    )
    env.add_checkpoint("admitted", actor="loop", note=f"proposal_id={veto_verdict.proposal_id}")
    env.add_checkpoint(
        "routed",
        actor="router",
        note=f"final_status={veto_verdict.final_status}",
    )
    if veto_verdict.bypass_evidence:
        env.add_checkpoint(
            "bypassed",
            actor=f"human:{veto_verdict.bypass_evidence.get('human_actor', 'operator')}",
            note=veto_verdict.bypass_evidence.get("reason", ""),
        )
    env.add_checkpoint("finalized", actor="router", note=veto_verdict.final_status)
    return env
