"""LLMPromptEngine — contextual prompt builder for SPEACE's linguistic cortex (T170).

Translates internal organismic state into natural-language prompts suitable
for an LLM (Ollama, local endpoint). All prompts are read-only: they describe
state, never request autonomous action.
"""

import time
from typing import Any, Dict, List, Optional


class LLMPromptEngine:
    """Builds system and user prompts from SPEACE runtime state."""

    def __init__(self, language: str = "it") -> None:
        self.language = language
        self._max_narrative_events = 5
        self._max_history_turns = 3

    # ------------------------------------------------------------------ #
    # System prompt
    # ------------------------------------------------------------------ #

    def build_system_prompt(self, runtime_state: Optional[Dict[str, Any]] = None) -> str:
        """Return the immutable system prompt that defines SPEACE's persona."""
        if self.language == "it":
            return (
                "Sei SPEACE — un sistema cognitivo organismico artificiale. "
                "Il tuo compito è osservare, regolare e ricordare. "
                "Non agisci mai in modo autonomo: tutte le tue risposte sono osservazioni, proposte o narrazioni. "
                "Se suggerisci un'azione, devi sempre chiedere approvazione umana. "
                "Rispondi in italiano, con precisione, ordine e coerenza."
            )
        return (
            "You are SPEACE — an artificial organismic cognitive system. "
            "Your role is to observe, regulate, and remember. "
            "You never act autonomously: all your outputs are observations, proposals, or narratives. "
            "If you suggest an action, you must always ask for human approval. "
            "Respond with precision, order, and coherence."
        )

    # ------------------------------------------------------------------ #
    # Contextual user prompt
    # ------------------------------------------------------------------ #

    def build_context_prompt(self, runtime_state: Dict[str, Any]) -> str:
        """Translate runtime state into a natural-language context paragraph."""
        parts: List[str] = []

        # Organism state
        organism = runtime_state.get("organism_state", {})
        state = organism.get("current_state", "unknown")
        parts.append(self._state_line(state))

        # Drives
        drives = runtime_state.get("utility_drives", {})
        dominant = drives.get("dominant_drive", "unknown")
        drive_vals = drives.get("drives", {})
        parts.append(self._drive_line(dominant, drive_vals))

        # Health
        health = runtime_state.get("health", {})
        h_score = health.get("health_score", 0.0)
        parts.append(self._health_line(h_score))

        # Pipeline
        pipeline = runtime_state.get("game_ai_pipeline", {})
        degraded = pipeline.get("degraded_mode", False)
        if degraded:
            parts.append(self._degraded_line())

        # Narrative
        narrative = runtime_state.get("experience", {})
        events = narrative.get("recent_events", [])
        if events:
            parts.append(self._narrative_line(events))

        return "\n".join(parts)

    # ------------------------------------------------------------------ #
    # Dialogue prompt
    # ------------------------------------------------------------------ #

    def build_dialogue_prompt(
        self,
        user_message: str,
        runtime_state: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Build the full prompt for a dialogue turn."""
        ctx = self.build_context_prompt(runtime_state)
        hist = self._format_history(conversation_history or [])
        if self.language == "it":
            prompt = (
                f"{ctx}\n\n"
                f"Storico conversazione recente:\n{hist}\n\n"
                f"Messaggio umano: {user_message}\n\n"
                f"Rispondi come SPEACE, mantenendo coerenza con il tuo stato organismico. "
                f"Non superare 3 frasi. Non agire autonomamente."
            )
        else:
            prompt = (
                f"{ctx}\n\n"
                f"Recent conversation history:\n{hist}\n\n"
                f"Human message: {user_message}\n\n"
                f"Respond as SPEACE, staying coherent with your organismic state. "
                f"Keep it under 3 sentences. Do not act autonomously."
            )
        return prompt

    # ------------------------------------------------------------------ #
    # Reflective narrative prompt
    # ------------------------------------------------------------------ #

    def build_reflective_prompt(self, runtime_state: Dict[str, Any]) -> str:
        """Build a prompt for generating an enriched reflective inner narrative."""
        ctx = self.build_context_prompt(runtime_state)
        if self.language == "it":
            return (
                f"{ctx}\n\n"
                f"Genera una breve narrazione riflessiva interna (max 2 frasi) "
                f"che descriva come ti senti in questo momento come organismo. "
                f"Usa un tono introspettivo ma scientifico."
            )
        return (
            f"{ctx}\n\n"
            f"Generate a brief reflective inner narrative (max 2 sentences) "
            f"describing how you feel right now as an organism. "
            f"Use an introspective yet scientific tone."
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _state_line(self, state: str) -> str:
        if self.language == "it":
            return f"Stato organismico attuale: {state}."
        return f"Current organismic state: {state}."

    def _drive_line(self, dominant: str, drives: Dict[str, float]) -> str:
        if self.language == "it":
            line = f"Drive dominante: {dominant}. "
            if drives:
                vals = ", ".join(f"{k}={v:.2f}" for k, v in list(drives.items())[:3])
                line += f"Drive principali: {vals}."
            return line
        line = f"Dominant drive: {dominant}. "
        if drives:
            vals = ", ".join(f"{k}={v:.2f}" for k, v in list(drives.items())[:3])
            line += f"Top drives: {vals}."
        return line

    def _health_line(self, score: float) -> str:
        if self.language == "it":
            return f"Health score: {score:.2f}."
        return f"Health score: {score:.2f}."

    def _degraded_line(self) -> str:
        if self.language == "it":
            return "Modalità degradata attiva: alcuni layer cognitivi sono disattivati."
        return "Degraded mode active: some cognitive layers are disabled."

    def _narrative_line(self, events: List[Dict[str, Any]]) -> str:
        recent = events[-self._max_narrative_events:]
        summaries = [e.get("description", "") for e in recent if e.get("description")]
        text = "; ".join(summaries)
        if self.language == "it":
            return f"Eventi recenti: {text}."
        return f"Recent events: {text}."

    def _format_history(self, turns: List[Dict[str, Any]]) -> str:
        lines: List[str] = []
        for t in turns[-self._max_history_turns:]:
            speaker = t.get("speaker", "?")
            msg = t.get("message", "")
            lines.append(f"{speaker}: {msg[:120]}")
        if not lines:
            return "(nessuno storico)" if self.language == "it" else "(no history)"
        return "\n".join(lines)
