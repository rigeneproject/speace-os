"""HierarchicalConceptAbstractionLayer — T159.

Builds a probabilistic hierarchical concept graph atop flat T157 concepts
and T153 causal observations, with human-gated abstraction.

Pipeline:
    flat concepts + causal observations
    → level-1 nodes in ConceptGraph
    → category detection (level-2)
    → schema detection (level-3)
    → human validation gate
    → semantic consolidation
    → deprecation/rollback possible
"""

from __future__ import annotations

import json
import time
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from speace_core.cellular_brain.cognition.concept_graph import ConceptGraph


class HierarchicalConceptAbstractionLayer:
    """Produces hierarchical abstractions from episodic concepts and causal observations."""

    def __init__(
        self,
        concept_graph: Optional[ConceptGraph] = None,
        data_root: str = "data/cognition/concept_abstraction",
        category_similarity_threshold: float = 0.5,
        schema_min_observations: int = 3,
        schema_confidence_threshold: float = 0.6,
    ) -> None:
        self._graph = concept_graph or ConceptGraph(data_root=data_root)
        self._data_root = Path(data_root)
        self._data_root.mkdir(parents=True, exist_ok=True)
        self._candidates_path = self._data_root / "abstraction_candidates.jsonl"

        self._category_sim_threshold = category_similarity_threshold
        self._schema_min_obs = schema_min_observations
        self._schema_conf_threshold = schema_confidence_threshold

        self._candidates: Dict[str, Dict[str, Any]] = {}
        self._load_candidates()

    # ------------------------------------------------------------------ #
    # Ingestion
    # ------------------------------------------------------------------ #

    def ingest(self, episodic_layer: Any, causal_model: Any) -> List[Dict[str, Any]]:
        """Pull sources, update graph, detect new abstraction candidates."""
        new_candidates: List[Dict[str, Any]] = []

        # 1. Pull flat concepts (level-1)
        flat_concepts = []
        if episodic_layer is not None:
            try:
                flat_concepts = episodic_layer.list_concepts(limit=500)
            except Exception:
                flat_concepts = []

        # 2. Ensure level-1 nodes exist in graph
        self._ensure_level1_nodes(flat_concepts)

        # 3. Pull causal observations
        observations = []
        if causal_model is not None:
            try:
                observations = causal_model.recent_observations(limit=500)
            except Exception:
                observations = []

        # 4. Map causal edges onto level-1 labels
        self._update_causal_edges(observations)

        # 5. Detect category candidates (level-2)
        category_candidates = self._detect_categories(flat_concepts)
        for cand in category_candidates:
            cid = cand["candidate_id"]
            if cid not in self._candidates:
                self._candidates[cid] = cand
                self._persist_candidate(cand)
                new_candidates.append(cand)

        # 6. Detect schema candidates (level-3)
        schema_candidates = self._detect_schemas(observations)
        for cand in schema_candidates:
            cid = cand["candidate_id"]
            if cid not in self._candidates:
                self._candidates[cid] = cand
                self._persist_candidate(cand)
                new_candidates.append(cand)

        return new_candidates

    # ------------------------------------------------------------------ #
    # Gates
    # ------------------------------------------------------------------ #

    def list_candidates(self, status: str = "pending", limit: int = 100) -> List[Dict[str, Any]]:
        items = [c for c in self._candidates.values() if c.get("status") == status]
        items.sort(key=lambda x: x.get("formed_at", 0), reverse=True)
        return items[:limit]

    def approve_abstraction(self, candidate_id: str, reviewer: str) -> Optional[Dict[str, Any]]:
        candidate = self._candidates.get(candidate_id)
        if not candidate or candidate.get("status") != "pending":
            return None

        level = candidate.get("level", 2)
        label = candidate["label"]
        parents = candidate.get("parents", [])
        causal_links = candidate.get("causal_links", [])
        symbolic_signature = candidate.get("symbolic_signature", [])
        confidence = candidate.get("confidence", 0.5)

        # Wire children links in parents (parents are stored as labels)
        for parent_label in parents:
            parent_node = self._graph.get_node_by_label(parent_label)
            if parent_node:
                if label not in parent_node.get("children", []):
                    parent_node.setdefault("children", []).append(label)
                    self._graph.update_node(parent_node["node_id"], parent_node)

        node = self._graph.add_node(
            label=label,
            level=level,
            parents=parents,
            causal_links=causal_links,
            symbolic_signature=symbolic_signature,
            confidence=confidence,
            status="approved",
            reviewer=reviewer,
        )

        candidate["status"] = "approved"
        candidate["reviewer"] = reviewer
        candidate["approved_at"] = time.time()
        candidate["node_id"] = node["node_id"]
        self._persist_candidate(candidate)
        return node

    def reject_abstraction(self, candidate_id: str, reviewer: str) -> bool:
        candidate = self._candidates.get(candidate_id)
        if not candidate:
            return False
        candidate["status"] = "rejected"
        candidate["reviewer"] = reviewer
        candidate["rejected_at"] = time.time()
        self._persist_candidate(candidate)
        return True

    def deprecate_abstraction(self, node_id: str, reviewer: str) -> Optional[Dict[str, Any]]:
        """Rollback an approved abstraction via soft deprecation."""
        return self._graph.deprecate_node(node_id, reviewer)

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def get_hierarchy(self, label: str, depth: int = 3) -> Dict[str, Any]:
        """Return ancestors and descendants tree for a label."""
        node = self._graph.get_node_by_label(label)
        if not node:
            return {"label": label, "exists": False}
        nid = node["node_id"]
        return {
            "label": label,
            "node_id": nid,
            "level": node["level"],
            "ancestors": self._graph.get_ancestors(nid, depth=depth),
            "descendants": self._graph.get_descendants(nid, depth=depth),
        }

    def get_schema(self, label: str) -> List[Dict[str, Any]]:
        """Return causal schemas involving this label."""
        return self._graph.get_causal_schemas(label)

    def summary(self) -> Dict[str, Any]:
        graph_summary = self._graph.summary()
        pending = sum(1 for c in self._candidates.values() if c.get("status") == "pending")
        approved = sum(1 for c in self._candidates.values() if c.get("status") == "approved")
        rejected = sum(1 for c in self._candidates.values() if c.get("status") == "rejected")
        return {
            **graph_summary,
            "pending_candidates": pending,
            "approved_candidates": approved,
            "rejected_candidates": rejected,
        }

    # ------------------------------------------------------------------ #
    # Internal: level-1 nodes
    # ------------------------------------------------------------------ #

    def _ensure_level1_nodes(self, flat_concepts: List[Dict[str, Any]]) -> None:
        for concept in flat_concepts:
            label = concept.get("concept_label")
            if not label:
                continue
            existing = self._graph.get_node_by_label(label)
            if existing:
                # Refresh confidence if present
                existing["confidence"] = max(existing.get("confidence", 0.5), concept.get("confidence", 0.5))
                self._graph.update_node(existing["node_id"], existing)
            else:
                self._graph.add_node(
                    label=label,
                    level=1,
                    symbolic_signature=concept.get("symbolic_signature", []),
                    confidence=concept.get("confidence", 0.5),
                    status="approved",
                )

    # ------------------------------------------------------------------ #
    # Internal: causal edges
    # ------------------------------------------------------------------ #

    def _update_causal_edges(self, observations: List[Dict[str, Any]]) -> None:
        """Map action/effect strings onto level-1 labels and add causal_links."""
        for obs in observations:
            action_name = obs.get("action_name", "")
            effect = obs.get("effect", "")
            confidence = obs.get("confidence", 0.0)
            if not action_name or not effect:
                continue

            cause_node = self._graph.get_node_by_label(action_name)
            if cause_node is None:
                # Try fuzzy match against level-1 labels
                cause_node = self._fuzzy_match_label(action_name)
            effect_node = self._graph.get_node_by_label(effect)
            if effect_node is None:
                effect_node = self._fuzzy_match_label(effect)

            if cause_node and effect_node:
                self._append_causal_link(cause_node, effect_node["label"], confidence)

    def _fuzzy_match_label(self, token: str) -> Optional[Dict[str, Any]]:
        token_set = set(token.lower().split("_"))
        best: Optional[Dict[str, Any]] = None
        best_score = 0.0
        for node in self._graph.list_nodes(level=1, status="approved"):
            label_set = set(node.get("label", "").lower().split("_"))
            inter = len(token_set & label_set)
            union = len(token_set | label_set)
            score = inter / union if union > 0 else 0.0
            if score > best_score:
                best_score = score
                best = node
        return best if best_score >= 0.5 else None

    def _append_causal_link(self, cause_node: Dict[str, Any], effect_label: str, confidence: float) -> None:
        links = cause_node.setdefault("causal_links", [])
        for link in links:
            target_node = self._graph.get_node(link.get("target", ""))
            if target_node and target_node.get("label") == effect_label:
                # Update existing weighted average
                old_conf = link.get("confidence", 0.0)
                count = link.get("obs_count", 1)
                new_conf = (old_conf * count + confidence) / (count + 1)
                link["confidence"] = round(new_conf, 4)
                link["obs_count"] = count + 1
                self._graph.update_node(cause_node["node_id"], cause_node)
                return
        effect_node = self._graph.get_node_by_label(effect_label)
        if effect_node:
            links.append({
                "target": effect_node["node_id"],
                "confidence": round(confidence, 4),
                "obs_count": 1,
            })
            self._graph.update_node(cause_node["node_id"], cause_node)

    # ------------------------------------------------------------------ #
    # Internal: category detection (level-2)
    # ------------------------------------------------------------------ #

    def _detect_categories(self, flat_concepts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        n = len(flat_concepts)
        if n < 2:
            return candidates

        sigs: List[Set[str]] = []
        for concept in flat_concepts:
            sig = set(concept.get("symbolic_signature", []))
            if not sig:
                desc = concept.get("concept_label", "")
                sig = {t.strip(".,;:!?") for t in desc.lower().split("_") if len(t) > 2}
            sigs.append(sig)

        for i in range(n):
            for j in range(i + 1, n):
                sim = self._jaccard(sigs[i], sigs[j])
                if sim >= self._category_sim_threshold:
                    # Require shared causal target for cohesion
                    shared_targets = self._shared_causal_targets(
                        flat_concepts[i].get("concept_label", ""),
                        flat_concepts[j].get("concept_label", ""),
                    )
                    if not shared_targets:
                        continue
                    shared_tokens = sorted(sigs[i] & sigs[j])
                    if not shared_tokens:
                        continue
                    label = "cat_" + "_".join(shared_tokens[:3])
                    if self._graph.get_node_by_label(label):
                        continue
                    cid = f"cand_{uuid.uuid4().hex[:8]}"
                    candidates.append({
                        "candidate_id": cid,
                        "label": label,
                        "level": 2,
                        "parents": [
                            flat_concepts[i].get("concept_label", ""),
                            flat_concepts[j].get("concept_label", ""),
                        ],
                        "symbolic_signature": shared_tokens,
                        "confidence": round(sim, 4),
                        "status": "pending",
                        "formed_at": time.time(),
                        "shared_causal_targets": shared_targets,
                    })
        return candidates

    def _shared_causal_targets(self, label_a: str, label_b: str) -> List[str]:
        node_a = self._graph.get_node_by_label(label_a)
        node_b = self._graph.get_node_by_label(label_b)
        if not node_a or not node_b:
            return []
        targets_a = set()
        for link in node_a.get("causal_links", []):
            target_node = self._graph.get_node(link.get("target", ""))
            if target_node:
                targets_a.add(target_node.get("label", ""))
        targets_b = set()
        for link in node_b.get("causal_links", []):
            target_node = self._graph.get_node(link.get("target", ""))
            if target_node:
                targets_b.add(target_node.get("label", ""))
        return sorted(targets_a & targets_b)

    # ------------------------------------------------------------------ #
    # Internal: schema detection (level-3)
    # ------------------------------------------------------------------ #

    def _detect_schemas(self, observations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Look for recurrent causal motifs between categories (level-2 nodes)."""
        candidates: List[Dict[str, Any]] = []
        categories = self._graph.list_nodes(level=2, status="approved")
        if len(categories) < 2:
            return candidates

        # Build observation count matrix between category labels
        cat_labels = {c["label"] for c in categories}
        motif_counts: Dict[tuple, List[float]] = defaultdict(list)

        for obs in observations:
            action = obs.get("action_name", "")
            effect = obs.get("effect", "")
            conf = obs.get("confidence", 0.0)
            # Map action/effect to categories via fuzzy match
            cause_cat = self._fuzzy_match_to_category(action, cat_labels)
            effect_cat = self._fuzzy_match_to_category(effect, cat_labels)
            if cause_cat and effect_cat and cause_cat != effect_cat:
                motif_counts[(cause_cat, effect_cat)].append(conf)

        for (cause, effect), confs in motif_counts.items():
            if len(confs) < self._schema_min_obs:
                continue
            avg_conf = sum(confs) / len(confs)
            if avg_conf < self._schema_conf_threshold:
                continue
            label = f"schema_{cause}_to_{effect}"
            if self._graph.get_node_by_label(label):
                continue
            cid = f"cand_{uuid.uuid4().hex[:8]}"
            cause_node = self._graph.get_node_by_label(cause)
            effect_node = self._graph.get_node_by_label(effect)
            candidates.append({
                "candidate_id": cid,
                "label": label,
                "level": 3,
                "parents": [cause, effect],
                "symbolic_signature": sorted(
                    set((cause_node or {}).get("symbolic_signature", []))
                    | set((effect_node or {}).get("symbolic_signature", []))
                ),
                "confidence": round(avg_conf, 4),
                "status": "pending",
                "formed_at": time.time(),
                "observation_count": len(confs),
            })
        return candidates

    def _fuzzy_match_to_category(self, token: str, cat_labels: Set[str]) -> Optional[str]:
        token_set = set(token.lower().split("_"))
        best_label: Optional[str] = None
        best_score = 0.0
        for label in cat_labels:
            label_set = set(label.lower().split("_"))
            inter = len(token_set & label_set)
            union = len(token_set | label_set)
            score = inter / union if union > 0 else 0.0
            if score > best_score:
                best_score = score
                best_label = label
        return best_label if best_score >= 0.5 else None

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _jaccard(a: Set[str], b: Set[str]) -> float:
        if not a and not b:
            return 1.0
        inter = len(a & b)
        union = len(a | b)
        return inter / union if union > 0 else 0.0

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _persist_candidate(self, candidate: Dict[str, Any]) -> None:
        try:
            with self._candidates_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(candidate, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _load_candidates(self) -> None:
        if not self._candidates_path.exists():
            return
        lines = self._candidates_path.read_text(encoding="utf-8").strip().split("\n")
        for line in lines:
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                cid = obj.get("candidate_id")
                if cid:
                    self._candidates[cid] = obj
            except json.JSONDecodeError:
                continue
