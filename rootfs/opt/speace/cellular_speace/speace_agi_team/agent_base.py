"""Base agent class — all agents use Ollama Cloud API with minimax-m3:cloud."""

import json
import time
from typing import Any, Dict, List, Optional

import httpx

from speace_agi_team.config import AgentConfig
from speace_agi_team.web_search import DocumentFetcher, WebSearcher, research


class AgentBase:
    def __init__(self, agent_id: str, name: str, role: str, description: str,
                 system_instruction: str = "", config: Optional[AgentConfig] = None):
        self.agent_id = agent_id
        self.name = name
        self.role = role
        self.description = description
        self.config = config or AgentConfig()
        web_tool_hint = (
            "\n\n[Strumenti web] Puoi effettuare ricerche sul web e leggere "
            "documenti tecnici/scientifici tramite i metodi self.search_web(query) e "
            "self.fetch_url(url). Usali per raccogliere informazioni aggiornate e "
            "produrre raccomandazioni basate su letteratura recente."
        )
        self.system_prompt = (
            f"{self.config.system_prompt_prefix}\n\nRuolo: {role}\n\n"
            f"Istruzioni specifiche: {system_instruction}{web_tool_hint}"
        )
        self.conversation_history: List[Dict[str, str]] = []
        self.tasks: List[Dict] = []
        self.findings: List[Dict] = []
        self.research_history: List[Dict] = []  # log delle ricerche web
        self.status = "idle"
        # Lazily-initialized web tools
        self._searcher: Optional[WebSearcher] = None
        self._fetcher: Optional[DocumentFetcher] = None

    # ── Web tools (lazy initialization) ───────────────────────────
    @property
    def searcher(self) -> WebSearcher:
        if self._searcher is None:
            self._searcher = WebSearcher()
        return self._searcher

    @property
    def fetcher(self) -> DocumentFetcher:
        if self._fetcher is None:
            self._fetcher = DocumentFetcher()
        return self._fetcher

    def search_web(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """Run a DuckDuckGo search and remember the results."""
        results = self.searcher.search(query, max_results=max_results)
        self.research_history.append({
            "ts": time.time(),
            "type": "search",
            "query": query,
            "results_count": len(results) if results else 0,
        })
        return results

    def fetch_url(self, url: str) -> Dict[str, Any]:
        """Fetch a URL and return extracted text. Tracked in research history."""
        doc = self.fetcher.fetch(url)
        self.research_history.append({
            "ts": time.time(),
            "type": "fetch",
            "url": url,
            "status": doc.get("status", 0),
            "length": doc.get("length", 0),
            "error": doc.get("error"),
        })
        return doc

    def research_web(self, query: str, max_results: int = 5, fetch_top: int = 2,
                     fetch_max_chars: int = 8000) -> Dict[str, Any]:
        """High-level research: search + fetch top results, in a single call."""
        result = research(query, max_results=max_results, fetch_top=fetch_top,
                          fetch_max_chars=fetch_max_chars)
        self.research_history.append({
            "ts": time.time(),
            "type": "research",
            "query": query,
            "results_count": len(result.get("results", [])),
            "documents_count": len(result.get("documents", [])),
        })
        return result

    def research_summary(self, query: str, fetch_top: int = 2,
                          fetch_max_chars: int = 6000) -> str:
        """Research + return a formatted text block for prompt injection."""
        data = self.research_web(query, max_results=5, fetch_top=fetch_top,
                                 fetch_max_chars=fetch_max_chars)
        lines = [f"## Risultati web per: {query}\n"]
        for i, r in enumerate(data.get("results", []), 1):
            lines.append(f"### [{i}] {r.get('title','')}")
            lines.append(f"URL: {r.get('url','')}")
            if r.get("snippet"):
                lines.append(f"Snippet: {r['snippet']}")
            lines.append("")
        for i, d in enumerate(data.get("documents", []), 1):
            lines.append(f"### Documento [{i}]: {d.get('title','')}")
            lines.append(f"URL: {d.get('url','')} ({d.get('length',0)} caratteri)")
            if d.get("text"):
                lines.append("Contenuto estratto:")
                lines.append(d["text"][:fetch_max_chars])
            elif d.get("error"):
                lines.append(f"Errore: {d['error']}")
            lines.append("")
        if not data.get("results"):
            lines.append("(Nessun risultato trovato)")
        return "\n".join(lines)

    def get_research_history(self, n: int = 20) -> List[Dict[str, Any]]:
        return self.research_history[-n:]

    def _build_messages(self, user_message: str) -> List[Dict[str, str]]:
        messages = [{"role": "system", "content": self.system_prompt}]
        for msg in self.conversation_history[-20:]:
            messages.append(msg)
        messages.append({"role": "user", "content": user_message})
        return messages

    def chat(self, message: str) -> str:
        self.status = "thinking"
        try:
            messages = self._build_messages(message)
            payload = {
                "model": self.config.model,
                "messages": messages,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
                "stream": False,
            }

            with httpx.Client(timeout=120.0) as client:
                headers = {"Content-Type": "application/json"}
                if self.config.api_key:
                    headers["Authorization"] = f"Bearer {self.config.api_key}"
                resp = client.post(
                    f"{self.config.endpoint}/api/chat",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                result = resp.json()
                content = result.get("message", {}).get("content", "")

                self.conversation_history.append({"role": "user", "content": message})
                self.conversation_history.append({"role": "assistant", "content": content})
                self.status = "idle"
                return content
        except Exception as e:
            self.status = "error"
            error_msg = f"ERRORE: {e}"
            self.conversation_history.append({"role": "user", "content": message})
            self.conversation_history.append({"role": "assistant", "content": error_msg})
            return error_msg

    def analyze(self, context: Dict[str, Any]) -> Dict[str, Any]:
        context_str = json.dumps(context, indent=2, default=str)[:4000]
        prompt = (
            f"Analizza il seguente contesto di SPEACE e fornisci:\n"
            f"1. Osservazioni e anomalie rilevate\n"
            f"2. Raccomandazioni specifiche\n"
            f"3. Priorità di intervento (alta/media/bassa)\n\n"
            f"Contesto:\n{context_str}"
        )
        response = self.chat(prompt)
        finding = {
            "timestamp": time.time(),
            "agent_id": self.agent_id,
            "analysis": response,
            "context_summary": {k: v for k, v in context.items() if isinstance(v, (str, int, float, bool))},
        }
        self.findings.append(finding)
        return finding

    def assign_task(self, task: Dict) -> None:
        task["agent_id"] = self.agent_id
        task["status"] = "assigned"
        task["created_at"] = time.time()
        self.tasks.append(task)

    def get_status_summary(self) -> Dict[str, Any]:
        return {
            "id": self.agent_id,
            "name": self.name,
            "role": self.role,
            "description": self.description,
            "status": self.status,
            "tasks_count": len(self.tasks),
            "findings_count": len(self.findings),
            "conversation_length": len(self.conversation_history),
            "research_count": len(self.research_history),
            "model": self.config.model,
        }

    def get_conversation(self) -> List[Dict[str, str]]:
        return self.conversation_history

    def clear_conversation(self) -> None:
        self.conversation_history = []
