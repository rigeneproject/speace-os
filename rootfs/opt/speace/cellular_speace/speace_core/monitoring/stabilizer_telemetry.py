"""Stabilizer telemetry (T137-Phase1, prop-ch-002-v2).

Diagnostic-only: reads data/regulation/stabilizer_interventions.jsonl and
emits an aggregated telemetry report. Does not modify the regulator or
runtime. Output is appended to data/regulation/stabilizer_telemetry.jsonl
and also returned for in-process use.

This module is the "telemetry first" step of prop-ch-002, before any
parameter change to chaos_threshold / criticality_drift_threshold / etc.
"""

from __future__ import annotations

import json
import logging
import statistics
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


DEFAULT_LOG = Path("data/regulation/stabilizer_interventions.jsonl")
DEFAULT_OUT = Path("data/regulation/stabilizer_telemetry.jsonl")


def _read_jsonl(path: Path, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    out.append(json.loads(ln))
                except json.JSONDecodeError:
                    continue
                if limit and len(out) >= limit:
                    break
    except OSError:
        return []
    return out


def aggregate(
    log_path: Path = DEFAULT_LOG,
    window: int = 50,
) -> Dict[str, Any]:
    """Aggregate the last ``window`` interventions into a telemetry report.

    Returns a dict with:
      - counts_by_pattern: {pattern: count}
      - counts_by_modulation: {modulation: count}
      - severity_stats_by_pattern: {pattern: {mean, max, min, stdev, count}}
      - last_window_count, last_window_severity_mean
      - chaos_score_proxy: severity_sum / window (clamped to 1.0)
      - recommended_action_hint: human-readable hint based on aggregates
    """
    log_path = Path(log_path)
    all_rows = _read_jsonl(log_path)
    recent = all_rows[-window:]

    counts_pattern: Counter = Counter()
    counts_mod: Counter = Counter()
    severities_by_pattern: Dict[str, List[float]] = {}

    for r in recent:
        p = r.get("pattern_detected", "unknown")
        m = r.get("modulation", "unknown")
        sev = float(r.get("severity", 0.0) or 0.0)
        counts_pattern[p] += 1
        counts_mod[m] += 1
        severities_by_pattern.setdefault(p, []).append(sev)

    sev_stats: Dict[str, Dict[str, float]] = {}
    for p, vals in severities_by_pattern.items():
        sev_stats[p] = {
            "count": len(vals),
            "mean": round(statistics.fmean(vals), 4),
            "max": round(max(vals), 4),
            "min": round(min(vals), 4),
            "stdev": round(statistics.pstdev(vals), 4) if len(vals) > 1 else 0.0,
        }

    sev_sum = sum(float(r.get("severity", 0.0) or 0.0) for r in recent)
    chaos_score_proxy = min(1.0, sev_sum / max(1, len(recent)))

    # Recommended action hint
    hint = "stable"
    if counts_pattern:
        dominant_pattern = counts_pattern.most_common(1)[0][0]
        if dominant_pattern == "criticality_drift":
            dominant_sev = sev_stats.get("criticality_drift", {}).get("mean", 0.0)
            if dominant_sev > 2.0:
                hint = (
                    "criticality_drift dominates with severity>2.0. "
                    "The system is consistently far from branching_ratio=1.0. "
                    "Consider (a) raising criticality_drift_threshold from 0.2 to 0.4, "
                    "or (b) capping severity at 1.0 in the alert engine."
                )
            else:
                hint = "criticality_drift dominates; severity moderate."
        elif dominant_pattern == "rigidity":
            hint = "rigidity dominates; system may be stuck in a low-variance attractor."
        elif dominant_pattern == "chaos":
            hint = "chaos dominates; Lyapunov exponent is high."
        else:
            hint = f"{dominant_pattern} dominates; review detector."

    return {
        "window": window,
        "total_in_log": len(all_rows),
        "last_window_count": len(recent),
        "last_window_severity_mean": round(sev_sum / max(1, len(recent)), 4),
        "chaos_score_proxy": round(chaos_score_proxy, 4),
        "counts_by_pattern": dict(counts_pattern),
        "counts_by_modulation": dict(counts_mod),
        "severity_stats_by_pattern": sev_stats,
        "recommended_action_hint": hint,
        "timestamp": time.time(),
    }


def emit(
    log_path: Path = DEFAULT_LOG,
    out_path: Path = DEFAULT_OUT,
    window: int = 50,
) -> Dict[str, Any]:
    """Aggregate, append to ``out_path`` (jsonl), and return the report."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report = aggregate(log_path=log_path, window=window)
    try:
        with out_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(report, ensure_ascii=False) + "\n")
    except OSError as exc:  # pragma: no cover
        logger.warning("stabilizer telemetry append failed: %s", exc)
    return report


def _self_test() -> Dict[str, Any]:
    import tempfile

    fake_rows = [
        {"tick": 1, "pattern_detected": "criticality_drift", "modulation": "dampen_feedback", "severity": 2.5},
        {"tick": 2, "pattern_detected": "criticality_drift", "modulation": "inject_noise", "severity": 2.4},
        {"tick": 3, "pattern_detected": "rigidity", "modulation": "reset_attractor", "severity": 2.0},
        {"tick": 4, "pattern_detected": "criticality_drift", "modulation": "dampen_feedback", "severity": 2.3},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        log = Path(tmp) / "stab.jsonl"
        with log.open("w", encoding="utf-8") as f:
            for r in fake_rows:
                f.write(json.dumps(r) + "\n")
        out = Path(tmp) / "telem.jsonl"
        report = emit(log_path=log, out_path=out, window=10)
    return report


if __name__ == "__main__":  # pragma: no cover
    print(json.dumps(_self_test(), indent=2))
