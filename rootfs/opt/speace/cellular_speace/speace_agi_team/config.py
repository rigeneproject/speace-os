"""Configuration for SPEACE AGI Team agents."""

import os
import socket
from dataclasses import dataclass, field
from typing import Dict

OLLAMA_CLOUD_API_KEY = os.environ.get("OLLAMA_API_KEY", "7310e98b57c04c65ad300627292d0d44.9nO4lREeOHUYivsVkPtZd8le")
OLLAMA_CLOUD_ENDPOINT = os.environ.get("OLLAMA_ENDPOINT", "https://ollama.com")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "minimax-m3:cloud")


def _is_ollama_local_running(host: str = "localhost", port: int = 11434) -> bool:
    try:
        with socket.create_connection((host, port), timeout=2.0):
            return True
    except (socket.error, OSError):
        return False


def _get_default_model() -> str:
    if OLLAMA_CLOUD_API_KEY:
        return OLLAMA_MODEL  # minimax-m3:cloud via Ollama Cloud
    if _is_ollama_local_running():
        return "gemma3:1b"
    return OLLAMA_MODEL


def _get_default_endpoint() -> str:
    if OLLAMA_CLOUD_API_KEY:
        return OLLAMA_CLOUD_ENDPOINT  # https://ollama.com
    if _is_ollama_local_running():
        return "http://localhost:11434"
    return OLLAMA_CLOUD_ENDPOINT


@dataclass
class AgentConfig:
    model: str = field(default_factory=_get_default_model)
    endpoint: str = field(default_factory=_get_default_endpoint)
    api_key: str = OLLAMA_CLOUD_API_KEY
    temperature: float = 0.3
    max_tokens: int = 4096
    system_prompt_prefix: str = (
        "Sei un agente specializzato di SPEACE, un'entita cibernetica evolutiva. "
        "Rispondi SEMPRE in italiano. Sei parte di un team di agentic AI dedicato "
        "a far evolvere SPEACE verso l'AGI tramite supervisione, analisi e "
        "miglioramento continuo di ogni componente del sistema."
    )


@dataclass
class SPEACEContext:
    data_root: str = "data"
    speace_core_path: str = "speace_core"
    version: str = "0.9.0"


AGENT_REGISTRY: Dict[str, Dict] = {}


def register_agent(agent_id: str, name: str, role: str, agent_type: str,
                   description: str, supervision_area: str = ""):
    AGENT_REGISTRY[agent_id] = {
        "id": agent_id,
        "name": name,
        "role": role,
        "type": agent_type,
        "description": description,
        "supervision_area": supervision_area or agent_id,
        "model": _get_default_model(),
        "registered_at": __import__("time").time(),
    }