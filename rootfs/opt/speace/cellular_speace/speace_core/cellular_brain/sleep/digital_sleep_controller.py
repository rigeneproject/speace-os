from typing import Any, Optional

from speace_core.cellular_brain.sleep.sleep_cycle_detector import (
    SleepCycleDetector,
    SleepPhase,
    SleepState,
)
from speace_core.cellular_brain.sleep.memory_consolidation_engine import (
    ConsolidationResult,
    MemoryConsolidationEngine,
)
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType


class DigitalSleepController:
    """Coordinates digital sleep cycles and memory consolidation."""

    def __init__(
        self,
        sleep_duration_ticks: int = 5,
        detector: Optional[SleepCycleDetector] = None,
        consolidation_engine: Optional[MemoryConsolidationEngine] = None,
    ):
        self.sleep_duration_ticks = sleep_duration_ticks
        self.detector = detector or SleepCycleDetector()
        self.consolidation_engine = consolidation_engine or MemoryConsolidationEngine()
        self.state = SleepState()
        self.sleep_ticks_remaining: int = 0
        self.last_consolidation_result: Optional[ConsolidationResult] = None

    def tick(self, orchestrator: Any) -> None:
        """Evaluate sleep state and run consolidation if sleeping."""
        if self.state.phase == SleepPhase.SLEEPING:
            self._run_sleep_tick(orchestrator)
            return

        new_state = self.detector.detect(orchestrator.metrics_log)
        if new_state.phase == SleepPhase.SLEEP_ELIGIBLE:
            self.state.phase = SleepPhase.SLEEP_ELIGIBLE
            self.state.ticks_in_current_phase += 1
            if self.state.ticks_in_current_phase >= self.detector.min_consecutive_stable:
                self._enter_sleep(orchestrator)
        else:
            self.state.ticks_in_current_phase = 0
            self.state.phase = SleepPhase.AWAKE

    def _enter_sleep(self, orchestrator: Any) -> None:
        self.state.phase = SleepPhase.SLEEPING
        self.sleep_ticks_remaining = self.sleep_duration_ticks
        memory: Optional[MorphologicalMemory] = getattr(orchestrator, "_memory", None)
        if memory is not None:
            memory.create_event(
                event_type=MorphologyEventType.PHI_CHANGED,
                metadata={
                    "sleep_event": "sleep_entered",
                    "tick": getattr(orchestrator, "current_tick", 0),
                },
            )

    def _run_sleep_tick(self, orchestrator: Any) -> None:
        circuit = orchestrator.circuit
        memory: Optional[MorphologicalMemory] = getattr(orchestrator, "_memory", None)
        assemblies = None
        store = getattr(orchestrator, "_semantic_memory_store", None)
        if store is not None:
            assemblies = getattr(store, "_assemblies", None)
            if hasattr(assemblies, "values"):
                assemblies = list(assemblies.values())

        self.last_consolidation_result = self.consolidation_engine.run_full_cycle(
            circuit=circuit,
            assemblies=assemblies,
            memory=memory,
        )

        self.sleep_ticks_remaining -= 1
        if self.sleep_ticks_remaining <= 0:
            self._exit_sleep(orchestrator)

    def _exit_sleep(self, orchestrator: Any) -> None:
        self.state.phase = SleepPhase.AWAKE
        self.state.ticks_in_current_phase = 0
        memory: Optional[MorphologicalMemory] = getattr(orchestrator, "_memory", None)
        if memory is not None:
            memory.create_event(
                event_type=MorphologyEventType.PHI_CHANGED,
                metadata={
                    "sleep_event": "sleep_exited",
                    "tick": getattr(orchestrator, "current_tick", 0),
                    "consolidation": self.last_consolidation_result.model_dump()
                    if self.last_consolidation_result
                    else None,
                },
            )
