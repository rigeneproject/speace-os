from unittest.mock import MagicMock

import pytest

from speace_core.cellular_brain.identity_kernel.identity_kernel import IdentityKernel


def test_identity_kernel_tick_stage_transition():
    kernel = IdentityKernel()
    orchestrator = MagicMock()
    orchestrator.current_tick = 10
    orchestrator.latest_metrics = {"coherence_phi": 0.8, "tick": 200}
    orchestrator.clone_count = 1
    orchestrator.semantic_memory_enabled = False
    orchestrator.self_improvement_enabled = False
    orchestrator.episodic_memory_enabled = False
    orchestrator.sleep_enabled = False
    orchestrator.immune_enabled = False
    orchestrator.tool_registry_enabled = False
    orchestrator._memory = None
    orchestrator._episodic_memory = None
    orchestrator.clone_states = {}

    kernel.tick(orchestrator)
    assert kernel.last_stage_eval is not None
    assert kernel.last_stage_eval.current_stage == "stage_0"


def test_identity_kernel_tick_narrative():
    kernel = IdentityKernel()
    orchestrator = MagicMock()
    orchestrator.current_tick = 10
    orchestrator.latest_metrics = {"coherence_phi": 0.8, "tick": 200}
    orchestrator.clone_count = 1
    orchestrator.semantic_memory_enabled = False
    orchestrator.self_improvement_enabled = False
    orchestrator.episodic_memory_enabled = True
    orchestrator.sleep_enabled = False
    orchestrator.immune_enabled = False
    orchestrator.tool_registry_enabled = False
    orchestrator._memory = None

    fake_episode = MagicMock()
    fake_episode.trigger = "test_trigger"
    fake_episode.outcome = "test_outcome"
    fake_episode.start_tick = 0
    fake_episode.end_tick = 5
    orchestrator._episodic_memory = MagicMock()
    orchestrator._episodic_memory.episodes = [fake_episode]
    orchestrator.clone_states = {}

    kernel.tick(orchestrator)
    assert kernel.last_chapter is not None
    assert "test_trigger" in kernel.last_chapter.title


def test_identity_kernel_tick_coherence_violation():
    kernel = IdentityKernel()
    orchestrator = MagicMock()
    orchestrator.current_tick = 10
    orchestrator.latest_metrics = {"coherence_phi": 0.8, "tick": 200}
    orchestrator.clone_count = 2
    orchestrator.semantic_memory_enabled = False
    orchestrator.self_improvement_enabled = False
    orchestrator.episodic_memory_enabled = False
    orchestrator.sleep_enabled = False
    orchestrator.immune_enabled = False
    orchestrator.tool_registry_enabled = False
    orchestrator._memory = None
    orchestrator._episodic_memory = None
    orchestrator.clone_states = {
        "a": {"species_orientation": "orient1"},
        "b": {"species_orientation": "orient2"},
    }

    kernel.tick(orchestrator)
    assert kernel.last_coherence is not None
    assert kernel.last_coherence.coherent is False
    assert "species_orientation_mismatch" in kernel.last_coherence.violations
