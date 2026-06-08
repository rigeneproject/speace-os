from speace_core.cellular_brain.base.digital_signal import DigitalSignal
from speace_core.cellular_brain.cells.digital_synapse import DigitalSynapse


def test_transmit():
    syn = DigitalSynapse(cell_id="s1", role="digital_synapse", source="a", target="b", weight=0.5, trust=0.5)
    sig = DigitalSignal(source="a", target="b", strength=1.0)
    out = syn.transmit(sig)
    assert out.strength == 0.25
    assert syn.use_count == 1


def test_reinforce():
    syn = DigitalSynapse(cell_id="s1", role="digital_synapse", source="a", target="b", weight=0.5, trust=0.5)
    syn.reinforce(1.0)
    assert syn.weight > 0.5
    assert syn.trust > 0.5


def test_weaken():
    syn = DigitalSynapse(cell_id="s1", role="digital_synapse", source="a", target="b", weight=0.5, trust=0.5)
    syn.weaken(1.0)
    assert syn.weight < 0.5
    assert syn.trust < 0.5
