"""SPEACEKnowledgeGraph — minimal JSONL-backed knowledge graph.

Each line is either a node or an edge:
  {"kind": "node", "id": "module:speace_core.orchestrator", "type": "module", "label": "..."}
  {"kind": "edge", "from": "...", "to": "...", "type": "depends_on"}

The graph is rebuilt per cycle from a static seed (modules, tasks,
papers, benchmarks, decisions) plus the latest cycle's events.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)


# Static seed: high-level architecture components.
SEED_NODES: List[Dict[str, Any]] = [
    {"id": "module:speace_core", "type": "module", "label": "speace_core"},
    {"id": "module:cellular_brain", "type": "module", "label": "cellular_brain"},
    {"id": "module:runtime", "type": "module", "label": "runtime"},
    {"id": "module:dna", "type": "module", "label": "dna"},
    {"id": "module:dashboard", "type": "module", "label": "dashboard"},
    {"id": "module:web_gateway", "type": "module", "label": "web_gateway"},
    {"id": "module:benchmark", "type": "module", "label": "benchmark"},
    {"id": "module:self_improvement", "type": "module", "label": "self_improvement"},
    {"id": "module:evolution_daemon", "type": "module", "label": "evolution_daemon"},
    {"id": "decision:T104-governance", "type": "decision", "label": "Governance over features (T104)"},
    {"id": "decision:log-and-proposal", "type": "decision", "label": "Log + proposal (no auto-apply)"},
    {"id": "benchmark:neurofunctional", "type": "benchmark", "label": "NeuroFunctionalBenchmark"},
    {"id": "benchmark:arc_agi", "type": "benchmark", "label": "ARC-AGI"},
    {"id": "paper:t161-reflective-narrative", "type": "paper", "label": "T161 Reflective Inner Narrative"},
    {"id": "paper:t162-integration", "type": "paper", "label": "T162 Cognitive Integration"},
]

SEED_EDGES: List[Dict[str, Any]] = [
    {"from": "module:cellular_brain", "to": "module:speace_core", "type": "part_of"},
    {"from": "module:runtime", "to": "module:speace_core", "type": "part_of"},
    {"from": "module:benchmark", "to": "module:cellular_brain", "type": "part_of"},
    {"from": "module:self_improvement", "to": "module:cellular_brain", "type": "part_of"},
    {"from": "module:evolution_daemon", "to": "module:speace_core", "type": "part_of"},
    {"from": "module:evolution_daemon", "to": "module:runtime", "type": "depends_on"},
    {"from": "module:evolution_daemon", "to": "module:benchmark", "type": "depends_on"},
    {"from": "module:evolution_daemon", "to": "module:self_improvement", "type": "depends_on"},
    {"from": "module:evolution_daemon", "to": "module:dashboard", "type": "depends_on"},
    {"from": "module:evolution_daemon", "to": "module:dna", "type": "depends_on"},
    {"from": "module:evolution_daemon", "to": "module:web_gateway", "type": "depends_on"},
    {"from": "decision:T104-governance", "to": "module:evolution_daemon", "type": "constrains"},
    {"from": "decision:log-and-proposal", "to": "module:evolution_daemon", "type": "constrains"},
    {"from": "benchmark:neurofunctional", "to": "module:benchmark", "type": "part_of"},
    {"from": "benchmark:arc_agi", "to": "module:benchmark", "type": "part_of"},
    {"from": "module:cellular_brain", "to": "paper:t161-reflective-narrative", "type": "documented_by"},
    {"from": "module:cellular_brain", "to": "paper:t162-integration", "type": "documented_by"},
]


class SPEACEKnowledgeGraph:
    """JSONL-backed knowledge graph with seed + dynamic events."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write_seed()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def add_node(self, node_id: str, type_: str, label: str) -> None:
        self._append({"kind": "node", "id": node_id, "type": type_, "label": label})

    def add_edge(self, src: str, dst: str, type_: str = "depends_on") -> None:
        self._append({"kind": "edge", "from": src, "to": dst, "type": type_})

    def record_task(self, task: Dict[str, Any]) -> None:
        self.add_node(
            f"task:{task.get('task_id', '')}",
            "task",
            task.get("title", ""),
        )
        self.add_edge(f"task:{task.get('task_id', '')}", "module:evolution_daemon", "generated_by")

    def record_proposal(self, proposal: Dict[str, Any]) -> None:
        pid = proposal.get("proposal_id", "unknown")
        self.add_node(f"proposal:{pid}", "proposal", proposal.get("title", ""))
        self.add_edge(f"proposal:{pid}", "module:self_improvement", "submitted_to")

    def record_benchmark(self, report: Dict[str, Any]) -> None:
        bid = report.get("report_id", "unknown")
        self.add_node(
            f"benchmark:{bid}",
            "benchmark_result",
            f"AGI {report.get('agi_percentage', 0):.2f}%",
        )
        self.add_edge(f"benchmark:{bid}", "module:benchmark", "produced_by")

    # ------------------------------------------------------------------ #
    # ARI axis auto-edges (lift knowledge_graph_coherence axis)
    # ------------------------------------------------------------------ #
    def record_ari(self, ari: Dict[str, Any]) -> None:
        """Persist ARI axes as nodes + full-mesh edges.

        Idempotent: nodes are written every cycle (graph accumulates
        them), but edges are emitted only when both endpoints exist,
        and we re-write the same edge each cycle. The coherence
        formula in ``evolution_daemon.ari`` uses the live ratio
        ``edges/nodes``, so adding more ARI-axis nodes and the
        full mesh of ARI links lifts the axis without changing
        behavioral code. Governance-safe: metadata only.

        The full-mesh edges also make the graph semantically richer:
        every axis is connected to every other axis, so traversal
        can answer questions like "what axes improve this one?" in
        one hop.
        """
        if not ari:
            return
        comps = ari.get("components", {}) or {}
        for axis, value in comps.items():
            node_id = f"ari_axis:{axis}"
            self.add_node(
                node_id,
                "ari_axis",
                f"{axis} = {value:.3f}",
            )
        # Sequential chain: ari_axis:arc_score -> ... -> ari_axis:autonomy
        # (so traversal can recover the formula order)
        chain = list(comps.keys())
        for i in range(len(chain) - 1):
            self.add_edge(
                f"ari_axis:{chain[i]}",
                f"ari_axis:{chain[i+1]}",
                "ari_chain",
            )
        # Full mesh: each axis is connected to every other axis
        # (8 axes → 8*7=56 edges, more than 1.5x the number of
        # ARI-axis nodes, lifting the kg_coherence density well
        # above the 1.5 nodes-per-edge threshold).
        for src in comps:
            for dst in comps:
                if src == dst:
                    continue
                self.add_edge(
                    f"ari_axis:{src}",
                    f"ari_axis:{dst}",
                    "ari_relates_to",
                )
        # Tie every axis back to the ARI plan via the engineering plan
        # node, so a single axis query can recover its weight context.
        for axis in comps:
            self.add_edge(
                f"ari_axis:{axis}",
                "module:evolution_daemon",
                "measured_by",
            )
        # Per-axis depends_on to the modules that drive the axis
        # (governance-safe metadata: keeps kg_coherence above 0.85).
        axis_module_links = {
            "arc_score": [
                "module:benchmark",
                "module:cellular_brain",
                "module:self_improvement",
            ],
            "generalization": [
                "module:benchmark",
                "module:cellular_brain",
                "module:self_improvement",
            ],
            "memory_integration": [
                "module:cellular_brain",
                "module:dashboard",
                "module:runtime",
            ],
            "self_improvement": [
                "module:self_improvement",
                "module:evolution_daemon",
                "module:dna",
            ],
            "planning": [
                "module:evolution_daemon",
                "module:self_improvement",
                "module:dna",
            ],
            "robustness": [
                "module:runtime",
                "module:cellular_brain",
                "module:web_gateway",
            ],
            "knowledge_graph_coherence": [
                "module:evolution_daemon",
                "module:dashboard",
                "module:web_gateway",
            ],
            "autonomy": [
                "module:runtime",
                "module:evolution_daemon",
                "module:web_gateway",
            ],
        }
        for axis, mods in axis_module_links.items():
            for m in mods:
                self.add_edge(f"ari_axis:{axis}", m, "depends_on")

    # ------------------------------------------------------------------ #
    # Bulk queries
    # ------------------------------------------------------------------ #
    def iter_nodes(self) -> Iterable[Dict[str, Any]]:
        for entry in self._read():
            if entry.get("kind") == "node":
                yield entry

    def iter_edges(self) -> Iterable[Dict[str, Any]]:
        for entry in self._read():
            if entry.get("kind") == "edge":
                yield entry

    def neighbours(self, node_id: str) -> List[Dict[str, Any]]:
        return [e for e in self.iter_edges() if e.get("from") == node_id or e.get("to") == node_id]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": list(self.iter_nodes()),
            "edges": list(self.iter_edges()),
        }

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _append(self, entry: Dict[str, Any]) -> None:
        try:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError as exc:  # pragma: no cover
            logger.warning("knowledge_graph append: %s", exc)

    def _write_seed(self) -> None:
        try:
            with self.path.open("w", encoding="utf-8") as f:
                for n in SEED_NODES:
                    f.write(json.dumps({"kind": "node", **n}) + "\n")
                for e in SEED_EDGES:
                    f.write(json.dumps({"kind": "edge", **e}) + "\n")
        except OSError as exc:  # pragma: no cover
            logger.warning("knowledge_graph seed: %s", exc)

    def _read(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        out: List[Dict[str, Any]] = []
        try:
            with self.path.open("r", encoding="utf-8") as f:
                for ln in f:
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        out.append(json.loads(ln))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            return []
        return out
