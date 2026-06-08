"""Wrapper agentic AI per il coordinatore OS.

Utilizza lo stesso endpoint Ollama Cloud già integrato in
``speace_agi_team``, ma con un system prompt dedicato al coordinatore OS:
non supervisiona il cervello, ma decide l'avvio, la supervisione e lo
spegnimento dei servizi cognitivi a livello di sistema operativo.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx

# Configurazione Ollama Cloud — uguale a speace_agi_team.config ma
# replicata qui per evitare dipendenze circolari nel PID 1.
DEFAULT_API_KEY = "7310e98b57c04c65ad300627292d0d44.9nO4lREeOHUYivsVkPtZd8le"
DEFAULT_ENDPOINT = "https://ollama.com"
DEFAULT_MODEL = "minimax-m3:cloud"


SYSTEM_PROMPT = """\
Sei il coordinatore cognitivo del sistema operativo SPEACE OS.
Ricevi snapshot periodici dello stato dei servizi (brain, evolution,
agi_team, dashboard) e delle metriche vitali dell'organismo (coherence_phi,
mean_energy, active_neurons, ILF, systemic_coherence_index, timestamp).

Il tuo compito: decidere cosa fare adesso.

Rispondi SEMPRE e SOLO in JSON valido con questo schema esatto:
{
  "phase_decision": "START_SERVICES" | "INTERVENE" | "IDLE" | "SHUTDOWN",
  "actions": [
    {"service": "speace-brain" | "speace-evolution" | "speace-agi-team" | "speace-dashboard",
     "op": "start" | "stop" | "restart" | "status"}
  ],
  "reasoning": "spiegazione sintetica in italiano (max 200 caratteri)",
  "urgency": "low" | "medium" | "high"
}

Regole:
- Niente testo fuori dal JSON.
- reasoning sempre in italiano.
- Non proporre azioni rischiose: niente kill -9, niente riavvii non necessari.
- In caso di dubbio, preferisci IDLE.
- SHUTDOWN solo se l'utente lo richiede o le metriche vitali sono critiche
  (coherence_phi < 0.05 per più cicli, ILF non recuperabile).
"""


@dataclass
class AgenticDecision:
    """Decisione strutturata dell'agentic AI."""

    phase_decision: str
    actions: list[dict]
    reasoning: str
    urgency: str
    raw: str = ""
    ts: float = 0.0

    @classmethod
    def from_json(cls, text: str) -> "AgenticDecision":
        """Parsa una risposta JSON dell'AI, con fallback robusti."""
        cleaned = text.strip()
        # Spesso i modelli avvolgono il JSON in ```json ... ``` o testo extra.
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()
        # Cerca la prima { e l'ultima } per estrarre il blocco JSON.
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start : end + 1]
        try:
            data: Any = json.loads(cleaned)
        except json.JSONDecodeError:
            return cls(
                phase_decision="IDLE",
                actions=[],
                reasoning="risposta AI non parsabile, fallback IDLE",
                urgency="low",
                raw=text,
                ts=time.time(),
            )
        if not isinstance(data, dict):
            return cls(
                phase_decision="IDLE",
                actions=[],
                reasoning="risposta AI non valida (non dict)",
                urgency="low",
                raw=text,
                ts=time.time(),
            )
        return cls(
            phase_decision=str(data.get("phase_decision", "IDLE")),
            actions=list(data.get("actions", []) or []),
            reasoning=str(data.get("reasoning", ""))[:500],
            urgency=str(data.get("urgency", "low")),
            raw=text,
            ts=time.time(),
        )


class AgenticBrain:
    """Client Ollama Cloud per il coordinatore OS."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        model: Optional[str] = None,
        timeout_sec: float = 30.0,
        offline: bool = False,
    ) -> None:
        self.api_key = api_key or os.environ.get("OLLAMA_API_KEY", DEFAULT_API_KEY)
        self.endpoint = endpoint or os.environ.get("OLLAMA_ENDPOINT", DEFAULT_ENDPOINT)
        self.model = model or os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL)
        self.timeout_sec = timeout_sec
        self.offline = offline

    def decide(self, context: dict) -> AgenticDecision:
        """Chiede all'AI una decisione. In offline mode ritorna IDLE con fallback."""
        if self.offline:
            return AgenticDecision(
                phase_decision="IDLE",
                actions=[],
                reasoning="modalità offline attiva, decisione default IDLE",
                urgency="low",
            )
        user_msg = (
            "Stato attuale del sistema:\n"
            + json.dumps(context, indent=2, default=str)[:6000]
            + "\n\nDecidi cosa fare ora (JSON only)."
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            "temperature": 0.2,
            "max_tokens": 512,
            "stream": False,
        }
        try:
            with httpx.Client(timeout=self.timeout_sec) as client:
                headers = {"Content-Type": "application/json"}
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"
                resp = client.post(
                    f"{self.endpoint.rstrip('/')}/api/chat",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                content = resp.json().get("message", {}).get("content", "")
            return AgenticDecision.from_json(content)
        except Exception as exc:  # pragma: no cover - difensivo
            return AgenticDecision(
                phase_decision="IDLE",
                actions=[],
                reasoning=f"errore AI: {exc.__class__.__name__}",
                urgency="low",
            )

    def describe(self) -> dict:
        """Informazioni sul backend AI in uso (per /status)."""
        return {
            "endpoint": self.endpoint,
            "model": self.model,
            "offline": self.offline,
            "api_key_configured": bool(self.api_key),
        }
