from typing import Any

from speace_core.cellular_brain.runtime.subsystem_plugin import SubsystemPlugin


class MemoryCoordinator(SubsystemPlugin):
    """Coordinates semantic, associative, and episodic memory engines."""

    @property
    def name(self) -> str:
        return "memory"

    def on_tick(self, context: Any) -> None:
        orch = context.orchestrator_ref()
        if orch.semantic_memory_enabled and orch._cell_assembly_engine is not None:
            orch._cell_assembly_engine.run_semantic_memory_cycle(orch)
        if (
            orch.semantic_memory_enabled
            and orch.associative_learning_enabled
            and orch._semantic_memory_store is not None
            and orch._associative_learning_engine is not None
        ):
            active_assemblies = orch._semantic_memory_store.list_active()
            orch._associative_learning_engine.observe_assemblies(
                active_assemblies, tick=orch.current_tick
            )

    def run_semantic_memory_cycle(self, context: Any):
        orch = context.orchestrator_ref()
        if orch.semantic_memory_enabled and orch._cell_assembly_engine is not None:
            return orch._cell_assembly_engine.run_semantic_memory_cycle(orch)
        return None

    def recall_semantic_memory(self, context: Any, query_signature):
        orch = context.orchestrator_ref()
        if orch.semantic_memory_enabled and orch._semantic_recall_engine is not None:
            return orch._semantic_recall_engine.recall(query_signature)
        return None

    def get_semantic_memory_metrics(self, context: Any):
        orch = context.orchestrator_ref()
        if orch.semantic_memory_enabled and orch._cell_assembly_engine is not None:
            return orch._cell_assembly_engine._compute_metrics()
        return None

    def run_associative_learning_cycle(self, context: Any):
        orch = context.orchestrator_ref()
        if (
            orch.semantic_memory_enabled
            and orch.associative_learning_enabled
            and orch._semantic_memory_store is not None
        ):
            engine = orch.get_associative_learning_engine()
            active_assemblies = orch._semantic_memory_store.list_active()
            return engine.observe_assemblies(active_assemblies, tick=orch.current_tick)
        return None

    def recall_associative_memory(self, context: Any, cue_assembly_id: str):
        orch = context.orchestrator_ref()
        if orch.associative_recall_enabled:
            engine = orch.get_associative_recall_engine()
            return engine.recall_from_assembly(cue_assembly_id)
        return None

    def start_episode(self, context: Any, trigger: str, initial_metrics=None, tick_id=0):
        orch = context.orchestrator_ref()
        if orch.episodic_memory_enabled:
            return orch.get_episodic_memory().start_episode(
                trigger=trigger,
                initial_metrics=initial_metrics or {},
                tick_id=tick_id,
            )
        return None

    def record_episode_event(
        self, context: Any, episode_id, event_type, source_module, metrics=None, metadata=None, tick_id=0
    ):
        orch = context.orchestrator_ref()
        if orch.episodic_memory_enabled and episode_id:
            return orch.get_episodic_memory().record_event(
                episode_id=episode_id,
                event_type=event_type,
                source_module=source_module,
                metrics=metrics,
                metadata=metadata,
                tick_id=tick_id,
            )
        return None

    def close_episode(self, context: Any, episode_id, final_metrics=None, outcome="unknown"):
        orch = context.orchestrator_ref()
        if orch.episodic_memory_enabled and episode_id:
            return orch.get_episodic_memory().close_episode(
                episode_id=episode_id,
                final_metrics=final_metrics or {},
                outcome=outcome,
            )
        return None

    # ------------------------------------------------------------------ #
    # Associative Pattern Completion Memory
    # ------------------------------------------------------------------ #

    def store_pattern_completion(self, context: Any, label: str, pattern):
        orch = context.orchestrator_ref()
        if orch.associative_pattern_completion_enabled:
            engine = orch.get_associative_pattern_completion()
            return engine.store_pattern(label, pattern)
        return None

    def complete_pattern(self, context: Any, partial_pattern, threshold: float = 0.8):
        orch = context.orchestrator_ref()
        if orch.associative_pattern_completion_enabled:
            engine = orch.get_associative_pattern_completion()
            return engine.complete_pattern(partial_pattern, threshold)
        return None

    def get_similar_pattern_states(self, context: Any, query):
        orch = context.orchestrator_ref()
        if orch.associative_pattern_completion_enabled:
            engine = orch.get_associative_pattern_completion()
            return engine.get_similar_states(query)
        return []
