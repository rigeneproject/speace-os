"""EcosystemGraph — T131-B: relational and systemic mapping of the ecosystem.

Builds a dynamic graph of ecosystem sources, infers relationships using
SemanticMapper, and identifies organismic clusters (systems).
"""

from typing import Any, Dict, List, Optional, Set, Tuple

from speace_core.ecosystem.ecosystem_state import EcosystemSource
from speace_core.ecosystem.semantic_mapper import SemanticMapper


class EcosystemGraph:
    """Graph of ecosystem sources with organismic relationship inference.

    T131-B uses this to build a "cognitive map" of the macro-ecosystem.
    """

    def __init__(self, mapper: Optional[SemanticMapper] = None) -> None:
        self._mapper = mapper or SemanticMapper()
        self._nodes: Dict[str, Dict[str, Any]] = {}
        self._edges: List[Tuple[str, str, str]] = []

    # ------------------------------------------------------------------ #
    # Node management
    # ------------------------------------------------------------------ #

    def add_source(self, source: EcosystemSource) -> None:
        """Add or update a source in the graph."""
        desc = self._mapper.describe(source.source_type)
        self._nodes[source.source_id] = {
            "source_id": source.source_id,
            "source_type": source.source_type,
            "trust_score": source.trust_score,
            "active": source.active,
            "semantic": desc,
        }

    def remove_source(self, source_id: str) -> None:
        """Remove a source and its edges."""
        self._nodes.pop(source_id, None)
        self._edges = [e for e in self._edges if e[0] != source_id and e[1] != source_id]

    def get_node(self, source_id: str) -> Optional[Dict[str, Any]]:
        return self._nodes.get(source_id)

    def list_nodes(self) -> List[Dict[str, Any]]:
        return list(self._nodes.values())

    # ------------------------------------------------------------------ #
    # Edge / relationship inference
    # ------------------------------------------------------------------ #

    def infer_edges(self) -> None:
        """Infer all possible edges between nodes based on semantic hints."""
        self._edges = []
        ids = list(self._nodes.keys())
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                rel = self._mapper.infer_relationship(
                    self._nodes[a]["source_type"],
                    self._nodes[b]["source_type"],
                )
                if rel and rel != "unrelated":
                    self._edges.append((a, b, rel))

    def edges_for(self, source_id: str) -> List[Dict[str, Any]]:
        """Return all edges connected to a source."""
        result: List[Dict[str, Any]] = []
        for a, b, rel in self._edges:
            if a == source_id:
                result.append({"from": a, "to": b, "relation": rel})
            elif b == source_id:
                result.append({"from": b, "to": a, "relation": rel})
        return result

    # ------------------------------------------------------------------ #
    # Systemic clustering
    # ------------------------------------------------------------------ #

    def clusters_by_system(self) -> Dict[str, List[str]]:
        """Group node IDs by organismic system class."""
        clusters: Dict[str, List[str]] = {}
        for sid, node in self._nodes.items():
            system = node["semantic"].get("system_class")
            if system is None:
                continue
            clusters.setdefault(system, []).append(sid)
        return clusters

    def functional_pathways(self) -> Dict[str, List[List[str]]]:
        """Find simple pathways from input → processing → output."""
        inputs: List[str] = []
        outputs: List[str] = []
        processing: List[str] = []
        for sid, node in self._nodes.items():
            role = node["semantic"].get("functional_role")
            if role == "input":
                inputs.append(sid)
            elif role == "output":
                outputs.append(sid)
            elif role == "processing":
                processing.append(sid)

        pathways: Dict[str, List[List[str]]] = {}
        for inp in inputs:
            for out in outputs:
                # Find simple 2-hop paths via processing nodes
                found: List[List[str]] = []
                for proc in processing:
                    if self._connected(inp, proc) and self._connected(proc, out):
                        found.append([inp, proc, out])
                if found:
                    pathways[f"{inp}_to_{out}"] = found
        return pathways

    def _connected(self, a: str, b: str) -> bool:
        for ea, eb, _ in self._edges:
            if (ea == a and eb == b) or (ea == b and eb == a):
                return True
        return False

    # ------------------------------------------------------------------ #
    # Summary
    # ------------------------------------------------------------------ #

    def summary(self) -> Dict[str, Any]:
        """Return a human-readable summary of the ecosystem graph."""
        clusters = self.clusters_by_system()
        pathways = self.functional_pathways()
        return {
            "node_count": len(self._nodes),
            "edge_count": len(self._edges),
            "systems": {k: len(v) for k, v in clusters.items()},
            "pathways_detected": len(pathways),
            "clusters": clusters,
        }

    def describe_map(self) -> str:
        """Generate a reflective narrative of the ecosystem map."""
        summary = self.summary()
        lines = [
            "Ecosystem Cognitive Map",
            f"Sources: {summary['node_count']}, Relationships: {summary['edge_count']}",
            "Organismic Systems:",
        ]
        for system, count in summary["systems"].items():
            lines.append(f"  - {system}: {count} source(s)")
        if summary["pathways_detected"]:
            lines.append(f"Functional pathways detected: {summary['pathways_detected']}")
        else:
            lines.append("No complete functional pathways detected yet.")
        return "\n".join(lines)
