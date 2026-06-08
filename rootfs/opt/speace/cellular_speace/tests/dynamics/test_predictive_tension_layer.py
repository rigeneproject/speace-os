import numpy as np
import pytest

from speace_core.cellular_brain.dynamics.predictive_coding_engine import PredictiveCodingEngine
from speace_core.cellular_brain.dynamics.predictive_tension_layer import PredictiveTensionLayer


class TestPredictiveTensionLayer:
    def test_tension_increases_with_error(self):
        engine = PredictiveCodingEngine()
        engine.register_layer("sensory", dim=4, level=0)
        engine.register_layer("assoc", dim=4, level=1)
        engine.set_connection("assoc", "sensory")

        tension = PredictiveTensionLayer(decay=0.0)
        # Inject a large prediction error
        engine.layers["sensory"]["prediction_error"] = np.ones(4)
        snap1 = tension.tick(engine)
        assert snap1.total_tension > 0

        # Second tick with same error should accumulate (decay=0)
        snap2 = tension.tick(engine)
        assert snap2.total_tension > snap1.total_tension

    def test_tension_decay(self):
        engine = PredictiveCodingEngine()
        engine.register_layer("sensory", dim=4, level=0)
        engine.layers["sensory"]["prediction_error"] = np.ones(4)

        tension = PredictiveTensionLayer(decay=0.5)
        snap1 = tension.tick(engine)
        # Zero error next tick
        engine.layers["sensory"]["prediction_error"] = np.zeros(4)
        snap2 = tension.tick(engine)
        assert snap2.total_tension < snap1.total_tension

    def test_drive_magnitude_capped(self):
        engine = PredictiveCodingEngine()
        engine.register_layer("sensory", dim=4, level=0)
        engine.layers["sensory"]["prediction_error"] = np.ones(4) * 100.0

        tension = PredictiveTensionLayer(decay=0.0)
        tension.tick(engine)
        assert 0.0 <= tension.get_drive_magnitude() <= 1.0
