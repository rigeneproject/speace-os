"""CognitiveLinguisticCoherenceMonitor — T143: misura l'allineamento tra
linguaggio esterno e stato cognitivo interno di SPEACE.

Metriche:
- narrative_coherence: allineamento tra narrative engine e dialogue topic
- grounding_consistency: coerenza tra symbolic grounding e tokens usati
- drive_language_alignment: allineamento tra homeostatic drives e sentiment del dialogo
- confidence_language_alignment: allineamento tra epistemic confidence e certezza linguistica
- memory_reference_consistency: frequenza con cui il dialogo referenzia memoria nota
- self_model_consistency: coerenza tra self-model e espressione identitaria
- contradiction_rate: tasso di contraddizioni interne nel dialogue history
- repetitive_loop_density: densità di pattern ripetitivi nel dialogue history

Il monitor viene invocato ad ogni turno di dialogo e produce un report
strutturato che può essere usato per:
- metacognitive self-observation
- reflective narrative
- regulation proposals (es. "il linguaggio è disallineato dallo stato")
"""

import time
from collections import Counter, deque
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field


class CognitiveLinguisticCoherenceReport(BaseModel):
    timestamp: float = 0.0
    turn_count: int = 0
    narrative_coherence: float = 0.0
    grounding_consistency: float = 0.0
    drive_language_alignment: float = 0.0
    confidence_language_alignment: float = 0.0
    memory_reference_consistency: float = 0.0
    self_model_consistency: float = 0.0
    contradiction_rate: float = 0.0
    repetitive_loop_density: float = 0.0
    overall_coherence_score: float = 0.0
    details: Dict[str, Any] = Field(default_factory=dict)


class CognitiveLinguisticCoherenceMonitor:
    """Monitora la coerenza cognitivo-linguistica di SPEACE."""

    def __init__(self, history_window: int = 20) -> None:
        self._history_window = history_window
        self._turns: deque[Dict[str, Any]] = deque(maxlen=history_window)
        self._last_report: Optional[CognitiveLinguisticCoherenceReport] = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def evaluate_turn(
        self,
        user_message: str,
        speace_response: str,
        topic: str,
        turn_count: int,
        meta_state: Optional[Dict[str, Any]] = None,
        narrative_state: Optional[Dict[str, Any]] = None,
        relational_record: Optional[Dict[str, Any]] = None,
        grounded_concepts: Optional[List[str]] = None,
    ) -> CognitiveLinguisticCoherenceReport:
        """Valuta la coerenza del turno corrente rispetto allo stato cognitivo."""

        turn = {
            "user_message": user_message,
            "speace_response": speace_response,
            "topic": topic,
            "turn_count": turn_count,
            "meta_state": meta_state or {},
            "narrative_state": narrative_state or {},
            "relational_record": relational_record or {},
            "grounded_concepts": grounded_concepts or [],
            "timestamp": time.time(),
        }
        self._turns.append(turn)

        narrative_coherence = self._compute_narrative_coherence(turn)
        grounding_consistency = self._compute_grounding_consistency(turn)
        drive_language_alignment = self._compute_drive_language_alignment(turn)
        confidence_language_alignment = self._compute_confidence_language_alignment(turn)
        memory_reference_consistency = self._compute_memory_reference_consistency(turn)
        self_model_consistency = self._compute_self_model_consistency(turn)
        contradiction_rate = self._compute_contradiction_rate()
        repetitive_loop_density = self._compute_repetitive_loop_density()

        # Overall: weighted average
        overall = (
            narrative_coherence * 0.15
            + grounding_consistency * 0.15
            + drive_language_alignment * 0.10
            + confidence_language_alignment * 0.15
            + memory_reference_consistency * 0.10
            + self_model_consistency * 0.15
            + (1.0 - contradiction_rate) * 0.10
            + (1.0 - repetitive_loop_density) * 0.10
        )

        report = CognitiveLinguisticCoherenceReport(
            timestamp=time.time(),
            turn_count=turn_count,
            narrative_coherence=narrative_coherence,
            grounding_consistency=grounding_consistency,
            drive_language_alignment=drive_language_alignment,
            confidence_language_alignment=confidence_language_alignment,
            memory_reference_consistency=memory_reference_consistency,
            self_model_consistency=self_model_consistency,
            contradiction_rate=contradiction_rate,
            repetitive_loop_density=repetitive_loop_density,
            overall_coherence_score=round(overall, 4),
            details={
                "topics_sequence": [t["topic"] for t in self._turns],
                "grounded_concepts_last": grounded_concepts,
            },
        )
        self._last_report = report
        return report

    def get_last_report(self) -> Optional[CognitiveLinguisticCoherenceReport]:
        return self._last_report

    def summary(self) -> Dict[str, Any]:
        if self._last_report is None:
            return {"status": "no_data"}
        r = self._last_report
        return {
            "turn_count": r.turn_count,
            "overall_coherence_score": r.overall_coherence_score,
            "narrative_coherence": r.narrative_coherence,
            "grounding_consistency": r.grounding_consistency,
            "drive_language_alignment": r.drive_language_alignment,
            "confidence_language_alignment": r.confidence_language_alignment,
            "memory_reference_consistency": r.memory_reference_consistency,
            "self_model_consistency": r.self_model_consistency,
            "contradiction_rate": r.contradiction_rate,
            "repetitive_loop_density": r.repetitive_loop_density,
        }

    # ------------------------------------------------------------------ #
    # Metriche
    # ------------------------------------------------------------------ #

    def _compute_narrative_coherence(self, turn: Dict[str, Any]) -> float:
        """Allineamento tra il topic del dialogo e la narrative coherence engine."""
        narrative = turn.get("narrative_state", {})
        if not narrative:
            return 0.5
        narrative_coherence = narrative.get("coherence", 0.5)
        # Se il topic è "general" e la narrative coherence è bassa, penalizza
        topic = turn.get("topic", "general")
        if topic == "general" and narrative_coherence < 0.5:
            return max(0.0, narrative_coherence - 0.2)
        return max(0.0, min(1.0, narrative_coherence))

    def _compute_grounding_consistency(self, turn: Dict[str, Any]) -> float:
        """Coerenza tra concetti groundati e tokens nella risposta."""
        grounded = list(turn.get("grounded_concepts", []))
        response = turn.get("speace_response", "").lower()
        topic = turn.get("topic", "")
        if topic and topic not in grounded:
            grounded.append(topic)
        if not grounded:
            return 0.5
        matched = sum(1 for concept in grounded if concept.lower() in response)
        return matched / len(grounded)

    def _compute_drive_language_alignment(self, turn: Dict[str, Any]) -> float:
        """Allineamento tra drive cognitivi e sentiment/espressione del dialogo."""
        meta = turn.get("meta_state", {})
        drives = meta.get("drives", {})
        if not drives:
            return 0.5
        # Semplice: se il drive "stability" è basso ma il linguaggio è rassicurante,
        # l'allineamento è basso. Altrimenti alto.
        stability = drives.get("stability", 0.5)
        response = turn.get("speace_response", "").lower()
        reassuring = any(w in response for w in ("stabile", "stable", "bene", "ok", "coerente"))
        if stability < 0.3 and reassuring:
            return 0.2  # linguaggio rassicurante ma stato instabile = disallineato
        if stability > 0.7 and reassuring:
            return 1.0
        return 0.5 + (stability - 0.5) * 0.5

    def _compute_confidence_language_alignment(self, turn: Dict[str, Any]) -> float:
        """Allineamento tra epistemic confidence e certezza linguistica."""
        meta = turn.get("meta_state", {})
        confidence = meta.get("epistemic_confidence", {}).get("confidence_score", 0.5)
        response = turn.get("speace_response", "")
        # Marker di incertezza linguistica
        uncertainty_markers = ["forse", "non so", "non sono sicuro", "uncertain", "maybe", "i don't know"]
        has_uncertainty = any(m in response.lower() for m in uncertainty_markers)
        if has_uncertainty and confidence > 0.7:
            return 0.2  # linguaggio incerto ma confidence alta
        if not has_uncertainty and confidence < 0.3:
            return 0.3  # linguaggio certo ma confidence bassa
        if has_uncertainty and confidence < 0.3:
            return 0.9  # allineato: incerto in entrambi
        return 0.7 + (confidence - 0.5) * 0.3

    def _compute_memory_reference_consistency(self, turn: Dict[str, Any]) -> float:
        """Frequenza con cui il dialogo referenzia memoria relazionale nota."""
        relational = turn.get("relational_record", {})
        response = turn.get("speace_response", "").lower()
        if not relational:
            return 0.5
        # Se la risposta menziona il nome dell'umano o topic passati, è coerente
        name = relational.get("name", "").lower()
        known_topics = set(relational.get("topics", []))
        refs = 0
        if name and name in response:
            refs += 1
        refs += sum(1 for t in known_topics if t.lower() in response)
        total = 1 + len(known_topics)
        return min(1.0, refs / total)

    def _compute_self_model_consistency(self, turn: Dict[str, Any]) -> float:
        """Coerenza tra self-model e espressione identitaria nel dialogo."""
        response = turn.get("speace_response", "").lower()
        meta = turn.get("meta_state", {})
        identity = meta.get("identity", {})
        entity_name = identity.get("entity_name", "speace").lower()
        # Se SPEACE si identifica correttamente, coerenza alta
        if entity_name in response:
            return 0.9
        # Se la risposta parla di "io" o "i am" in inglese o italiano
        self_refs = ["io ", "sono ", "i am ", "my "]
        if any(r in response for r in self_refs):
            return 0.8
        return 0.5

    def _compute_contradiction_rate(self) -> float:
        """Tasso di contraddizioni nel dialogue history."""
        if len(self._turns) < 2:
            return 0.0
        contradictions = 0
        checks = 0
        responses = [t["speace_response"].lower() for t in self._turns]
        # Semplice: se due risposte consecutive contengono negazioni opposte
        negation_pairs = [
            ("bene", "male"),
            ("stable", "unstable"),
            ("stabile", "instabile"),
            ("ok", "not ok"),
            ("pronto", "non pronto"),
            ("attivo", "inattivo"),
            ("sì", "no"),
        ]
        for i in range(1, len(responses)):
            prev = responses[i - 1]
            curr = responses[i]
            for a, b in negation_pairs:
                if (a in prev and b in curr) or (b in prev and a in curr):
                    contradictions += 1
            checks += 1
        return contradictions / checks if checks > 0 else 0.0

    def _compute_repetitive_loop_density(self) -> float:
        """Densità di pattern ripetitivi nel dialogue history."""
        if len(self._turns) < 4:
            return 0.0
        responses = [t["speace_response"] for t in self._turns]
        # Conta quante volte la stessa risposta esatta appare
        counter = Counter(responses)
        most_common = counter.most_common(1)[0][1]
        if most_common <= 1:
            return 0.0
        # Se l'ultima risposta è uguale a una precedente, loop rilevato
        last = responses[-1]
        loop_count = sum(1 for r in responses[:-1] if r == last)
        return min(1.0, loop_count / (len(responses) - 1))
