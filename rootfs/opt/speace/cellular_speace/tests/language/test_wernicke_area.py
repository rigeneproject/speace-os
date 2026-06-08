import pytest

from speace_core.cellular_brain.language.wernicke_area import DigitalWernickeArea, SemanticAssembly


@pytest.fixture
def vocab():
    return {
        "cat": [0.9, 0.1, 0.0],
        "dog": [0.1, 0.9, 0.0],
        "runs": [0.5, 0.5, 0.8],
    }


@pytest.fixture
def wernicke(vocab):
    return DigitalWernickeArea(vocab=vocab, coherence_threshold=0.3, decay_rate=0.05)


def test_receive_tokens_populates_buffer(wernicke):
    wernicke.receive_tokens(["cat", "runs"])
    assert wernicke.token_buffer == ["cat", "runs"]


def test_receive_tokens_unknown_token_gets_novelty_activation(wernicke):
    wernicke.receive_tokens(["xyz"])
    activation = wernicke.get_semantic_activation()
    assert "xyz" in activation
    assert activation["xyz"] > 0.0


def test_decode_to_assembly_known_tokens(wernicke):
    wernicke.receive_tokens(["cat", "runs"])
    assembly = wernicke.decode_to_assembly()
    assert isinstance(assembly, SemanticAssembly)
    assert assembly.tokens == ["cat", "runs"]
    assert len(assembly.activation_vector) == 3
    assert assembly.dominant_concept in ("cat", "runs")


def test_decode_to_assembly_unknown_tokens(wernicke):
    wernicke.receive_tokens(["qwerty"])
    assembly = wernicke.decode_to_assembly()
    assert assembly.dominant_concept == "qwerty"
    assert assembly.coherence == 0.0


def test_decode_to_assembly_empty_buffer(wernicke):
    assembly = wernicke.decode_to_assembly()
    assert assembly.tokens == []
    assert assembly.activation_vector == []
    assert assembly.dominant_concept == ""


def test_semantic_activation_decays(wernicke):
    wernicke.receive_tokens(["cat"])
    before = wernicke.get_semantic_activation()["cat"]
    # decay happens on every call to get_semantic_activation
    after = wernicke.get_semantic_activation().get("cat", 0.0)
    assert after < before


def test_semantic_activation_drops_zero_keys(wernicke):
    wernicke.receive_tokens(["cat"])
    # decay repeatedly until gone
    for _ in range(100):
        wernicke.get_semantic_activation()
    assert "cat" not in wernicke.get_semantic_activation()


def test_clear_buffer_empties_tokens(wernicke):
    wernicke.receive_tokens(["dog"])
    wernicke.clear_buffer()
    assert wernicke.token_buffer == []
    # semantic map is retained
    assert "dog" in wernicke.get_semantic_activation()


def test_reset_clears_everything(wernicke):
    wernicke.receive_tokens(["cat", "dog"])
    wernicke.decode_to_assembly()
    wernicke.reset()
    assert wernicke.token_buffer == []
    assert wernicke.get_semantic_activation() == {}
    assert wernicke.assembly_history == []


def test_assembly_history_tracks_multiple_decodes(wernicke):
    wernicke.receive_tokens(["cat"])
    wernicke.decode_to_assembly()
    wernicke.receive_tokens(["dog"])
    wernicke.decode_to_assembly()
    assert len(wernicke.assembly_history) == 2


def test_known_tokens_property(wernicke, vocab):
    assert wernicke.known_tokens() == set(vocab.keys())


def test_receive_tokens_extends_buffer(wernicke):
    wernicke.receive_tokens(["cat"])
    wernicke.receive_tokens(["dog", "runs"])
    assert wernicke.token_buffer == ["cat", "dog", "runs"]
