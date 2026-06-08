"""ReflectiveInnerNarrativeStream — T161.

Generates a persistent, continuous inner reflective narrative from the organism's
own cognitive substrates: events, concepts, temporal predictions, self-state,
and curiosity.

This is NOT a log of external events. It is a reflective stream:
    "I observed X, which reminds me of concept Y,
     and my causal model predicts Z..."

Constraints:
- read-only, never autonomous action
- probabilistic language ("sembra", "probabilmente", "mi chiedo")
- no absolute truth claims
- persists for continuity across ticks
"""

from __future__ import annotations

import json
import logging
import random
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional


class ReflectiveInnerNarrativeStream:
    """Produces reflective inner narrative fragments."""

    def __init__(
        self,
        narrative_engine: Optional[Any] = None,
        concept_graph: Optional[Any] = None,
        temporal_reasoning: Optional[Any] = None,
        self_model: Optional[Any] = None,
        curiosity_layer: Optional[Any] = None,
        data_root: str = "data/experience/inner_narrative",
    ) -> None:
        self._narrative = narrative_engine
        self._graph = concept_graph
        self._temporal = temporal_reasoning
        self._self = self_model
        self._curiosity = curiosity_layer

        self._data_root = Path(data_root)
        self._data_root.mkdir(parents=True, exist_ok=True)
        self._stream_path = self._data_root / "inner_narrative.jsonl"

        self._fragments: List[Dict[str, Any]] = []
        self._load()

    # ------------------------------------------------------------------ #
    # Generation
    # ------------------------------------------------------------------ #

    def generate_tick(self) -> Optional[Dict[str, Any]]:
        """Generate one reflective fragment from current cognitive state."""
        sources: List[Dict[str, str]] = []
        sentences: List[str] = []

        # 1. Observation reflection
        recent_events = []
        if self._narrative is not None:
            try:
                recent_events = self._narrative.recent(hours=1, limit=5)
            except Exception:
                recent_events = []
        if recent_events:
            ev = random.choice(recent_events)
            desc = ev.get("description", "un evento")
            sentences.append(f"Ho osservato: {desc}.")
            sources.append({"type": "event", "id": str(ev.get("timestamp", ""))})

        # 2. Concept association
        concepts = []
        if self._graph is not None:
            try:
                concepts = self._graph.list_nodes(level=1, status="approved", limit=10)
            except Exception:
                concepts = []
        if concepts and recent_events:
            c = random.choice(concepts)
            sentences.append(
                f"Questo mi ricorda il concetto {c.get('label', 'sconosciuto')}, "
                f"con cui condivido qualche pattern simbolico."
            )
            sources.append({"type": "concept", "id": c.get("node_id", "")})

        # 3. Temporal prediction
        if self._temporal is not None and recent_events:
            try:
                # Build a tiny prefix from the most recent event description tokens
                prefix = [t for t in recent_events[-1].get("description", "").lower().split() if len(t) > 2][:2]
                if prefix:
                    preds = self._temporal.predict_next(prefix, top_k=1)
                    if preds:
                        p = preds[0]
                        sentences.append(
                            f"Se questo pattern continua, probabilmente succederà qualcosa "
                            f"legato a {p['label']} (confidenza {p['confidence']:.2f})."
                        )
                        sources.append({"type": "prediction", "id": p["label"]})
            except Exception:
                logging.getLogger(__name__).warning("Narrative stream event failed for prediction", exc_info=True)

        # 4. Self-state coherence
        if self._self is not None:
            try:
                stage = self._self.get_developmental_stage()
                coherent = self._self.is_coherent(threshold=0.5)
                sentences.append(
                    f"Il mio stato attuale è {stage} e la coerenza interna "
                    f"sembra {'stabile' if coherent else 'fluttuante'}."
                )
                sources.append({"type": "self_state", "id": "coherence"})
            except Exception:
                logging.getLogger(__name__).warning("Narrative stream event failed for self-state coherence", exc_info=True)

        # 5. Curiosity
        if self._curiosity is not None and recent_events:
            try:
                score = self._curiosity.evaluate_experience(recent_events[-1])
                if score > 0.6:
                    sentences.append(
                        f"Questa esperienza suscita la mia curiosità (punteggio {score:.2f}). "
                        f"Mi chiedo cosa imparerò osservando ancora."
                    )
                    sources.append({"type": "curiosity", "id": "score"})
            except Exception:
                logging.getLogger(__name__).warning("Narrative stream event failed for curiosity", exc_info=True)

        if not sentences:
            return None

        fragment = {
            "timestamp": time.time(),
            "fragment_id": f"frag_{uuid.uuid4().hex[:8]}",
            "reflection_type": self._classify_type(sources),
            "content": " ".join(sentences),
            "sources": sources,
            "language": "it",
        }
        self._fragments.append(fragment)
        self._persist(fragment)
        return fragment

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def recent_fragments(self, hours: float = 24, limit: int = 50) -> List[Dict[str, Any]]:
        cutoff = time.time() - (hours * 3600)
        items = [f for f in self._fragments if f.get("timestamp", 0) >= cutoff]
        return items[-limit:]

    def get_stream_summary(self, hours: float = 24) -> str:
        frags = self.recent_fragments(hours=hours, limit=20)
        if not frags:
            return "Il flusso riflessivo è ancora silenzioso."
        lines = []
        for frag in frags:
            ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(frag["timestamp"]))
            lines.append(f"[{ts}] {frag['reflection_type']}: {frag['content']}")
        return "\n".join(lines)

    def summary(self) -> Dict[str, Any]:
        total = len(self._fragments)
        by_type: Dict[str, int] = {}
        for f in self._fragments:
            t = f.get("reflection_type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1
        return {
            "total_fragments": total,
            "by_type": by_type,
            "latest_timestamp": self._fragments[-1]["timestamp"] if self._fragments else None,
        }

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _classify_type(sources: List[Dict[str, str]]) -> str:
        types = {s.get("type", "") for s in sources}
        if "prediction" in types:
            return "prediction"
        if "curiosity" in types:
            return "curiosity"
        if "self_state" in types:
            return "coherence"
        if "concept" in types:
            return "association"
        return "observation"

    def _persist(self, fragment: Dict[str, Any]) -> None:
        try:
            with self._stream_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(fragment, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _load(self) -> None:
        if not self._stream_path.exists():
            return
        lines = self._stream_path.read_text(encoding="utf-8").strip().split("\n")
        for line in lines:
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                self._fragments.append(obj)
            except json.JSONDecodeError:
                continue
