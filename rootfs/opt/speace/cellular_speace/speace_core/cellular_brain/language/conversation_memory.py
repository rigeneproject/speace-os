"""ConversationMemory — persists dialogue turns for T107.

Format per turn:
  {"timestamp": float, "speaker": "user"|"speace", "message": str,
   "grounded_assembly_id": str|null}
"""

import json
import pathlib
import time
from typing import Any, Dict, List, Optional


class ConversationMemory:
    """Append-only dialogue history with bounded retrieval."""

    def __init__(
        self,
        history_path: str = "data/dialogue/dialogue_history.jsonl",
        max_turns: int = 10000,
    ) -> None:
        self.history_path = pathlib.Path(history_path)
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_turns = max_turns

    def append(
        self,
        speaker: str,
        message: str,
        grounded_assembly_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        turn = {
            "timestamp": time.time(),
            "speaker": speaker,
            "message": message,
            "grounded_assembly_id": grounded_assembly_id,
        }
        try:
            with self.history_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(turn, ensure_ascii=False) + "\n")
        except OSError:
            pass
        self._trim()
        return turn

    def recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        if not self.history_path.exists():
            return []
        turns: List[Dict[str, Any]] = []
        try:
            with self.history_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        turns.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            return []
        return turns[-limit:]

    def _trim(self) -> None:
        turns = self.recent(limit=0)
        if len(turns) > self.max_turns:
            turns = turns[-self.max_turns:]
            try:
                with self.history_path.open("w", encoding="utf-8") as f:
                    for t in turns:
                        f.write(json.dumps(t, ensure_ascii=False) + "\n")
            except OSError:
                pass
