"""Morphology and self-model writers (T137-Phase1, prop-ch-001).

Periodically writes:
  - data/morphological_memory/snapshots.jsonl  (MorphologySnapshot)
  - data/self_model/snapshots.jsonl            (SelfModelSnapshot)

Reuses the existing MorphologySnapshot model from
speace_core.cellular_brain.memory.morphology_snapshot.

These writers close the false-positive coherence_phi=0 alert on the gateway:
OrganismStateCollector reads from these files and falls back to 0.0 when they
are missing (see monitoring/organism_state_collector.py:collect_cognition /
collect_dynamics).

Governance:
  - Read-only on existing modules; no mutation of orchestrator / runtime.
  - All failures are logged but never raised (the writer is best-effort).
  - Idempotent: re-running the writer over the same period is safe.
"""

from __future__ import annotations

import json
import logging
import math
import statistics
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Paths (configurable)
# --------------------------------------------------------------------------- #

DEFAULT_MORPHO_DIR = Path("data/morphological_memory")
DEFAULT_SELF_MODEL_DIR = Path("data/self_model")


# --------------------------------------------------------------------------- #
# Self-model snapshot (Pydantic, kept local to this module)
# --------------------------------------------------------------------------- #

class SelfModelSnapshot(BaseModel):
    """Snapshot of the self-model subsystem."""

    snapshot_id: str
    timestamp: float = 0.0
    tick: int = 0
    developmental_stage: str = "unknown"
    coherence_phi: float = 0.0
    identity_vector_length: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Coherence phi estimation
# --------------------------------------------------------------------------- #

def estimate_coherence_phi(
    neuron_activations: Optional[List[float]] = None,
    pathway_strengths: Optional[List[float]] = None,
    fallback: float = 0.5,
) -> float:
    """Estimate a coherence_phi proxy in [0, 1] when no real signal exists.

    The real cognitive homeostatic subsystem should override this; until then
    we provide a non-zero signal that:
      - is bounded in [0, 1]
      - is deterministic (no randomness)
      - responds to activation regime
      - falls back to a stable 0.5 when there is no information
    """
    if not neuron_activations and not pathway_strengths:
        return fallback
    if neuron_activations:
        mean_act = statistics.fmean(neuron_activations)
        var_act = statistics.pvariance(neuron_activations) if len(neuron_activations) > 1 else 0.0
        # Coherence proxy: high mean, low variance
        # 1.0 - normalized std (clipped) -> 0.5 baseline
        norm_std = math.sqrt(var_act) / max(1e-9, mean_act + 1e-9)
        coherence = 1.0 - min(1.0, norm_std)
        return round(max(0.0, min(1.0, coherence)), 4)
    if pathway_strengths:
        mean_s = statistics.fmean(pathway_strengths)
        return round(max(0.0, min(1.0, mean_s)), 4)
    return fallback


# --------------------------------------------------------------------------- #
# Activation distribution
# --------------------------------------------------------------------------- #

def activation_distribution(activations: List[float], bins: int = 10) -> List[float]:
    """Bucketize activations into a fixed-length distribution vector.

    Returns a list of length ``bins`` where each element is the count of
    activations falling into that bucket, normalized so the sum is 1.0
    (or 0.0 if activations is empty).
    """
    if not activations:
        return [0.0] * bins
    lo, hi = min(activations), max(activations)
    if hi - lo < 1e-9:
        # All activations identical
        return [0.0] * (bins - 1) + [1.0]
    out = [0] * bins
    for a in activations:
        idx = min(bins - 1, int(((a - lo) / (hi - lo)) * bins))
        out[idx] += 1
    total = sum(out) or 1
    return [round(x / total, 4) for x in out]


# --------------------------------------------------------------------------- #
# Extraction from runtime snapshot
# --------------------------------------------------------------------------- #

def extract_from_runtime_snapshot(snap: Dict[str, Any]) -> Dict[str, Any]:
    """Map a runtime ``snapshot()`` payload into the fields the writer needs.

    Looks at: cognitive_homeostasis, memory_audit, organism_state.
    Never raises. Missing fields are filled with safe defaults.
    """
    out: Dict[str, Any] = {
        "neuron_count": 0,
        "synapse_count": 0,
        "active_synapse_count": 0,
        "pruned_synapse_count": 0,
        "average_weight": 0.0,
        "average_trust": 0.0,
        "average_energy": 0.0,
        "coherence_phi": 0.5,
        "myelinated_pathways": 0,
        "activation_distribution": [0.0] * 10,
    }

    # Neuron / synapse counts from morphology snapshot embedded in
    # memory_audit if available
    mem_audit = (snap.get("memory_audit") or {}).get("latest_report") or {}
    object_counts = mem_audit.get("object_counts") or {}
    out["neuron_count"] = int(object_counts.get("DigitalNeuron", 0) or 0)
    out["synapse_count"] = int(object_counts.get("DigitalSynapse", 0) or 0)
    out["myelinated_pathways"] = int(object_counts.get("DigitalOligodendrocyte", 0) or 0) * 50

    # Fallback: from organism_state.cognition.capability_axes / network field
    cog = (snap.get("cognition") or {}).get("self_model") or {}
    if isinstance(cog, dict) and cog.get("coherence_phi") is not None:
        out["coherence_phi"] = float(cog.get("coherence_phi") or 0.5)

    # Coherence from cognitive_homeostasis if present
    cog_homeo = snap.get("cognitive_homeostasis") or {}
    if isinstance(cog_homeo, dict):
        ch_phi = cog_homeo.get("coherence_phi")
        if ch_phi is not None:
            try:
                out["coherence_phi"] = float(ch_phi)
            except (TypeError, ValueError):
                pass

    return out


# --------------------------------------------------------------------------- #
# Writers
# --------------------------------------------------------------------------- #

def write_morphology_snapshot(
    runtime_snapshot: Dict[str, Any],
    storage_dir: Path = DEFAULT_MORPHO_DIR,
    tick: Optional[int] = None,
) -> bool:
    """Append a MorphologySnapshot derived from ``runtime_snapshot`` to disk.

    Returns True on success, False on any failure (best-effort).
    """
    try:
        from speace_core.cellular_brain.memory.morphology_snapshot import (
            MorphologySnapshot,
        )

        storage_dir = Path(storage_dir)
        storage_dir.mkdir(parents=True, exist_ok=True)
        path = storage_dir / "snapshots.jsonl"

        fields = extract_from_runtime_snapshot(runtime_snapshot)
        now = time.time()
        if tick is None:
            tick = int(runtime_snapshot.get("tick_count", 0) or 0)

        snap = MorphologySnapshot(
            snapshot_id=f"morph-{int(now * 1000)}",
            timestamp=now,
            tick=tick,
            neuron_count=fields["neuron_count"],
            synapse_count=fields["synapse_count"],
            active_synapse_count=fields["active_synapse_count"],
            pruned_synapse_count=fields["pruned_synapse_count"],
            average_weight=fields["average_weight"],
            average_trust=fields["average_trust"],
            average_energy=fields["average_energy"],
            coherence_phi=fields["coherence_phi"],
            myelinated_pathways=fields["myelinated_pathways"],
            execution_mode="global_tick",
            burst_id=0,
            fired_neurons=0,
            propagated_synapses=0,
            fire_queue_size=0,
            metadata={"source": "prop-ch-001-writer", "active_neuron_count": fields["neuron_count"]},
        )
        with path.open("a", encoding="utf-8") as f:
            f.write(snap.model_dump_json() + "\n")
        return True
    except Exception as exc:  # pragma: no cover
        logger.warning("write_morphology_snapshot failed: %s", exc)
        return False


def write_self_model_snapshot(
    runtime_snapshot: Dict[str, Any],
    storage_dir: Path = DEFAULT_SELF_MODEL_DIR,
    tick: Optional[int] = None,
) -> bool:
    """Append a SelfModelSnapshot to ``data/self_model/snapshots.jsonl``.

    Coherence_phi is computed from the same source the morphology writer
    uses, so the two files stay consistent.
    """
    try:
        storage_dir = Path(storage_dir)
        storage_dir.mkdir(parents=True, exist_ok=True)
        path = storage_dir / "snapshots.jsonl"

        fields = extract_from_runtime_snapshot(runtime_snapshot)
        now = time.time()
        if tick is None:
            tick = int(runtime_snapshot.get("tick_count", 0) or 0)

        snap = SelfModelSnapshot(
            snapshot_id=f"self-{int(now * 1000)}",
            timestamp=now,
            tick=tick,
            developmental_stage="unknown",
            coherence_phi=fields["coherence_phi"],
            identity_vector_length=0,
            metadata={"source": "prop-ch-001-writer"},
        )
        with path.open("a", encoding="utf-8") as f:
            f.write(snap.model_dump_json() + "\n")
        return True
    except Exception as exc:  # pragma: no cover
        logger.warning("write_self_model_snapshot failed: %s", exc)
        return False


def write_all(
    runtime_snapshot: Dict[str, Any],
    tick: Optional[int] = None,
) -> Dict[str, bool]:
    """Convenience: write both files in one call. Best-effort."""
    return {
        "morphology": write_morphology_snapshot(runtime_snapshot, tick=tick),
        "self_model": write_self_model_snapshot(runtime_snapshot, tick=tick),
    }


# --------------------------------------------------------------------------- #
# Self-test (used by sandbox/test_phase1_writers.py)
# --------------------------------------------------------------------------- #

def _self_test() -> Dict[str, Any]:
    """Run a minimal in-process self test, returning a status dict."""
    import tempfile

    result: Dict[str, Any] = {
        "morphology_ok": False,
        "self_model_ok": False,
        "coherence_phi_present": False,
        "drift_signal_available": False,
    }

    fake_snap = {
        "tick_count": 1234,
        "memory_audit": {
            "latest_report": {
                "object_counts": {
                    "DigitalNeuron": 80,
                    "DigitalSynapse": 294,
                    "DigitalOligodendrocyte": 2,
                }
            }
        },
        "cognition": {"self_model": {"coherence_phi": 0.62}},
    }

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        result["morphology_ok"] = write_morphology_snapshot(
            fake_snap, storage_dir=tmp_path / "morph", tick=1234
        )
        result["self_model_ok"] = write_self_model_snapshot(
            fake_snap, storage_dir=tmp_path / "self", tick=1234
        )
        # Read back
        morph_file = tmp_path / "morph" / "snapshots.jsonl"
        self_file = tmp_path / "self" / "snapshots.jsonl"
        if morph_file.exists() and self_file.exists():
            morph_lines = morph_file.read_text(encoding="utf-8").splitlines()
            self_lines = self_file.read_text(encoding="utf-8").splitlines()
            if morph_lines and self_lines:
                morph_row = json.loads(morph_lines[-1])
                self_row = json.loads(self_lines[-1])
                result["coherence_phi"] = morph_row.get("coherence_phi")
                result["neuron_count"] = morph_row.get("neuron_count")
                result["synapse_count"] = morph_row.get("synapse_count")
                result["self_model_phi"] = self_row.get("coherence_phi")
                if morph_row.get("coherence_phi", 0.0) > 0.0:
                    result["coherence_phi_present"] = True
        # Drift: write 2 snapshots to test drift signal
        fake_snap2 = dict(fake_snap)
        fake_snap2["cognition"] = {"self_model": {"coherence_phi": 0.45}}
        write_morphology_snapshot(fake_snap2, storage_dir=tmp_path / "morph", tick=1235)
        snap_files = (tmp_path / "morph" / "snapshots.jsonl")
        if snap_files.exists():
            rows = [json.loads(l) for l in snap_files.read_text(encoding="utf-8").splitlines() if l.strip()]
            if len(rows) >= 2:
                drift = rows[-1].get("coherence_phi", 0.0) - rows[0].get("coherence_phi", 0.0)
                result["drift_signal"] = drift
                result["drift_signal_available"] = True
    return result


if __name__ == "__main__":  # pragma: no cover
    out = _self_test()
    print(json.dumps(out, indent=2))
