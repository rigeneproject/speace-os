from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.identity_kernel.autobiographical_narrative_engine import (
    AutobiographicalNarrativeEngine,
    NarrativeChapter,
)
from speace_core.cellular_brain.identity_kernel.cross_clone_coherence_checker import (
    CrossCloneCoherenceChecker,
    CoherenceReport,
)
from speace_core.cellular_brain.identity_kernel.ontogenetic_stage_tracker import (
    OntogeneticStageTracker,
    StageEvaluation,
)
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType


class IdentityKernel:
    """Coordinates autobiographical identity, coherence, and ontogenetic tracking."""

    def __init__(
        self,
        narrative_engine: Optional[AutobiographicalNarrativeEngine] = None,
        coherence_checker: Optional[CrossCloneCoherenceChecker] = None,
        stage_tracker: Optional[OntogeneticStageTracker] = None,
    ):
        self.narrative_engine = narrative_engine or AutobiographicalNarrativeEngine()
        self.coherence_checker = coherence_checker or CrossCloneCoherenceChecker()
        self.stage_tracker = stage_tracker or OntogeneticStageTracker()
        self.last_chapter: Optional[NarrativeChapter] = None
        self.last_coherence: Optional[CoherenceReport] = None
        self.last_stage_eval: Optional[StageEvaluation] = None

    def tick(self, orchestrator: Any) -> None:
        """Run one identity kernel cycle."""
        memory: Optional[MorphologicalMemory] = getattr(orchestrator, "_memory", None)
        current_tick = getattr(orchestrator, "current_tick", 0)

        # Update ontogenetic stage
        latest_metrics = getattr(orchestrator, "latest_metrics", None)
        capabilities = self._collect_capabilities(orchestrator)
        clone_count = getattr(orchestrator, "clone_count", 1)

        self.last_stage_eval = self.stage_tracker.evaluate_stage_transition(
            metrics=latest_metrics or {},
            capabilities=capabilities,
            clone_count=clone_count,
        )
        if self.last_stage_eval.transition_ready:
            self.stage_tracker.advance_stage()
            if memory is not None:
                memory.create_event(
                    event_type=MorphologyEventType.PHI_CHANGED,
                    metadata={
                        "identity_event": "stage_transition",
                        "new_stage": self.stage_tracker.current_stage,
                        "tick": current_tick,
                    },
                )

        # Synthesize narrative from recent episodes
        episodic_memory = getattr(orchestrator, "_episodic_memory", None)
        if episodic_memory is not None:
            episodes = getattr(episodic_memory, "episodes", [])
            if episodes:
                # Use last 10 episodes
                recent = episodes[-10:]
                tick_start = getattr(recent[0], "start_tick", current_tick)
                tick_end = getattr(recent[-1], "end_tick", current_tick)
                chapter = self.narrative_engine.synthesize_narrative(
                    recent, tick_start, tick_end
                )
                if chapter is not None:
                    self.narrative_engine.append_to_life_story(chapter)
                    self.last_chapter = chapter
                    if memory is not None:
                        memory.create_event(
                            event_type=MorphologyEventType.PHI_CHANGED,
                            metadata={
                                "identity_event": "narrative_synthesized",
                                "chapter_title": chapter.title,
                                "tick": current_tick,
                            },
                        )

        # Check clone coherence
        clone_states = getattr(orchestrator, "clone_states", {})
        if clone_states:
            self.last_coherence = self.coherence_checker.check_coherence(clone_states)
            if not self.last_coherence.coherent and memory is not None:
                memory.create_event(
                    event_type=MorphologyEventType.PHI_CHANGED,
                    metadata={
                        "identity_event": "coherence_violation",
                        "violations": self.last_coherence.violations,
                        "coherence_score": self.last_coherence.coherence_score,
                        "tick": current_tick,
                    },
                )

    def _collect_capabilities(self, orchestrator: Any) -> List[str]:
        caps = []
        if getattr(orchestrator, "semantic_memory_enabled", False):
            caps.append("semantic_memory")
        if getattr(orchestrator, "self_improvement_enabled", False):
            caps.append("self_improvement")
        if getattr(orchestrator, "episodic_memory_enabled", False):
            caps.append("episodic_memory")
        if getattr(orchestrator, "sleep_enabled", False):
            caps.append("sleep")
        if getattr(orchestrator, "immune_enabled", False):
            caps.append("immune")
        if getattr(orchestrator, "tool_registry_enabled", False):
            caps.append("tool_registry")
        return caps
