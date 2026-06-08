"""Tests for bootstrap pairing token system (T115)."""

import time

import pytest

from speace_core.bootstrap.pairing_token import PairingToken


def test_generate_and_verify():
    engine = PairingToken()
    token = engine.generate("node-a", "node-b", expiry_hours=24)
    assert isinstance(token, str)
    assert len(token) > 0

    payload = engine.verify(token, expected_target_node="node-b")
    assert payload["source_node"] == "node-a"
    assert payload["target_node"] == "node-b"


def test_verify_wrong_target():
    engine = PairingToken()
    token = engine.generate("node-a", "node-b")
    with pytest.raises(ValueError, match="not valid for this node"):
        engine.verify(token, expected_target_node="node-c")


def test_verify_expired_token():
    engine = PairingToken()
    # Generate a token that expires immediately
    token = engine.generate("node-a", "node-b", expiry_hours=0)
    # Sleep a tiny bit to ensure expiry
    time.sleep(0.1)
    with pytest.raises(ValueError, match="expired"):
        engine.verify(token, expected_target_node="node-b")


def test_verify_no_dot_malformed():
    engine = PairingToken()
    with pytest.raises(ValueError, match="Malformed"):
        engine.verify("not-a-valid-token")


def test_verify_invalid_encoding():
    engine = PairingToken()
    # token with a dot but invalid base64 parts
    with pytest.raises(ValueError, match="encoding"):
        engine.verify("not-valid.!!!")


def test_verify_malformed_token():
    engine = PairingToken()
    import base64

    # single base64 part without dot
    bad = base64.urlsafe_b64encode(b"nodotsignature").decode().rstrip("=")
    with pytest.raises(ValueError, match="Malformed"):
        engine.verify(bad)


def test_list_tokens(tmp_path):
    engine = PairingToken(base_path=tmp_path / "tokens")
    tokens_before = engine.list_tokens()
    assert tokens_before == []

    engine.generate("node-a", "node-b")
    tokens_after = engine.list_tokens()
    assert len(tokens_after) == 1
    assert tokens_after[0]["source_node"] == "node-a"
    assert tokens_after[0]["target_node"] == "node-b"


def test_token_signature_uniqueness():
    engine = PairingToken()
    t1 = engine.generate("node-a", "node-b")
    t2 = engine.generate("node-a", "node-b")
    assert t1 != t2
