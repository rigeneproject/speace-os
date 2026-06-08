"""ConceptGraph — lightweight probabilistic DAG for hierarchical concepts (T159)."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


class ConceptGraph:
    """Directed acyclic graph of concept nodes with confidence-weighted edges.

    Levels:
        1 — flat concept (from T157)
        2 — category (cluster of level-1 concepts)
        3 — abstract schema (recurrent causal pattern across categories)
    """

    def __init__(self, data_root: str = "data/cognition/concept_graph") -> None:
        self._data_root = Path(data_root)
        self._data_root.mkdir(parents=True, exist_ok=True)
        self._nodes_path = self._data_root / "nodes.jsonl"
        self._rejected_path = self._data_root / "rejected_abstractions.jsonl"
        self._deprecation_path = self._data_root / "deprecated_abstractions.jsonl"

        self._nodes: Dict[str, Dict[str, Any]] = {}
        self._load()

    # ------------------------------------------------------------------ #
    # Node management
    # ------------------------------------------------------------------ #

    def add_node(
        self,
        label: str,
        level: int,
        parents: Optional[List[str]] = None,
        children: Optional[List[str]] = None,
        causal_links: Optional[List[Dict[str, Any]]] = None,
        symbolic_signature: Optional[List[str]] = None,
        confidence: float = 0.5,
        status: str = "approved",
        reviewer: Optional[str] = None,
        node_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Insert or update a node."""
        nid = node_id or f"node_{uuid.uuid4().hex[:8]}"
        node = {
            "node_id": nid,
            "label": label,
            "level": level,
            "parents": parents or [],
            "children": children or [],
            "causal_links": causal_links or [],
            "symbolic_signature": symbolic_signature or [],
            "confidence": round(max(0.0, min(1.0, confidence)), 4),
            "status": status,
            "reviewer": reviewer,
            "created_at": time.time(),
        }
        self._nodes[nid] = node
        self._persist_node(node)
        return node

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        return self._nodes.get(node_id)

    def update_node(self, node_id: str, node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an existing node dict in place and persist."""
        if node_id not in self._nodes:
            return None
        self._nodes[node_id] = node
        self._persist_node(node)
        return node

    def get_node_by_label(self, label: str) -> Optional[Dict[str, Any]]:
        for node in self._nodes.values():
            if node.get("label") == label and node.get("status") != "deprecated":
                return node
        return None

    def list_nodes(
        self,
        level: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for node in self._nodes.values():
            if level is not None and node.get("level") != level:
                continue
            if status is not None and node.get("status") != status:
                continue
            results.append(node)
        results.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        return results[:limit]

    def deprecate_node(self, node_id: str, reviewer: str) -> Optional[Dict[str, Any]]:
        node = self._nodes.get(node_id)
        if not node:
            return None
        node["status"] = "deprecated"
        node["reviewer"] = reviewer
        node["deprecated_at"] = time.time()
        # Sever children links (downstream isolation), keep parents for history
        for child_id in node.get("children", []):
            child = self._nodes.get(child_id)
            if child and node_id in child.get("parents", []):
                child["parents"] = [p for p in child["parents"] if p != node_id]
                self._persist_node(child)
        node["children"] = []
        self._persist_node(node)
        self._persist_deprecation(node)
        return node

    # ------------------------------------------------------------------ #
    # Graph traversal
    # ------------------------------------------------------------------ #

    def get_ancestors(self, node_id: str, depth: int = 3) -> Dict[str, Any]:
        """Return a nested dict of ancestors up to depth."""
        node = self._nodes.get(node_id)
        if not node:
            return {}
        return self._build_tree(node_id, direction="parents", depth=depth, visited=set())

    def get_descendants(self, node_id: str, depth: int = 3) -> Dict[str, Any]:
        """Return a nested dict of descendants up to depth."""
        node = self._nodes.get(node_id)
        if not node:
            return {}
        return self._build_tree(node_id, direction="children", depth=depth, visited=set())

    def get_causal_schemas(self, label: str) -> List[Dict[str, Any]]:
        """Return causal links where this label is cause or effect."""
        schemas: List[Dict[str, Any]] = []
        node = self.get_node_by_label(label)
        if not node:
            return schemas
        nid = node["node_id"]
        # Outgoing
        for link in node.get("causal_links", []):
            target = self._nodes.get(link.get("target"))
            if target and target.get("status") != "deprecated":
                schemas.append({
                    "direction": "outgoing",
                    "cause_label": label,
                    "effect_label": target.get("label"),
                    "confidence": link.get("confidence"),
                    "obs_count": link.get("obs_count"),
                })
        # Incoming
        for other in self._nodes.values():
            if other.get("status") == "deprecated" or other["node_id"] == nid:
                continue
            for link in other.get("causal_links", []):
                if link.get("target") == nid:
                    schemas.append({
                        "direction": "incoming",
                        "cause_label": other.get("label"),
                        "effect_label": label,
                        "confidence": link.get("confidence"),
                        "obs_count": link.get("obs_count"),
                    })
        return schemas

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _build_tree(
        self,
        node_id: str,
        direction: str,
        depth: int,
        visited: Set[str],
    ) -> Dict[str, Any]:
        if depth <= 0 or node_id in visited:
            return {}
        visited.add(node_id)
        node = self._nodes.get(node_id)
        if not node:
            return {}
        children_ids = node.get(direction, [])
        branches: List[Dict[str, Any]] = []
        for cid in children_ids:
            child = self._nodes.get(cid)
            if child and child.get("status") != "deprecated":
                branch = self._build_tree(cid, direction, depth - 1, visited)
                if branch:
                    branches.append(branch)
        result: Dict[str, Any] = {
            "node_id": node["node_id"],
            "label": node["label"],
            "level": node["level"],
            "confidence": node["confidence"],
        }
        if branches:
            result["branches"] = branches
        return result

    def _persist_node(self, node: Dict[str, Any]) -> None:
        try:
            with self._nodes_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(node, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _persist_deprecation(self, node: Dict[str, Any]) -> None:
        try:
            with self._deprecation_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(node, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _load(self) -> None:
        if not self._nodes_path.exists():
            return
        lines = self._nodes_path.read_text(encoding="utf-8").strip().split("\n")
        for line in lines:
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                nid = obj.get("node_id")
                if nid:
                    self._nodes[nid] = obj
            except json.JSONDecodeError:
                continue

    # ------------------------------------------------------------------ #
    # Stats
    # ------------------------------------------------------------------ #

    def summary(self) -> Dict[str, Any]:
        total = len(self._nodes)
        deprecated = sum(1 for n in self._nodes.values() if n.get("status") == "deprecated")
        active = total - deprecated
        by_level: Dict[int, int] = {}
        for n in self._nodes.values():
            if n.get("status") != "deprecated":
                by_level[n.get("level", 0)] = by_level.get(n.get("level", 0), 0) + 1
        return {
            "total_nodes": total,
            "active_nodes": active,
            "deprecated_nodes": deprecated,
            "by_level": by_level,
        }
