"""Append Phase-1 nodes + edges to data/knowledge_graph.jsonl.

Idempotent: only appends a node id that is not already present, and only
appends an edge (from, to, type) if not already present.
"""

import json
from pathlib import Path

KG_PATH = Path("data/knowledge_graph.jsonl")

NODES = [
    # Cognitive modules (existing)
    ("module:cognition.few_shot_program_induction", "module", "Few-Shot Program Induction"),
    ("module:cognition.spatial_symbolic_reasoning", "module", "Spatial Symbolic Reasoning"),
    ("module:benchmark.arc_agi_adapter", "module", "ARC-AGI Adapter"),
    ("module:benchmark.arc_agi_curriculum", "module", "ARC-AGI Curriculum Engine"),
    # Capability gaps
    ("capability_gap:object_centric_representation", "capability_gap", "Object-Centric Representation (no dedicated module)"),
    ("capability_gap:failure_memory", "capability_gap", "Failure Memory (no persistent structured failures)"),
    ("capability_gap:cognitive_genome", "capability_gap", "Cognitive Genome (DNA lacks primitive/strategy/policy/invariant layers)"),
    # Alerts discovered in Phase 1
    ("alert:chaos_critical_recurrent", "alert", "chaos_critical (severity 2.5, 181 interventions)"),
    ("alert:coherence_phi_critical_false_positive", "alert", "coherence_phi_critical (root cause: missing self_model/morphological writers)"),
    ("alert:drive_instability_energy", "alert", "drive_instability_critical (energy_conservation urgency 0.84 stuck)"),
    # Benchmark results (latest live)
    ("benchmark_result:arc_2026-06-04_phase1", "benchmark_result", "ARC 2/5 (40%) - MMAPR 3/4 accepts (75%)"),
    # Live metrics
    ("metric:runtime_health", "metric", "RuntimeHealthMonitor.health_score=1.0 (no exceptions, no leak)"),
    ("metric:gateway_health", "metric", "AlertEngine.health_score~0.0 (4 critical alerts)"),
]

EDGES = [
    # Cognitive modules: part_of
    ("module:cognition.few_shot_program_induction", "module:benchmark", "part_of"),
    ("module:cognition.spatial_symbolic_reasoning", "module:cellular_brain", "part_of"),
    ("module:benchmark.arc_agi_adapter", "module:benchmark", "part_of"),
    ("module:benchmark.arc_agi_curriculum", "module:benchmark", "part_of"),
    # Capability gaps block AGI alignment
    ("capability_gap:object_centric_representation", "module:cognition.few_shot_program_induction", "blocks"),
    ("capability_gap:object_centric_representation", "module:cognition.spatial_symbolic_reasoning", "blocks"),
    ("capability_gap:failure_memory", "module:benchmark.arc_agi_adapter", "blocks"),
    ("capability_gap:failure_memory", "capability_gap:cognitive_genome", "blocks"),
    ("capability_gap:cognitive_genome", "module:dna", "blocks"),
    ("capability_gap:cognitive_genome", "capability_gap:failure_memory", "blocks"),
    # Alerts point to their root cause
    ("alert:chaos_critical_recurrent", "proposal:prop-ch-002", "root_cause"),
    ("alert:coherence_phi_critical_false_positive", "proposal:prop-ch-001", "root_cause"),
    ("alert:drive_instability_energy", "proposal:prop-ch-003", "root_cause"),
    # Benchmark result
    ("benchmark_result:arc_2026-06-04_phase1", "module:benchmark.arc_agi_adapter", "produced_by"),
    ("benchmark_result:arc_2026-06-04_phase1", "module:cognition.few_shot_program_induction", "depends_on"),
    # Metric provenance
    ("metric:runtime_health", "module:runtime", "produced_by"),
    ("metric:gateway_health", "module:web_gateway", "produced_by"),
    ("metric:gateway_health", "alert:chaos_critical_recurrent", "influenced_by"),
    ("metric:gateway_health", "alert:coherence_phi_critical_false_positive", "influenced_by"),
]


def _existing() -> tuple:
    if not KG_PATH.exists():
        return set(), set()
    node_ids: set = set()
    edge_keys: set = set()
    with KG_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("kind") == "node":
                node_ids.add(rec.get("id"))
            elif rec.get("kind") == "edge":
                edge_keys.add((rec.get("from"), rec.get("to"), rec.get("type")))
    return node_ids, edge_keys


def main() -> int:
    node_ids, edge_keys = _existing()
    added_nodes: list = []
    added_edges: list = []
    with KG_PATH.open("a", encoding="utf-8") as f:
        for nid, ntype, label in NODES:
            if nid in node_ids:
                continue
            f.write(
                json.dumps({"kind": "node", "id": nid, "type": ntype, "label": label}, ensure_ascii=False)
                + "\n"
            )
            added_nodes.append(nid)
        for src, dst, etype in EDGES:
            key = (src, dst, etype)
            if key in edge_keys:
                continue
            f.write(
                json.dumps(
                    {"kind": "edge", "from": src, "to": dst, "type": etype},
                    ensure_ascii=False,
                )
                + "\n"
            )
            added_edges.append(key)
    print(f"Nodes added: {len(added_nodes)} | Edges added: {len(added_edges)}")
    for nid in added_nodes:
        print(f"  + node {nid}")
    for src, dst, etype in added_edges:
        print(f"  + edge {src} -[{etype}]-> {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
