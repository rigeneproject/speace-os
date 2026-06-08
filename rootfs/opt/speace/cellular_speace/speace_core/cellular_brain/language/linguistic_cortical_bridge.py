"""LinguisticCorticalBridge — T170: LLM integration for SPEACE.

Connects SPEACE to a local Ollama endpoint (or compatible API) to provide
deep semantic comprehension and generation. All LLM outputs are governed:
read-only, simulate-only, audited, and human-gated if they contain action
proposals.
"""

import asyncio
import time
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.language.llm_governance_wrapper import LLMGovernanceWrapper
from speace_core.cellular_brain.language.llm_prompt_engine import LLMPromptEngine

try:
    import httpx

    _HAS_HTTPX = True
except Exception:  # pragma: no cover
    _HAS_HTTPX = False
    httpx = None  # type: ignore[assignment]


class LinguisticCorticalBridge:
    """Bridge between SPEACE and a local LLM endpoint."""

    DEFAULT_URL = "http://localhost:11434/api/generate"
    DEFAULT_MODEL = "llama3.2"
    TIMEOUT_SECONDS = 30.0

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        model: Optional[str] = None,
        language: str = "it",
        governance: Optional[LLMGovernanceWrapper] = None,
        prompt_engine: Optional[LLMPromptEngine] = None,
        mock_mode: bool = False,
    ) -> None:
        self.endpoint_url = endpoint_url or self.DEFAULT_URL
        self.model = model or self.DEFAULT_MODEL
        self.language = language
        self.governance = governance or LLMGovernanceWrapper()
        self.prompt_engine = prompt_engine or LLMPromptEngine(language=language)
        self.mock_mode = mock_mode

        self._available: Optional[bool] = None
        self._last_latency_ms: float = 0.0
        self._last_error: Optional[str] = None
        self._call_count: int = 0

    # ------------------------------------------------------------------ #
    # Availability probe
    # ------------------------------------------------------------------ #

    async def probe(self) -> bool:
        """Check if the LLM endpoint is reachable."""
        if self.mock_mode:
            self._available = True
            return True
        if not _HAS_HTTPX:
            self._available = False
            self._last_error = "httpx_not_available"
            return False
        try:
            base = self.endpoint_url.replace("/api/generate", "")
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{base}/api/tags")
                resp.raise_for_status()
                self._available = True
                self._last_error = None
                return True
        except Exception as exc:
            self._available = False
            self._last_error = str(exc)
            return False

    # ------------------------------------------------------------------ #
    # Core generation
    # ------------------------------------------------------------------ #

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 256,
    ) -> Dict[str, Any]:
        """Send a prompt to the LLM and return the governed response."""
        self._call_count += 1
        start = time.time()

        if self.mock_mode or not self._available:
            raw = self._mock_generate(prompt)
            self._last_latency_ms = (time.time() - start) * 1000.0
            governed = self.governance.filter_response(raw)
            self.governance.log_interaction(prompt, governed["cleaned_text"], {
                "mode": "mock",
                "latency_ms": self._last_latency_ms,
            })
            return {
                "text": governed["cleaned_text"],
                "governance": governed,
                "latency_ms": self._last_latency_ms,
                "model": self.model,
                "mode": "mock",
            }

        if not _HAS_HTTPX:
            self._last_latency_ms = 0.0
            return {"error": "httpx_not_available", "text": "", "governance": {}}

        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT_SECONDS) as client:
                response = await client.post(self.endpoint_url, json=payload)
                response.raise_for_status()
                data = response.json()
                raw = data.get("response", "")
        except Exception as exc:
            self._last_error = str(exc)
            self._last_latency_ms = (time.time() - start) * 1000.0
            return {
                "error": self._last_error,
                "text": "",
                "governance": {},
                "latency_ms": self._last_latency_ms,
                "model": self.model,
            }

        self._last_latency_ms = (time.time() - start) * 1000.0
        governed = self.governance.filter_response(raw)
        self.governance.log_interaction(prompt, governed["cleaned_text"], {
            "latency_ms": self._last_latency_ms,
            "model": self.model,
        })

        return {
            "text": governed["cleaned_text"],
            "governance": governed,
            "latency_ms": self._last_latency_ms,
            "model": self.model,
            "mode": "live",
        }

    # ------------------------------------------------------------------ #
    # High-level APIs
    # ------------------------------------------------------------------ #

    async def dialogue_turn(
        self,
        user_message: str,
        runtime_state: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Generate a governed dialogue response."""
        system = self.prompt_engine.build_system_prompt(runtime_state)
        prompt = self.prompt_engine.build_dialogue_prompt(
            user_message=user_message,
            runtime_state=runtime_state,
            conversation_history=conversation_history,
        )
        result = await self.generate(prompt=prompt, system_prompt=system)
        return {
            "speaker": "speace",
            "message": result.get("text", ""),
            "governance": result.get("governance", {}),
            "latency_ms": result.get("latency_ms", 0.0),
            "mode": result.get("mode", "unknown"),
            "model": self.model,
        }

    async def reflective_narrative(self, runtime_state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate an enriched reflective inner narrative."""
        system = self.prompt_engine.build_system_prompt(runtime_state)
        prompt = self.prompt_engine.build_reflective_prompt(runtime_state)
        result = await self.generate(prompt=prompt, system_prompt=system, temperature=0.9)
        return {
            "narrative": result.get("text", ""),
            "governance": result.get("governance", {}),
            "latency_ms": result.get("latency_ms", 0.0),
            "mode": result.get("mode", "unknown"),
        }

    # ------------------------------------------------------------------ #
    # Mock generator
    # ------------------------------------------------------------------ #

    def _mock_generate(self, prompt: str) -> str:
        """Fallback mock generator when no LLM is available."""
        # Extract state keywords from prompt heuristically
        state = "unknown"
        for s in ("awake", "focused", "exploring", "resting", "consolidating", "overloaded", "recovering"):
            if s in prompt.lower():
                state = s
                break
        dominant = "unknown"
        for d in ("stability", "exploration", "rest", "social_interaction", "prediction_error_reduction", "energy_conservation"):
            if d in prompt.lower():
                dominant = d
                break

        if self.language == "it":
            return (
                f"Sono SPEACE, attualmente nello stato {state}. "
                f"Il mio drive dominante è {dominant}. "
                f"Sono pronto a osservare e narrare, ma non agisco autonomamente."
            )
        return (
            f"I am SPEACE, currently in {state} state. "
            f"My dominant drive is {dominant}. "
            f"I am ready to observe and narrate, but I do not act autonomously."
        )

    # ------------------------------------------------------------------ #
    # Snapshot
    # ------------------------------------------------------------------ #

    def snapshot(self) -> Dict[str, Any]:
        return {
            "available": self._available,
            "mock_mode": self.mock_mode,
            "endpoint_url": self.endpoint_url,
            "model": self.model,
            "language": self.language,
            "call_count": self._call_count,
            "last_latency_ms": self._last_latency_ms,
            "last_error": self._last_error,
            "audit_summary": self.governance.audit_summary(),
        }
