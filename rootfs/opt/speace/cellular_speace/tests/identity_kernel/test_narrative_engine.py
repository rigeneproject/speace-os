import pytest
from pydantic import BaseModel

from speace_core.cellular_brain.identity_kernel.autobiographical_narrative_engine import (
    AutobiographicalNarrativeEngine,
    NarrativeChapter,
)


class FakeEpisode(BaseModel):
    trigger: str
    outcome: str
    start_tick: int = 0
    end_tick: int = 1


def test_synthesize_narrative_basic():
    engine = AutobiographicalNarrativeEngine()
    episodes = [
        FakeEpisode(trigger="hunger", outcome="feed"),
        FakeEpisode(trigger="threat", outcome="escape"),
        FakeEpisode(trigger="hunger", outcome="feed"),
    ]
    chapter = engine.synthesize_narrative(episodes, tick_start=0, tick_end=10)
    assert chapter is not None
    assert "Chapter" in chapter.title
    assert chapter.tick_start == 0
    assert chapter.tick_end == 10
    assert len(chapter.key_events) == 3
    assert "feed" in chapter.outcome_summary


def test_synthesize_narrative_empty():
    engine = AutobiographicalNarrativeEngine()
    chapter = engine.synthesize_narrative([], tick_start=0, tick_end=1)
    assert chapter is None


def test_append_and_load_chapters(tmp_path):
    engine = AutobiographicalNarrativeEngine(storage_path=tmp_path / "life_story.jsonl")
    chapter = NarrativeChapter(
        title="Test Chapter",
        period="ticks 0-5",
        themes=["test"],
        key_events=["a -> b"],
        outcome_summary="ok",
        tick_start=0,
        tick_end=5,
    )
    engine.append_to_life_story(chapter)
    loaded = engine.load_chapters()
    assert len(loaded) == 1
    assert loaded[0].title == "Test Chapter"
