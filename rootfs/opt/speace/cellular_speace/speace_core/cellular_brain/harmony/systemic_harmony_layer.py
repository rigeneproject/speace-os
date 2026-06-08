"""SystemicHarmonyLayer — T162.

Orchestrates T159 (Hierarchical Conceptual Abstraction) and T161 (Reflective Inner
Narrative) into the organism's life cycle, computing cross-layer harmony metrics.

Responsibilities:
    1. Drive reflective narrative generation on each tick.
    2. Drive concept abstraction ingestion on each tick.
    3. Compute harmony metrics from all cognitive substrates.
    4. Persist reports and expose read-only state.

Constraints:
    - read-only observables, never autonomous action
    - graceful degradation (missing substrate → neutral score 0.5)
    - human approval gate preserved for T159 candidates
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from speace_core.cellular_brain.cognition.hierarchical_concept_abstraction_layer import (
    HierarchicalConceptAbstractionLayer,
)
from speace_core.cellular_brain.experience.reflective_inner_narrative_stream import (
    ReflectiveInnerNarrativeStream,
)


class SystemicHarmonyLayer:
    """Integrates conceptual abstraction and reflective narrative into the runtime."""

    def __init__(
        self,
        narrative_engine: Optional[Any] = None,
        episodic_layer: Optional[Any] = None,
        causal_model: Optional[Any] = None,
        concept_graph: Optional[Any] = None,
        temporal_reasoning: Optional[Any] = None,
        self_model: Optional[Any] = None,
        curiosity_layer: Optional[Any] = None,
        data_root: str = "data/harmony",
    ) -> None:
        self._narrative_engine = narrative_engine
        self._episodic_layer = episodic_layer
        self._causal_model = causal_model
        self._concept_graph = concept_graph
        self._temporal_reasoning = temporal_reasoning
        self._self_model = self_model
        self._curiosity_layer = curiosity_layer

        self._data_root = Path(data_root)
        self._data_root.mkdir(parents=True, exist_ok=True)
        self._reports_path = self._data_root / "reports.jsonl"

        self._reports: List[Dict[str, Any]] = []
        self._load()

        # Own T161 and T159 instances if not provided externally
        self._narrative_stream: Optional[ReflectiveInnerNarrativeStream] = None
        self._concept_abstraction: Optional[HierarchicalConceptAbstractionLayer] = None

        if self._narrative_engine is not None:
            self._narrative_stream = ReflectiveInnerNarrativeStream(
                narrative_engine=self._narrative_engine,
                concept_graph=self._concept_graph,
                temporal_reasoning=self._temporal_reasoning,
                self_model=self._self_model,
                curiosity_layer=self._curiosity_layer,
                data_root=str(self._data_root / "inner_narrative"),
            )

        if self._concept_graph is not None:
            self._concept_abstraction = HierarchicalConceptAbstractionLayer(
                concept_graph=self._concept_graph,
                data_root=str(self._data_root / "concept_abstraction"),
            )

    # ------------------------------------------------------------------ #
    # Tick
    # ------------------------------------------------------------------ #

    def tick(self) -> Optional[Dict[str, Any]]:
        """Generate reflection, ingest concepts, compute harmony report."""
        # 1. Reflective narrative
        fragment: Optional[Dict[str, Any]] = None
        if self._narrative_stream is not None:
            try:
                fragment = self._narrative_stream.generate_tick()
            except Exception:
                fragment = None

        # 2. Concept abstraction ingestion
        candidates: List[Dict[str, Any]] = []
        if self._concept_abstraction is not None:
            try:
                candidates = self._concept_abstraction.ingest(
                    self._episodic_layer,
                    self._causal_model,
                )
            except Exception:
                candidates = []

        # 3. Compute harmony metrics
        report = self._compute_harmony_report(fragment, candidates)
        self._reports.append(report)
        self._persist(report)
        return report

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def latest_report(self) -> Optional[Dict[str, Any]]:
        return self._reports[-1] if self._reports else None

    def to_state_dict(self) -> Dict[str, Any]:
        report = self.latest_report()
        return {
            "harmony_enabled": True,
            "latest_report": report,
            "total_reports": len(self._reports),
            "narrative_stream_active": self._narrative_stream is not None,
            "concept_abstraction_active": self._concept_abstraction is not None,
        }

    def summary(self) -> Dict[str, Any]:
        if not self._reports:
            return {"total_reports": 0, "average_aggregate_harmony": None}
        scores = [r.get("aggregate_harmony", 0.5) for r in self._reports]
        return {
            "total_reports": len(self._reports),
            "average_aggregate_harmony": round(sum(scores) / len(scores), 4),
            "latest_aggregate_harmony": round(scores[-1], 4),
        }

    # ------------------------------------------------------------------ #
    # Harmony computation
    # ------------------------------------------------------------------ #

    def _compute_harmony_report(
        self,
        fragment: Optional[Dict[str, Any]],
        candidates: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        metrics: Dict[str, float] = {}

        metrics["narrative_concept_alignment"] = self._metric_narrative_concept_alignment()
        metrics["prediction_narrative_consistency"] = self._metric_prediction_narrative_consistency()
        metrics["self_state_stability"] = self._metric_self_state_stability()
        metrics["curiosity_concept_coverage"] = self._metric_curiosity_concept_coverage()
        metrics["temporal_chain_depth"] = self._metric_temporal_chain_depth()

        # Weighted aggregate
        weights = {
            "narrative_concept_alignment": 0.25,
            "prediction_narrative_consistency": 0.20,
            "self_state_stability": 0.20,
            "curiosity_concept_coverage": 0.15,
            "temporal_chain_depth": 0.20,
        }
        aggregate = sum(metrics[k] * weights[k] for k in weights)

        return {
            "timestamp": time.time(),
            "aggregate_harmony": round(aggregate, 4),
            "metrics": metrics,
            "fragment_generated": fragment is not None,
            "new_candidates_count": len(candidates),
        }

    def _metric_narrative_concept_alignment(self) -> float:
        """Jaccard overlap between recent narrative tokens and active concept signatures."""
        if self._narrative_stream is None or self._concept_graph is None:
            return 0.5
        try:
            frags = self._narrative_stream.recent_fragments(hours=1, limit=20)
            if not frags:
                return 0.5
            narrative_tokens: Set[str] = set()
            for frag in frags:
                content = frag.get("content", "")
                for token in content.lower().split():
                    token = token.strip(".,;:!?")
                    if len(token) > 2:
                        narrative_tokens.add(token)

            nodes = self._concept_graph.list_nodes(status="approved", limit=100)
            if not nodes:
                return 0.5
            concept_tokens: Set[str] = set()
            for node in nodes:
                for token in node.get("symbolic_signature", []):
                    concept_tokens.add(token.lower())

            inter = len(narrative_tokens & concept_tokens)
            union = len(narrative_tokens | concept_tokens)
            return round(inter / union, 4) if union > 0 else 0.0
        except Exception:
            return 0.5

    def _metric_prediction_narrative_consistency(self) -> float:
        """Fraction of recent predictions appearing in recent narrative."""
        if self._temporal_reasoning is None or self._narrative_stream is None:
            return 0.5
        try:
            frags = self._narrative_stream.recent_fragments(hours=1, limit=10)
            if not frags:
                return 0.5
            narrative_text = " ".join(f.get("content", "") for f in frags).lower()

            # Sample predictions from known sequences
            seqs = self._temporal_reasoning.list_sequences(limit=20)
            if not seqs:
                return 0.5
            pred_labels: Set[str] = set()
            for seq in seqs:
                for event in seq.get("events", []):
                    pred_labels.add(event.get("label", "").lower())

            if not pred_labels:
                return 0.5
            matched = sum(1 for label in pred_labels if label in narrative_text)
            return round(matched / len(pred_labels), 4)
        except Exception:
            return 0.5

    def _metric_self_state_stability(self) -> float:
        """Inverse variance of latest self-model coherence (high = stable)."""
        if self._self_model is None:
            return 0.5
        try:
            history = getattr(self._self_model, "coherence_history", [])
            if len(history) < 2:
                return 0.5
            # Use last 10 values
            recent = history[-10:]
            mean = sum(recent) / len(recent)
            variance = sum((x - mean) ** 2 for x in recent) / len(recent)
            # Map variance ∈ [0, ∞) to stability ∈ [0, 1] via exponential decay
            stability = max(0.0, min(1.0, 1.0 - variance))
            return round(stability, 4)
        except Exception:
            return 0.5

    def _metric_curiosity_concept_coverage(self) -> float:
        """Fraction of active concepts that received curiosity attention."""
        if self._curiosity_layer is None or self._concept_graph is None:
            return 0.5
        try:
            nodes = self._concept_graph.list_nodes(status="approved", limit=100)
            if not nodes:
                return 0.5
            # We cannot directly map curiosity scores to concepts without events.
            # Proxy: if curiosity layer has top_interesting items, check overlap.
            top = getattr(self._curiosity_layer, "get_top_interesting", lambda n: [])()
            if not top:
                return 0.5
            top_labels = {t.get("label", "").lower() for t in top}
            concept_labels = {n.get("label", "").lower() for n in nodes}
            matched = len(top_labels & concept_labels)
            return round(matched / len(concept_labels), 4) if concept_labels else 0.5
        except Exception:
            return 0.5

    def _metric_temporal_chain_depth(self) -> float:
        """Normalized max sequence depth from temporal reasoning."""
        if self._temporal_reasoning is None:
            return 0.5
        try:
            seqs = self._temporal_reasoning.list_sequences(limit=50)
            if not seqs:
                return 0.5
            max_len = max(s.get("length", 2) for s in seqs)
            # Normalize: assume 10 is a rich chain
            return round(min(1.0, max_len / 10.0), 4)
        except Exception:
            return 0.5

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _persist(self, report: Dict[str, Any]) -> None:
        try:
            with self._reports_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(report, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _load(self) -> None:
        if not self._reports_path.exists():
            return
        try:
            lines = self._reports_path.read_text(encoding="utf-8").strip().split("\n")
        except OSError:
            return
        for line in lines:
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                self._reports.append(obj)
            except json.JSONDecodeError:
                continue
