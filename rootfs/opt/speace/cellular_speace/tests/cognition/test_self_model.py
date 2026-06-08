import pytest
import tempfile

from speace_core.cellular_brain.cognition.self_model import SelfModel


class TestSelfModel:
    def test_initial_stage_defaults_to_embryonic(self):
        with tempfile.TemporaryDirectory() as td:
            model = SelfModel(base_path=td)
            assert model.get_developmental_stage() == "embryonic"

    def test_identity_signature_empty_on_init(self):
        with tempfile.TemporaryDirectory() as td:
            model = SelfModel(base_path=td)
            assert model.get_identity_signature() == []

    def test_update_returns_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            model = SelfModel(base_path=td)
            snapshot = model.update({"coherence_phi": 0.7})
            assert snapshot.tick == 1
            assert snapshot.coherence_phi == pytest.approx(0.7)
            assert snapshot.developmental_stage == "embryonic"

    def test_identity_vector_merges(self):
        with tempfile.TemporaryDirectory() as td:
            model = SelfModel(base_path=td, identity_vector=[1.0, 2.0])
            model.update({"identity_vector": [3.0, 4.0], "coherence_phi": 0.6})
            sig = model.get_identity_signature()
            assert len(sig) == 2
            assert sig[0] != 1.0
            assert sig[1] != 2.0

    def test_developmental_stage_updates(self):
        with tempfile.TemporaryDirectory() as td:
            model = SelfModel(base_path=td)
            model.update({"developmental_stage": "neonatal", "coherence_phi": 0.5})
            assert model.get_developmental_stage() == "neonatal"

    def test_is_coherent_above_threshold(self):
        with tempfile.TemporaryDirectory() as td:
            model = SelfModel(base_path=td)
            model.update({"coherence_phi": 0.8})
            assert model.is_coherent(threshold=0.5)
            assert not model.is_coherent(threshold=0.9)

    def test_is_coherent_false_when_no_history(self):
        with tempfile.TemporaryDirectory() as td:
            model = SelfModel(base_path=td)
            assert not model.is_coherent()

    def test_coherence_history_tracks(self):
        with tempfile.TemporaryDirectory() as td:
            model = SelfModel(base_path=td)
            model.update({"coherence_phi": 0.1})
            model.update({"coherence_phi": 0.2})
            model.update({"coherence_phi": 0.3})
            assert len(model.coherence_history) == 3
            assert model.coherence_history[-1] == pytest.approx(0.3)

    def test_narrative_trace_grows(self):
        with tempfile.TemporaryDirectory() as td:
            model = SelfModel(base_path=td)
            model.update({"coherence_phi": 0.5, "event": "test_event"})
            assert len(model.narrative_trace) == 1
            assert model.narrative_trace[0]["event"] == "test_event"

    def test_persistence_across_instances(self):
        with tempfile.TemporaryDirectory() as td:
            model1 = SelfModel(base_path=td, identity_vector=[0.1, 0.2])
            model1.update({"coherence_phi": 0.6, "developmental_stage": "infant"})

            model2 = SelfModel(base_path=td)
            assert model2.get_developmental_stage() == "infant"
            assert model2.coherence_history == pytest.approx([0.6])
            assert len(model2.get_identity_signature()) == 2

    def test_summary_contains_expected_keys(self):
        with tempfile.TemporaryDirectory() as td:
            model = SelfModel(base_path=td)
            model.update({"coherence_phi": 0.5})
            summary = model.summary()
            assert "tick" in summary
            assert "developmental_stage" in summary
            assert "identity_vector_length" in summary
            assert "coherence_latest" in summary
            assert "coherence_mean" in summary
            assert "narrative_entries" in summary

    def test_merge_vector_with_different_lengths(self):
        with tempfile.TemporaryDirectory() as td:
            model = SelfModel(base_path=td, identity_vector=[1.0, 2.0])
            model.update({"identity_vector": [3.0, 4.0, 5.0], "coherence_phi": 0.5})
            sig = model.get_identity_signature()
            assert len(sig) == 3

    def test_tick_increments(self):
        with tempfile.TemporaryDirectory() as td:
            model = SelfModel(base_path=td)
            s1 = model.update({"coherence_phi": 0.1})
            s2 = model.update({"coherence_phi": 0.2})
            assert s2.tick == s1.tick + 1

    def test_is_coherent_at_exact_threshold(self):
        with tempfile.TemporaryDirectory() as td:
            model = SelfModel(base_path=td)
            model.update({"coherence_phi": 0.5})
            assert model.is_coherent(threshold=0.5)
