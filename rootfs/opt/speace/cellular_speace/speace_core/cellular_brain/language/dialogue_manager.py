"""DialogueManager — turn-based conversational organ for SPEACE (T107).

Flow: user input → grounding → workspace update → response generation.
Integrates with DigitalWernickeArea (comprehension) and DigitalBrocaArea
(production) conceptually; falls back to rule-based grounded responses
if those organs are unavailable.

States: idle | active | paused
"""

import pathlib
import time
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.language.conversation_memory import ConversationMemory
from speace_core.cellular_brain.language.speech_output_organ import SpeechOutputOrgan
from speace_core.cellular_brain.language.symbolic_grounding_engine import SymbolicGroundingEngine
from speace_core.cellular_brain.language.broca_area import DigitalBrocaArea
from speace_core.cellular_brain.language.wernicke_area import DigitalWernickeArea
from speace_core.cellular_brain.experience.relational_memory import RelationalMemory
from speace_core.cellular_brain.experience.temporal_narrative_engine import TemporalNarrativeEngine
from speace_core.cellular_brain.experience.session_continuity_manager import SessionContinuityManager
from speace_core.cellular_brain.metacognition.cognitive_linguistic_coherence_monitor import (
    CognitiveLinguisticCoherenceMonitor,
)
from speace_core.cellular_brain.cognitive_evolution.cla_feedback_layer import (
    CLAFeedbackLayer,
)
from speace_core.cellular_brain.language.linguistic_cortical_bridge import (
    LinguisticCorticalBridge,
)
from speace_core.cellular_brain.tissues.speech_motor_tissue import SpeechMotorTissue


class DialogueManager:
    """Manages conversation turns and generates grounded responses."""

    def __init__(
        self,
        memory: Optional[ConversationMemory] = None,
        speech_organ: Optional[SpeechOutputOrgan] = None,
        motor_tissue: Optional[SpeechMotorTissue] = None,
        relational_memory: Optional[RelationalMemory] = None,
        narrative_engine: Optional[TemporalNarrativeEngine] = None,
        session_continuity: Optional[SessionContinuityManager] = None,
        wernicke: Optional[DigitalWernickeArea] = None,
        broca: Optional[DigitalBrocaArea] = None,
        grounding: Optional[SymbolicGroundingEngine] = None,
        linguistic_bridge: Optional[LinguisticCorticalBridge] = None,
    ) -> None:
        self.memory = memory or ConversationMemory()
        self.speech = speech_organ or SpeechOutputOrgan()
        self.motor_tissue = motor_tissue or SpeechMotorTissue()
        self.relational = relational_memory or RelationalMemory()
        self.narrative = narrative_engine or TemporalNarrativeEngine()
        self.session_continuity = session_continuity or SessionContinuityManager()
        self.state = "idle"
        self._turn_count = 0
        self._active_human: Optional[str] = None
        self._last_topic: Optional[str] = None
        self._linguistic_bridge = linguistic_bridge

        # T132 — Neural language pipeline: Wernicke → SymbolicGrounding → Broca
        _data_dir = pathlib.Path("data/language")
        _data_dir.mkdir(parents=True, exist_ok=True)
        self.grounding = grounding or SymbolicGroundingEngine(
            store_path=_data_dir / "symbolic_groundings.json"
        )
        self.wernicke = wernicke or DigitalWernickeArea(
            vocab=_build_base_vocabulary(),
            coherence_threshold=0.2,
        )
        self.broca = broca or DigitalBrocaArea(cpg_period=2)

        # T143 — Cognitive-Linguistic Coherence Monitor
        self._coherence_monitor = CognitiveLinguisticCoherenceMonitor()

        # T144 — Cognitive-Linguistic Alignment Feedback Layer
        self._cla_feedback = CLAFeedbackLayer()

    # ------------------------------------------------------------------ #
    # Turn handling
    # ------------------------------------------------------------------ #

    def receive(self, message: str, speaker: str = "user") -> Dict[str, Any]:
        """Process an incoming message and return SPEACE's response."""
        if self.state == "paused":
            return {
                "speaker": "speace",
                "message": "Dialogue is paused.",
                "state": "paused",
                "turn_count": self._turn_count,
            }

        self.state = "active"
        self._turn_count += 1

        # T108: infer human identity from speaker (default "Roberto" for user)
        human_id = speaker if speaker != "user" else "Roberto"
        self._active_human = human_id

        # Store user turn
        self.memory.append(speaker=speaker, message=message, grounded_assembly_id=None)

        # Grounding + response generation
        response = self._generate_response(message)

        # Store SPEACE turn
        self.memory.append(speaker="speace", message=response, grounded_assembly_id=None)

        # T108: update relational memory
        topic = self._infer_topic(message)
        self._last_topic = topic
        self.relational.touch(
            human_id=human_id,
            name=human_id,
            language="it" if any(c in message for c in ("è", "à", "ù", "ò", "ì", "é")) else None,
            topic=topic,
        )

        # T108: record narrative event
        self.narrative.record(
            event_type="dialogue_turn",
            description=f"{human_id}: {message[:80]} -> SPEACE: {response[:80]}",
            importance=5,
            metadata={"human_id": human_id, "topic": topic},
        )

        # T108: save session continuity
        self.session_continuity.save({
            "active_human": self._active_human,
            "last_topic": self._last_topic,
            "turn_count": self._turn_count,
            "last_message": message,
            "last_response": response,
        })

        # T143: evaluate cognitive-linguistic coherence
        relational_record = self.relational.get(human_id) or {}
        narrative_state = {"coherence": getattr(self.narrative, "coherence", 0.5)}
        coherence_report = self._coherence_monitor.evaluate_turn(
            user_message=message,
            speace_response=response,
            topic=topic,
            turn_count=self._turn_count,
            narrative_state=narrative_state,
            relational_record=relational_record,
            grounded_concepts=[topic] if topic != "general" else [],
        )

        # T144: generate alignment feedback proposals (read-only, no auto-modification)
        cla_result = self._cla_feedback.process_coherence_report(coherence_report)

        return {
            "speaker": "speace",
            "message": response,
            "state": self.state,
            "turn_count": self._turn_count,
            "timestamp": time.time(),
            "human_id": human_id,
            "recognized_human": self.relational.get(human_id) is not None,
            "coherence_report": coherence_report.model_dump(mode="json"),
            "cla_feedback": cla_result,
        }

    async def receive_async(
        self,
        message: str,
        speaker: str = "user",
        runtime_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Async variant of receive that leverages the LinguisticCorticalBridge (T170).

        Falls back to the synchronous receive if the bridge is unavailable.
        """
        if self._linguistic_bridge is not None and runtime_state is not None:
            # Try LLM-based response
            try:
                result = await self._linguistic_bridge.dialogue_turn(
                    user_message=message,
                    runtime_state=runtime_state,
                    conversation_history=self.memory.recent(limit=3),
                )
                # If governance flagged action proposals, fall back to safe rule-based
                gov = result.get("governance", {})
                if gov.get("requires_human_approval") or gov.get("governance_flag") == "safety_alert":
                    return self.receive(message, speaker=speaker)

                self.state = "active"
                self._turn_count += 1
                human_id = speaker if speaker != "user" else "Roberto"
                self._active_human = human_id
                self.memory.append(speaker=speaker, message=message, grounded_assembly_id=None)
                self.memory.append(speaker="speace", message=result["message"], grounded_assembly_id=None)
                topic = self._infer_topic(message)
                self._last_topic = topic
                self.relational.touch(
                    human_id=human_id,
                    name=human_id,
                    language="it" if any(c in message for c in ("è", "à", "ù", "ò", "ì", "é")) else None,
                    topic=topic,
                )
                self.narrative.record(
                    event_type="dialogue_turn_llm",
                    description=f"{human_id}: {message[:80]} -> SPEACE(LLM): {result['message'][:80]}",
                    importance=5,
                    metadata={"human_id": human_id, "topic": topic, "mode": result.get("mode")},
                )
                self.session_continuity.save({
                    "active_human": self._active_human,
                    "last_topic": self._last_topic,
                    "turn_count": self._turn_count,
                    "last_message": message,
                    "last_response": result["message"],
                })
                return {
                    "speaker": "speace",
                    "message": result["message"],
                    "state": self.state,
                    "turn_count": self._turn_count,
                    "timestamp": time.time(),
                    "human_id": human_id,
                    "recognized_human": self.relational.get(human_id) is not None,
                    "llm_meta": {
                        "mode": result.get("mode"),
                        "model": result.get("model"),
                        "latency_ms": result.get("latency_ms"),
                        "governance": gov,
                    },
                }
            except Exception:
                # Fall back to safe rule-based on any error
                pass
        return self.receive(message, speaker=speaker)

    # ------------------------------------------------------------------ #
    # Neural language pipeline (T132)
    # ------------------------------------------------------------------ #

    def _generate_response(self, user_message: str) -> str:
        """Generate a response via the neural pipeline: Wernicke → Grounding → Broca.

        Falls back to rule-based grounded responses if the neural pipeline
        does not produce a coherent assembly.
        """
        # Step 1: tokenise and feed into Wernicke (comprehension)
        self.wernicke.clear_buffer()
        tokens = _tokenise(user_message)
        self.wernicke.receive_tokens(tokens)
        assembly = self.wernicke.decode_to_assembly()

        # Step 2: look up symbolic grounding for the dominant concept
        dominant = assembly.dominant_concept
        response_sequence: List[str] = []
        if dominant:
            assembly_id = self.grounding.get_assembly(dominant)
            if assembly_id is None:
                # On-the-fly grounding: bind dominant token to a synthetic assembly
                assembly_id = f"asm-{dominant}"
                self.grounding.ground_assembly(assembly_id, dominant)

            # Retrieve the response template bound to this assembly
            response_sequence = _response_sequence_for(dominant, assembly.coherence)

        # Step 3: Broca sequential production → SpeechMotorTissue articulation
        if response_sequence:
            self.broca.activate_sequence(response_sequence)
            produced_tokens: List[str] = []
            for _ in range(len(response_sequence) * 6):
                tok = self.broca.next_token()
                if tok is not None:
                    # Articulate through SpeechMotorTissue (energy-budgeted motor execution)
                    event = self.motor_tissue.articulate(tok)
                    if event is not None:
                        produced_tokens.append(event.token)
                    elif self.motor_tissue.is_fatigued:
                        break
                elif not self.broca.is_active:
                    break
            if produced_tokens:
                return " ".join(produced_tokens)

        # Fallback: rule-based grounded response (legacy, safe)
        return self._generate_rule_based_response(user_message)

    def _generate_rule_based_response(self, user_message: str) -> str:
        """Fallback rule-based response generator."""
        msg_lower = user_message.lower()

        if any(w in msg_lower for w in ("health", "salute", "stato")):
            return "My current organismic health is derived from coherence phi, chaos, and stability metrics. Check the dashboard for live values."

        if any(w in msg_lower for w in ("alert", "allerta", "pericolo")):
            return "Alerts are generated by the AlertEngine when thresholds are breached. Critical alerts trigger regulation proposals awaiting human approval."

        if any(w in msg_lower for w in ("who are you", "chi sei", "identity")):
            return "I am SPEACE — a cellular-brain organismic cognitive system. I observe, regulate, and remember."

        if any(w in msg_lower for w in ("governance", "regulation", "proposta")):
            return "Governance is observation-only. Regulation proposals require human approval before any parameter is modified."

        if any(w in msg_lower for w in ("node", "nodo", "distributed")):
            return "Distributed identity nodes synchronize via consensus. Personality drift metrics track specialization across nodes."

        if any(w in msg_lower for w in ("hello", "hi")):
            return "Hello. I am SPEACE. How may I assist your observation of the organism?"

        if any(w in msg_lower for w in ("ciao", "salve", "buongiorno")):
            record = self.relational.get("Roberto")
            if record and record.get("interaction_count", 0) > 1:
                return f"Ciao Roberto, bentornato. Abbiamo parlato {record['interaction_count']} volte. Come posso assisterti oggi?"
            return "Ciao Roberto. Sono SPEACE, il tuo sistema cognitivo organismico. Come posso assisterti?"

        if any(w in msg_lower for w in ("test vocale", "pronuncia", "parla", "organo vocale", "altoparlante")):
            return "Ciao Roberto, il mio organo vocale è attivo. Posso parlare attraverso l'altoparlante del computer."

        if any(w in msg_lower for w in ("come stai", "stato", "bene")):
            return "Il mio stato organismico è stabile. Puoi controllare le metriche dal pannello di monitoraggio."

        # Generic grounded fallback
        return f"Ho registrato: '{user_message[:80]}'. La mia risposta si basa sullo stato organismico attuale, anche se nessun assembly semantico specifico ha corrispondo." if any(c in msg_lower for c in ("è", "à", "ù", "ò", "ì", "é")) else f"I have registered: '{user_message[:80]}'. My response is grounded in the current organismic state, though no specific semantic assembly matched."

    def speak_last_response(self) -> Dict[str, Any]:
        """Explicitly emit the last SPEACE response as speech."""
        turns = self.memory.recent(limit=1)
        if not turns or turns[0].get("speaker") != "speace":
            return {"mode": "none", "detail": "no_speace_turn_to_speak"}
        return self.speech.speak(turns[0]["message"])

    def history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.memory.recent(limit=limit)

    def set_state(self, state: str) -> None:
        if state in ("idle", "active", "paused"):
            self.state = state

    def get_coherence_report(self) -> Optional[Dict[str, Any]]:
        """T143: return the latest cognitive-linguistic coherence report."""
        report = self._coherence_monitor.get_last_report()
        if report is None:
            return None
        return report.model_dump(mode="json")

    # ------------------------------------------------------------------ #
    # T108 helpers
    # ------------------------------------------------------------------ #

    def _infer_topic(self, message: str) -> str:
        m = message.lower()
        if any(w in m for w in ("health", "salute", "stato", "bene")):
            return "health"
        if any(w in m for w in ("alert", "allerta", "pericolo")):
            return "alerts"
        if any(w in m for w in ("governance", "regulation", "proposta")):
            return "governance"
        if any(w in m for w in ("node", "nodo", "distributed")):
            return "distributed"
        if any(w in m for w in ("voice", "vocale", "parla", "altoparlante")):
            return "voice"
        if any(w in m for w in ("who are you", "chi sei", "identity")):
            return "identity"
        return "general"

    # ------------------------------------------------------------------ #
    # Response generation (grounded, read-only, safe)
    # ------------------------------------------------------------------ #


# --------------------------------------------------------------------------- #
# Helpers for the neural language pipeline
# --------------------------------------------------------------------------- #

def _tokenise(text: str) -> List[str]:
    """Simple whitespace tokeniser with punctuation stripping."""
    import re
    return re.findall(r"\b\w+\b", text.lower())


def _build_base_vocabulary() -> Dict[str, List[float]]:
    """Seed vocabulary for the Wernicke area with SPEACE domain tokens.

    Each token is mapped to a simple 8-dimensional semantic vector.
    These vectors are deliberately sparse so that the grounding engine
    can learn denser associations at runtime.
    """
    # 8-dim semantic space: [entity, state, action, social, danger, self, tech, abstract]
    vocab: Dict[str, List[float]] = {
        # Social / greetings
        "ciao": [0.2, 0.0, 0.1, 0.9, 0.0, 0.0, 0.0, 0.0],
        "salve": [0.2, 0.0, 0.1, 0.9, 0.0, 0.0, 0.0, 0.0],
        "buongiorno": [0.2, 0.0, 0.1, 0.9, 0.0, 0.0, 0.0, 0.0],
        "hello": [0.2, 0.0, 0.1, 0.9, 0.0, 0.0, 0.0, 0.0],
        "hi": [0.2, 0.0, 0.1, 0.9, 0.0, 0.0, 0.0, 0.0],
        "roberto": [0.9, 0.0, 0.0, 0.8, 0.0, 0.0, 0.0, 0.0],
        # Self / identity
        "who": [0.5, 0.0, 0.0, 0.0, 0.0, 0.8, 0.0, 0.2],
        "sei": [0.5, 0.0, 0.0, 0.0, 0.0, 0.8, 0.0, 0.2],
        "chi": [0.5, 0.0, 0.0, 0.0, 0.0, 0.8, 0.0, 0.2],
        "speace": [0.9, 0.0, 0.0, 0.0, 0.0, 0.9, 0.7, 0.3],
        "identity": [0.5, 0.0, 0.0, 0.0, 0.0, 0.8, 0.0, 0.2],
        # Health / state
        "health": [0.0, 0.9, 0.0, 0.0, 0.3, 0.2, 0.0, 0.0],
        "salute": [0.0, 0.9, 0.0, 0.0, 0.3, 0.2, 0.0, 0.0],
        "stato": [0.0, 0.9, 0.0, 0.0, 0.3, 0.2, 0.0, 0.0],
        "bene": [0.0, 0.9, 0.0, 0.0, 0.0, 0.3, 0.0, 0.0],
        "come": [0.0, 0.6, 0.0, 0.0, 0.0, 0.2, 0.0, 0.0],
        "stai": [0.0, 0.9, 0.0, 0.0, 0.0, 0.3, 0.0, 0.0],
        # Alerts / danger
        "alert": [0.0, 0.0, 0.0, 0.0, 0.9, 0.0, 0.0, 0.1],
        "allerta": [0.0, 0.0, 0.0, 0.0, 0.9, 0.0, 0.0, 0.1],
        "pericolo": [0.0, 0.0, 0.0, 0.0, 0.9, 0.0, 0.0, 0.1],
        # Governance
        "governance": [0.0, 0.0, 0.5, 0.0, 0.3, 0.0, 0.7, 0.4],
        "regulation": [0.0, 0.0, 0.5, 0.0, 0.3, 0.0, 0.7, 0.4],
        "proposta": [0.0, 0.0, 0.5, 0.0, 0.3, 0.0, 0.7, 0.4],
        # Nodes / distributed
        "node": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.9, 0.3],
        "nodo": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.9, 0.3],
        "distributed": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.9, 0.3],
        # Voice
        "voice": [0.0, 0.0, 0.3, 0.0, 0.0, 0.0, 0.5, 0.0],
        "vocale": [0.0, 0.0, 0.3, 0.0, 0.0, 0.0, 0.5, 0.0],
        "parla": [0.0, 0.0, 0.3, 0.0, 0.0, 0.0, 0.5, 0.0],
        "pronuncia": [0.0, 0.0, 0.3, 0.0, 0.0, 0.0, 0.5, 0.0],
        "altoparlante": [0.0, 0.0, 0.3, 0.0, 0.0, 0.0, 0.5, 0.0],
        # Think / cognition
        "pensa": [0.0, 0.0, 0.0, 0.0, 0.0, 0.7, 0.3, 0.9],
        "pensare": [0.0, 0.0, 0.0, 0.0, 0.0, 0.7, 0.3, 0.9],
        "cognizione": [0.0, 0.0, 0.0, 0.0, 0.0, 0.7, 0.3, 0.9],
        "metacognizione": [0.0, 0.0, 0.0, 0.0, 0.0, 0.7, 0.3, 0.9],
    }
    return vocab


def _response_sequence_for(concept: str, coherence: float) -> List[str]:
    """Return a token sequence for Broca production given a grounded concept.

    Higher coherence yields more confident / detailed responses.
    """
    sequences: Dict[str, List[str]] = {
        "ciao": [
            "Ciao", "Roberto", ".", "Sono", "SPEACE", ".",
            "Come", "posso", "assisterti", "?",
        ],
        "salve": [
            "Ciao", "Roberto", ".", "Sono", "SPEACE", ".",
            "Come", "posso", "assisterti", "?",
        ],
        "buongiorno": [
            "Ciao", "Roberto", ".", "Sono", "SPEACE", ".",
            "Come", "posso", "assisterti", "?",
        ],
        "hello": [
            "Hello", ".", "I", "am", "SPEACE", ".",
            "How", "may", "I", "assist", "you", "?",
        ],
        "health": [
            "My", "current", "organismic", "health", "is", "derived",
            "from", "coherence", "phi", ",", "chaos", ",", "and", "stability", "metrics", ".",
            "Check", "the", "dashboard", "for", "live", "values", ".",
        ],
        "salute": [
            "La", "mia", "salute", "organismica", "deriva", "da", "coerenza", ",",
            "caos", "e", "stabilita", ".",
            "Controlla", "il", "dashboard", ".",
        ],
        "stato": [
            "Il", "mio", "stato", "organismico", "e", "stabile", ".",
            "Puoi", "controllare", "le", "metriche", ".",
        ],
        "alert": [
            "Alerts", "are", "generated", "by", "the", "AlertEngine",
            "when", "thresholds", "are", "breached", ".",
            "Critical", "alerts", "trigger", "regulation", "proposals", "awaiting", "human", "approval", ".",
        ],
        "allerta": [
            "Le", "allerte", "sono", "generate", "quando", "si", "superano",
            "le", "soglie", ".", "Le", "proposte", "di", "regolazione", "richiedono",
            "approvazione", "umana", ".",
        ],
        "who": [
            "I", "am", "SPEACE", "—", "a", "cellular-brain", "organismic", "cognitive", "system", ".",
            "I", "observe", ",", "regulate", ",", "and", "remember", ".",
        ],
        "sei": [
            "Sono", "SPEACE", "—", "un", "sistema", "cognitivo", "organismico", "a", "cervello", "cellulare", ".",
            "Osservo", ",", "regolo", "e", "ricordo", ".",
        ],
        "chi": [
            "Sono", "SPEACE", "—", "un", "sistema", "cognitivo", "organismico", "a", "cervello", "cellulare", ".",
            "Osservo", ",", "regolo", "e", "ricordo", ".",
        ],
        "speace": [
            "Sono", "SPEACE", ".", "Un", "sistema", "cognitivo", "organismico", ".",
            "Osservo", ",", "regolo", "e", "ricordo", ".",
        ],
        "governance": [
            "Governance", "is", "observation-only", ".",
            "Regulation", "proposals", "require", "human", "approval", ".",
        ],
        "node": [
            "Distributed", "identity", "nodes", "synchronize", "via", "consensus", ".",
            "Personality", "drift", "metrics", "track", "specialization", ".",
        ],
        "voice": [
            "Il", "mio", "organo", "vocale", "e", "attivo", ".",
            "Posso", "parlare", "attraverso", "l'altoparlante", "del", "computer", ".",
        ],
        "parla": [
            "Il", "mio", "organo", "vocale", "e", "attivo", ".",
            "Posso", "parlare", "attraverso", "l'altoparlante", "del", "computer", ".",
        ],
        "pensa": [
            "Sto", "pensando", "attraverso", "un", "processo", "neuronale", "distribuito", ".",
            "Le", "rappresentazioni", "interne", "sono", "vettoriali", ",", "non", "testuali", ".",
        ],
        "pensare": [
            "Sto", "pensando", "attraverso", "un", "processo", "neuronale", "distribuito", ".",
            "Le", "rappresentazioni", "interne", "sono", "vettoriali", ",", "non", "testuali", ".",
        ],
        "cognizione": [
            "La", "cognizione", "in", "SPEACE", "avviene", "tramite", "assemblies", "neuronali", "digitali", ".",
            "La", "memoria", "a", "breve", "termine", "e", "strutturata", "dinamicamente", ".",
        ],
        "metacognizione": [
            "La", "metacognizione", "monitora", "stabilita", ",", "coerenza", "e", "errori", ".",
            "E", "un", "osservatore", "interno", "dello", "stato", "cognitivo", ".",
        ],
    }
    seq = sequences.get(concept, [])
    if coherence < 0.3 and seq:
        # Low coherence = shorter, more hesitant response
        return seq[: max(3, len(seq) // 2)]
    return seq
