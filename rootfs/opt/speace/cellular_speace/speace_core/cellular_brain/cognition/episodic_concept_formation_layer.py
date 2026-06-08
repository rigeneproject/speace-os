"""EpisodicConceptFormationLayer — T157.

Emerges stable concepts from repeated episodes.

Pipeline:
    episodic memory / narrative events
    → similarity clustering (Jaccard on symbolic labels)
    → recurrent pattern detection (co-occurrence counts)
    → symbolic abstraction (concept candidate label)
    → human validation (pending → approved)
    → semantic consolidation (ground in SymbolicGroundingEngine)

Constraints:
- no autonomous concept injection
- human validation required before consolidation
- read-only observation until approval
"""

from __future__ import annotations

import json
import math
import time
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


class EpisodicConceptFormationLayer:
    """Forms concepts from clustered episodes."""

    def __init__(
        self,
        narrative_engine: Any,
        grounding_engine: Any,
        data_root: str = "data/cognition/concept_formation",
        similarity_threshold: float = 0.6,
        min_cluster_size: int = 3,
    ) -> None:
        self._narrative = narrative_engine
        self._grounding = grounding_engine
        self._data_root = Path(data_root)
        self._data_root.mkdir(parents=True, exist_ok=True)
        self._candidates_path = self._data_root / "concept_candidates.jsonl"
        self._concepts_path = self._data_root / "consolidated_concepts.jsonl"

        self._similarity_threshold = similarity_threshold
        self._min_cluster_size = min_cluster_size

        self._candidates: Dict[str, Dict[str, Any]] = {}
        self._concepts: Dict[str, Dict[str, Any]] = {}
        self._load()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def ingest_recent_episodes(self, hours: float = 168) -> List[Dict[str, Any]]:
        """Read recent narrative events and attempt concept formation."""
        if self._narrative is None:
            return []
        episodes = self._narrative.recent(hours=hours, limit=500)
        if len(episodes) < self._min_cluster_size:
            return []

        clusters = self._cluster_episodes(episodes)
        new_candidates: List[Dict[str, Any]] = []
        for cluster in clusters:
            if len(cluster) >= self._min_cluster_size:
                candidate = self._form_concept_candidate(cluster)
                if candidate:
                    self._candidates[candidate["candidate_id"]] = candidate
                    self._persist_candidate(candidate)
                    new_candidates.append(candidate)
        return new_candidates

    def approve_candidate(self, candidate_id: str, reviewer: str) -> Optional[Dict[str, Any]]:
        """Human-approved concept becomes semantically consolidated."""
        candidate = self._candidates.get(candidate_id)
        if not candidate:
            return None
        if candidate.get("status") != "pending":
            return None

        concept_label = candidate["concept_label"]
        assembly_id = f"asm_concept_{uuid.uuid4().hex[:6]}"

        # Consolidate in SymbolicGroundingEngine
        if self._grounding is not None:
            try:
                self._grounding.ground_assembly(assembly_id, concept_label)
            except Exception:
                pass

        concept = {
            "concept_id": f"concept_{uuid.uuid4().hex[:8]}",
            "candidate_id": candidate_id,
            "concept_label": concept_label,
            "assembly_id": assembly_id,
            "status": "consolidated",
            "reviewer": reviewer,
            "episode_count": candidate["episode_count"],
            "symbolic_signature": candidate["symbolic_signature"],
            "consolidated_at": time.time(),
        }
        self._concepts[concept["concept_id"]] = concept
        self._persist_concept(concept)

        candidate["status"] = "consolidated"
        self._persist_candidate(candidate)
        return concept

    def reject_candidate(self, candidate_id: str, reviewer: str) -> bool:
        candidate = self._candidates.get(candidate_id)
        if not candidate:
            return False
        candidate["status"] = "rejected"
        candidate["reviewer"] = reviewer
        self._persist_candidate(candidate)
        return True

    def list_candidates(self, status: Optional[str] = "pending", limit: int = 100) -> List[Dict[str, Any]]:
        items = list(self._candidates.values())
        if status:
            items = [c for c in items if c.get("status") == status]
        items.sort(key=lambda x: x.get("formed_at", 0), reverse=True)
        return items[:limit]

    def list_concepts(self, limit: int = 100) -> List[Dict[str, Any]]:
        items = list(self._concepts.values())
        items.sort(key=lambda x: x.get("consolidated_at", 0), reverse=True)
        return items[:limit]

    def summary(self) -> Dict[str, Any]:
        pending = sum(1 for c in self._candidates.values() if c.get("status") == "pending")
        consolidated = len(self._concepts)
        rejected = sum(1 for c in self._candidates.values() if c.get("status") == "rejected")
        return {
            "pending_candidates": pending,
            "consolidated_concepts": consolidated,
            "rejected_candidates": rejected,
            "total_episodes_ingested": sum(
                c.get("episode_count", 0) for c in self._candidates.values()
            ),
        }

    # ------------------------------------------------------------------ #
    # Clustering
    # ------------------------------------------------------------------ #

    def _cluster_episodes(self, episodes: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Simple threshold-based agglomerative clustering on Jaccard similarity."""
        signatures = [self._extract_signature(ep) for ep in episodes]
        n = len(episodes)
        parent = list(range(n))

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def union(i: int, j: int) -> None:
            pi, pj = find(i), find(j)
            if pi != pj:
                parent[pi] = pj

        for i in range(n):
            for j in range(i + 1, n):
                sim = self._jaccard(signatures[i], signatures[j])
                if sim >= self._similarity_threshold:
                    union(i, j)

        clusters: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        for i, ep in enumerate(episodes):
            clusters[find(i)].append(ep)
        return list(clusters.values())

    @staticmethod
    def _extract_signature(episode: Dict[str, Any]) -> Set[str]:
        """Extract a set of symbolic tokens from an episode."""
        sig: Set[str] = set()
        desc = episode.get("description", "")
        # Simple tokenization: lowercase words
        for token in desc.lower().split():
            token = token.strip(".,;:!?")
            if len(token) > 2:
                sig.add(token)
        metadata = episode.get("metadata", {})
        if isinstance(metadata, dict):
            for key, val in metadata.items():
                if isinstance(val, str):
                    sig.add(val.lower())
                elif isinstance(val, list):
                    for item in val:
                        if isinstance(item, str):
                            sig.add(item.lower())
        return sig

    @staticmethod
    def _jaccard(a: Set[str], b: Set[str]) -> float:
        if not a and not b:
            return 1.0
        inter = len(a & b)
        union = len(a | b)
        return inter / union if union > 0 else 0.0

    # ------------------------------------------------------------------ #
    # Concept candidate formation
    # ------------------------------------------------------------------ #

    def _form_concept_candidate(self, cluster: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not cluster:
            return None

        # Build recurrent symbolic signature (tokens appearing in > 50% of episodes)
        token_counts: Counter[str] = Counter()
        for ep in cluster:
            sig = self._extract_signature(ep)
            for token in sig:
                token_counts[token] += 1

        threshold = len(cluster) * 0.5
        recurrent = {token for token, count in token_counts.items() if count >= threshold}
        if not recurrent:
            return None

        # Concept label from top-3 recurrent tokens
        top_tokens = [t for t, _ in token_counts.most_common(3)]
        concept_label = "concept_" + "_".join(top_tokens)

        candidate_id = f"cand_{uuid.uuid4().hex[:8]}"
        candidate = {
            "candidate_id": candidate_id,
            "concept_label": concept_label,
            "symbolic_signature": sorted(recurrent),
            "episode_count": len(cluster),
            "status": "pending",
            "formed_at": time.time(),
            "reviewer": None,
        }
        return candidate

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _persist_candidate(self, candidate: Dict[str, Any]) -> None:
        try:
            with self._candidates_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(candidate, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _persist_concept(self, concept: Dict[str, Any]) -> None:
        try:
            with self._concepts_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(concept, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _load(self) -> None:
        for path, store in [(self._candidates_path, self._candidates), (self._concepts_path, self._concepts)]:
            if not path.exists():
                continue
            lines = path.read_text(encoding="utf-8").strip().split("\n")
            for line in lines:
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                    if "candidate_id" in obj:
                        store[obj["candidate_id"]] = obj
                    elif "concept_id" in obj:
                        store[obj["concept_id"]] = obj
                except json.JSONDecodeError:
                    continue
