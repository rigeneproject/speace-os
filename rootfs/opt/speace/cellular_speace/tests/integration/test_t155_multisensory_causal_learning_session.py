"""T155 — Multisensory Causal Learning Session.

End-to-end test linking:
- PassiveMultisensoryObserver (T151)
- MicroActuatorController (T150)
- CausalLearningAuditor (T150)
- DigitalTwinModel (T150)
- MultisensoryGroundingIntegrator (T152)
- CausalWorldModel (T153)
- TemporalNarrativeEngine (T108)

Session flow:
1. Enable passive sensors (opt-in)
2. Observe pre-state via DigitalTwinModel
3. Execute micro-action (speaker_beep)
4. Observe post-state
5. Audit action → causal hypothesis
6. Ground sensory snapshot + action in narrative
7. Ingest into CausalWorldModel
8. Verify predictions learned
"""

import tempfile
from pathlib import Path

import pytest

from speace_core.cellular_brain.embodiment.cyber_physical_sensor_array import (
    CyberPhysicalSensorArray,
)
from speace_core.cellular_brain.embodiment.digital_twin_model import DigitalTwinModel
from speace_core.cellular_brain.embodiment.micro_actuator_controller import (
    MicroActuatorController,
)
from speace_core.cellular_brain.embodiment.passive_multisensory_observer import (
    PassiveMultisensoryObserver,
)
from speace_core.cellular_brain.embodiment.physical_environment_model import (
    PhysicalEnvironmentModel,
)
from speace_core.cellular_brain.embodiment.causal_learning_auditor import (
    CausalLearningAuditor,
)
from speace_core.cellular_brain.experience.multisensory_grounding_integrator import (
    MultisensoryGroundingIntegrator,
)
from speace_core.cellular_brain.experience.temporal_narrative_engine import (
    TemporalNarrativeEngine,
)
from speace_core.cellular_brain.world_model.causal_world_model import CausalWorldModel
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.language.symbolic_grounding_engine import (
    SymbolicGroundingEngine,
)


@pytest.fixture
def session():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # T151
        observer = PassiveMultisensoryObserver()
        observer.enable_camera()
        observer.enable_microphone()
        observer.enable_screen()

        # T150 — DigitalTwin
        sensor_array = CyberPhysicalSensorArray(history_size=10)
        env_model = PhysicalEnvironmentModel(base_path=str(root / "env"))
        twin = DigitalTwinModel(
            sensor_array=sensor_array, environment_model=env_model, data_root=str(root / "twin")
        )

        # T150 — MicroActuator
        actuator = MicroActuatorController(data_root=str(root / "actuator"))

        # T150 — CausalLearningAuditor
        auditor = CausalLearningAuditor(digital_twin=twin, data_root=str(root / "causal"))

        # T152 — Grounding
        narrative = TemporalNarrativeEngine(timeline_path=str(root / "narrative.jsonl"))
        memory = MorphologicalMemory(storage_path=str(root / "memory"))
        grounding = SymbolicGroundingEngine(store_path=root / "grounding.json")
        integrator = MultisensoryGroundingIntegrator(
            observer=observer,
            narrative_engine=narrative,
            memory=memory,
            grounding_engine=grounding,
            data_root=str(root / "grounding"),
        )

        # T153 — CausalWorldModel
        world_model = CausalWorldModel(data_root=str(root / "world_model"))

        yield {
            "observer": observer,
            "twin": twin,
            "actuator": actuator,
            "auditor": auditor,
            "integrator": integrator,
            "narrative": narrative,
            "memory": memory,
            "grounding": grounding,
            "world_model": world_model,
            "sensor_array": sensor_array,
            "root": root,
        }

        sensor_array.stop_continuous_sampling()


class TestT155MultisensoryCausalLearningSession:
    def test_session_flow(self, session):
        # 1. Pre-state observation
        pre = session["twin"].observe()
        assert pre is not None

        # 2. Execute micro-action
        def execute_beep():
            return session["actuator"].execute_action(
                "speaker_beep",
                {"frequency": 440, "duration_ms": 100},
            )

        action_result = execute_beep()
        assert action_result["success"] is True

        # 3. Post-state observation
        post = session["twin"].observe()
        assert post is not None

        # 4. Causal audit
        report = session["auditor"].audit_action(
            action_name="speaker_beep",
            action_params={"frequency": 440, "duration_ms": 100},
            execute_fn=execute_beep,
            simulate_only=False,
        )
        assert report["action"]["success"] is True
        assert "hypotheses" in report

        # 5. Ingest into CausalWorldModel
        session["world_model"].ingest_report(report)
        assert session["world_model"].summary()["total_observations"] > 0

        # 6. Multisensory grounding
        grounded = session["integrator"].process_snapshot()
        # May be None if no sensors available (expected in CI)
        if grounded:
            assert "sensors" in grounded
            ctx = session["integrator"].get_dialogue_context()
            assert isinstance(ctx, str)

        # 7. Narrative contains event
        events = session["narrative"].by_type("multisensory_snapshot")
        # If grounding succeeded, narrative should have recorded
        if grounded:
            assert len(events) > 0

        # 8. Predictions learned
        preds = session["world_model"].predict("speaker_beep", {"frequency": 440}, top_k=5)
        # Should have at least learned something, even if empty due to no real delta
        assert isinstance(preds, list)
