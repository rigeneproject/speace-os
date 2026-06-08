"""ARI — AGI Readiness Index computation (8-axis, shared by daemon + web).

The 8 axes are independent cognitive capabilities. Each axis is in [0,1]
and the weighted sum (weights sum to 1.0) is reported as a percentage.

This module is *pure* (no Flask, no I/O on data/) so it can be reused
inside the evolution daemon and the web dashboard.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


# Canonical weights (must sum to 1.0)
ARI_WEIGHTS: Dict[str, float] = {
    "arc_score": 0.20,
    "generalization": 0.15,
    "memory_integration": 0.15,
    "self_improvement": 0.10,
    "planning": 0.10,
    "robustness": 0.10,
    "knowledge_graph_coherence": 0.10,
    "autonomy": 0.10,
}


# --------------------------------------------------------------------------- #
# Per-axis components
# --------------------------------------------------------------------------- #
def arc_score(cycles: List[Dict[str, Any]]) -> float:
    """ARC score = best available ARC signal from the latest cycle.

    Combines three sources, in order of preference:
    1. ``bench.components.arc_agi_subset`` (binary solve rate)
    2. Mean ``match_score`` from ``steps.arc.results`` (pixel-level
       partial credit, including best-partial candidates)
    3. ``steps.arc.accuracy`` (solve rate from the runner)
    """
    if not cycles:
        return 0.0
    last = cycles[-1]
    bench = last.get("steps", {}).get("benchmark", {}) or {}
    direct = float(bench.get("components", {}).get("arc_agi_subset", 0.0))
    # Pixel-level partial credit
    arc = last.get("steps", {}).get("arc", {}) or {}
    results = arc.get("results", []) or []
    pixel_score = 0.0
    if results:
        scores = [float(r.get("match_score", 0.0) or 0.0) for r in results]
        pixel_score = sum(scores) / max(1, len(scores))
    runner_acc = float(arc.get("accuracy", 0.0) or 0.0)
    return max(0.0, min(1.0, max(direct, pixel_score, runner_acc)))


def generalization(cycles: List[Dict[str, Any]]) -> float:
    """Stability of the AGI% across recent cycles (low variance = good)."""
    if len(cycles) < 3:
        return 0.0
    scores: List[float] = []
    for c in cycles[-10:]:
        v = c.get("steps", {}).get("benchmark", {}).get("agi_percentage")
        if v is not None:
            scores.append(float(v))
    if len(scores) < 2:
        return 0.0
    mean = sum(scores) / len(scores)
    var = sum((s - mean) ** 2 for s in scores) / len(scores)
    cv = (var ** 0.5) / max(1e-6, mean)
    return max(0.0, min(1.0, 1.0 - min(1.0, cv)))


def memory_integration(cycles: List[Dict[str, Any]]) -> float:
    """Memory integration: workspace activity × capability axes × narrative."""
    if not cycles:
        return 0.0
    last = cycles[-1]
    cog = last.get("steps", {}).get("cognition", {}) or {}
    ws = cog.get("workspace", {}) or {}
    sm = cog.get("self_model", {}) or {}
    # Boolean checks on individual cognitive capabilities.
    components = [
        bool(ws.get("active_items", 0) > 0),
        bool(ws.get("ignition_score", 0.0) > 0.0),
        bool(sm.get("identity_coherence", 0.0) > 0.0),
        bool(sm.get("self_awareness", 0.0) > 0.0),
        bool(cog.get("narrative_depth", 0) > 0),
        bool((cog.get("capability_axes") or {})),
    ]
    axes = (cog.get("capability_axes") or {}).values()
    axes_score = sum(1 for v in axes if v) / max(1, len(list(axes)))
    # Bonus: actual ignition value (0-1) contributes directly.
    ignition = float(ws.get("ignition_score", 0.0) or 0.0)
    base = axes_score * 0.5 + (sum(components) / len(components)) * 0.3
    return max(0.0, min(1.0, base + ignition * 0.2))


def self_improvement(cycles: List[Dict[str, Any]]) -> float:
    """Self-improvement: trend of AGI% across recent cycles, blended
    with adoption/proposal evidence.

    T169 — the pure slope of AGI% can stay at 0 when the system is
    stable (no regression but no growth). To capture the *capacity*
    for self-improvement, we blend:
      - 70% AGI% slope (the "did we actually improve" signal)
      - 30% adoption/proposal activity (the "are we exercising the
        self-modification loop" signal)
    """
    slope_part = 0.0
    if len(cycles) >= 3:
        pairs: List[float] = []
        for c in cycles[-15:]:
            v = c.get("steps", {}).get("benchmark", {}).get("agi_percentage")
            if v is not None:
                pairs.append(float(v))
        if len(pairs) >= 3:
            n = len(pairs)
            mean_y = sum(pairs) / n
            num = sum((i - (n - 1) / 2) * (y - mean_y) for i, y in enumerate(pairs))
            den = sum((i - (n - 1) / 2) ** 2 for i in range(n)) or 1.0
            slope = num / den
            slope_part = max(0.0, min(1.0, 0.5 + slope))
    # Adoption / proposal activity: count the number of self-modification
    # events in the recent cycles. Each event is read-only evidence that
    # the system *can* modify itself.
    activity = 0.0
    n_cycles = min(15, len(cycles))
    if n_cycles > 0:
        total_events = 0
        for c in cycles[-n_cycles:]:
            dna = c.get("steps", {}).get("dna_proposals", []) or []
            refactor = c.get("steps", {}).get("refactor_proposals", []) or []
            smc = c.get("steps", {}).get("self_modification", {}) or {}
            total_events += len(dna) + len(refactor)
            if smc:
                # Count adoption evidence
                total_events += int(smc.get("adopted_count", 0) or 0)
                total_events += int(smc.get("tested_count", 0) or 0)
        # Saturated at 25 events across the window (encourages activity)
        activity = min(1.0, total_events / 25.0)
    return max(0.0, min(1.0, 0.6 * slope_part + 0.4 * activity))


def planning(cycles: List[Dict[str, Any]]) -> float:
    """Planning: how well-formed are the proposed tasks (priority distribution)."""
    if not cycles:
        return 0.0
    last = cycles[-1]
    tasks = last.get("steps", {}).get("tasks", []) or []
    if not tasks:
        return 0.0
    by_pri = {"high": 3, "medium": 2, "low": 1}
    score = sum(by_pri.get(t.get("priority", "low"), 1) for t in tasks) / (3 * len(tasks))
    return max(0.0, min(1.0, score))


def robustness(cycles: List[Dict[str, Any]]) -> float:
    """Robustness: 1 - error_rate across recent cycles."""
    if not cycles:
        return 0.0
    recent = cycles[-10:]
    if not recent:
        return 0.0
    errs = sum(len(c.get("errors", []) or []) for c in recent)
    return max(0.0, min(1.0, 1.0 - min(1.0, errs / (3 * len(recent)))))


def knowledge_graph_coherence(cycles: List[Dict[str, Any]], data_root: Optional[Path] = None) -> float:
    """KG coherence: node/edge density and recency."""
    if data_root is None:
        return 0.5  # no data root → neutral
    nodes: List[Dict[str, Any]] = []
    kg_path = Path(data_root) / "knowledge_graph.jsonl"
    if kg_path.exists():
        try:
            with kg_path.open("r", encoding="utf-8") as f:
                for ln in f:
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        nodes.append(json.loads(ln))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            return 0.5
    n_nodes = sum(1 for n in nodes if n.get("kind") == "node")
    n_edges = sum(1 for n in nodes if n.get("kind") == "edge")
    if n_nodes == 0:
        return 0.0
    density = min(1.0, (n_edges / max(1, n_nodes)) / 1.5)
    recency = 0.5
    if cycles:
        last = cycles[-1]
        kg = (last.get("steps", {}) or {}).get("knowledge_graph", {}) or {}
        if (kg.get("nodes") or []) or (kg.get("edges") or []):
            recency = 1.0
    return max(0.0, min(1.0, 0.6 * density + 0.4 * recency))


def autonomy(cycles: List[Dict[str, Any]]) -> float:
    """Autonomy: runtime status + uptime persistence + orchestrator independence."""
    if not cycles:
        return 0.0
    last = cycles[-1]
    runtime = (last.get("steps", {}) or {}).get("runtime", {}) or {}
    status = runtime.get("status", "")
    if status == "already_running":
        base = 0.95
    elif status == "started":
        base = 0.6
    else:
        return 0.2  # degraded/no data
    # Bonus: cross-cycle uptime tracked in
    # data/evolution_daemon/runtime_uptime.json
    try:
        from pathlib import Path as _P
        # We try a few candidate roots so the function works inside
        # the web dashboard (data_root) and the daemon (config.repo_root / data)
        candidates = [
            _P("data/evolution_daemon/runtime_uptime.json"),
            _P("evolution_daemon/runtime_uptime.json"),
        ]
        for path in candidates:
            if path.exists():
                import json as _json
                payload = _json.loads(path.read_text(encoding="utf-8"))
                total = float(payload.get("total_uptime_seconds", 0.0))
                # 1h of accumulated uptime → small bonus, capped.
                bonus = min(0.05, total / 3600.0 * 0.05)
                return min(1.0, base + bonus)
    except Exception:  # pragma: no cover - file may be missing
        pass
    return base


# --------------------------------------------------------------------------- #
# Aggregate
# --------------------------------------------------------------------------- #
def compute_ari(cycles: List[Dict[str, Any]], data_root: Optional[Path] = None) -> Dict[str, Any]:
    """Return ARI components, weighted score, and AGI% for comparison.

    The function is *pure*: it takes cycles already in memory and an
    optional data_root (only needed for the KG-coherence axis). It
    can be called from the web dashboard (Flask) or the daemon
    without side effects.
    """
    components = {
        "arc_score": arc_score(cycles),
        "generalization": generalization(cycles),
        "memory_integration": memory_integration(cycles),
        "self_improvement": self_improvement(cycles),
        "planning": planning(cycles),
        "robustness": robustness(cycles),
        "knowledge_graph_coherence": knowledge_graph_coherence(cycles, data_root),
        "autonomy": autonomy(cycles),
    }
    ari_pct = sum(ARI_WEIGHTS[k] * components[k] for k in ARI_WEIGHTS) * 100.0
    # Legacy AGI% is the previous benchmark score (0..100)
    legacy = 0.0
    if cycles:
        last = cycles[-1]
        legacy = float(last.get("steps", {}).get("benchmark", {}).get("agi_percentage", 0.0))
    return {
        "ari_percentage": round(ari_pct, 2),
        "components": {k: round(v, 4) for k, v in components.items()},
        "weights": ARI_WEIGHTS,
        "agi_percentage_legacy": legacy,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def cycle_summary(cycles: List[Dict[str, Any]], data_root: Optional[Path] = None) -> Dict[str, Any]:
    """Quick textual summary for dashboards."""
    ari = compute_ari(cycles, data_root)
    lines = []
    for k, v in ari["components"].items():
        w = ari["weights"][k]
        lines.append(f"{k:30s} {v:.3f} × {w:.2f} = {v*w*100:5.2f}%")
    lines.append("-" * 60)
    lines.append(f"ARI% = {ari['ari_percentage']}   AGI%_legacy = {ari['agi_percentage_legacy']}")
    return {"summary_text": "\n".join(lines), "ari": ari}
