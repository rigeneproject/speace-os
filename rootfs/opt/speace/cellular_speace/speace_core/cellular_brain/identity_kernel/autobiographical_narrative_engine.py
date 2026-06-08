import json
import pathlib
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class NarrativeChapter(BaseModel):
    title: str
    period: str
    themes: List[str] = []
    key_events: List[str] = []
    outcome_summary: str
    tick_start: int = 0
    tick_end: int = 0

    model_config = ConfigDict(arbitrary_types_allowed=True)


class AutobiographicalNarrativeEngine:
    """Synthesizes episodes into narrative chapters."""

    def __init__(self, storage_path: Optional[pathlib.Path] = None):
        self._storage_path = storage_path or pathlib.Path(
            "data/identity_kernel/life_story.jsonl"
        )
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)

    def synthesize_narrative(
        self,
        episodes: List[Any],
        tick_start: int,
        tick_end: int,
    ) -> Optional[NarrativeChapter]:
        if not episodes:
            return None

        outcomes = [getattr(ep, "outcome", "unknown") for ep in episodes]
        triggers = [getattr(ep, "trigger", "unknown") for ep in episodes]
        outcome_counter = Counter(outcomes)
        trigger_counter = Counter(triggers)

        dominant_outcome = outcome_counter.most_common(1)[0][0]
        dominant_trigger = trigger_counter.most_common(1)[0][0]
        themes = list(set(outcomes + triggers))

        title = f"Chapter: {dominant_trigger} to {dominant_outcome}"
        period = f"ticks {tick_start}-{tick_end}"
        key_events = [f"{getattr(ep, 'trigger', '?')} -> {getattr(ep, 'outcome', '?')}" for ep in episodes[:5]]
        outcome_summary = f"Dominant outcome: {dominant_outcome} ({outcome_counter[dominant_outcome]}/{len(episodes)} episodes)"

        return NarrativeChapter(
            title=title,
            period=period,
            themes=themes,
            key_events=key_events,
            outcome_summary=outcome_summary,
            tick_start=tick_start,
            tick_end=tick_end,
        )

    def append_to_life_story(self, chapter: NarrativeChapter) -> None:
        with open(self._storage_path, "a", encoding="utf-8") as f:
            f.write(chapter.model_dump_json() + "\n")

    def load_chapters(self) -> List[NarrativeChapter]:
        chapters = []
        if not self._storage_path.exists():
            return chapters
        with open(self._storage_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    chapters.append(NarrativeChapter.model_validate_json(line))
                except Exception:
                    continue
        return chapters
