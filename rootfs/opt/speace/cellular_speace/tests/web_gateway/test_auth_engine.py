"""Tests for T121 + T125 — SPEACE Secure Web Gateway auth engine."""

import json

from speace_core.web_gateway.auth_engine import AuthEngine


def _make_auth():
    return AuthEngine(data_root="data/test_web_gateway")


def test_generate_and_validate_key():
    auth = _make_auth()
    key = auth.generate_key(role="observer")
    assert len(key) > 0
    assert auth.is_valid(key) is True
    assert auth.is_valid("invalid_key") is False
    assert auth.get_role(key) == "observer"


def test_generate_key_with_role():
    auth = _make_auth()
    key = auth.generate_key(role="reviewer")
    assert auth.get_role(key) == "reviewer"


def test_generate_key_invalid_role_raises():
    auth = _make_auth()
    try:
        auth.generate_key(role="hacker")
        assert False, "should have raised"
    except ValueError as e:
        assert "hacker" in str(e)


def test_revoke_key():
    auth = _make_auth()
    key = auth.generate_key()
    assert auth.revoke_key(key) is True
    assert auth.is_valid(key) is False
    assert auth.revoke_key(key) is False


def test_list_keys():
    auth = _make_auth()
    k1 = auth.generate_key(role="observer")
    k2 = auth.generate_key(role="admin")
    keys = auth.list_keys()
    assert len(keys) >= 2
    roles = {k["role"] for k in keys}
    assert "observer" in roles
    assert "admin" in roles
    # key_preview should be redacted
    assert "..." in keys[0]["key_preview"]
    assert keys[0]["key_preview"] != k1


def test_rate_limit():
    auth = _make_auth()
    key = auth.generate_key()
    # 60 requests allowed in window
    for _ in range(60):
        assert auth.check_rate_limit(key) is True
    # 61st should fail
    assert auth.check_rate_limit(key) is False


def test_audit_log_includes_role_and_user_id():
    auth = _make_auth()
    key = auth.generate_key(role="operator")
    auth.audit(key, "/api/state", "GET", 200, "127.0.0.1")
    assert auth._audit_path.exists()
    lines = auth._audit_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) >= 1
    record = json.loads(lines[-1])
    assert record["endpoint"] == "/api/state"
    assert record["status"] == 200
    assert record["role"] == "operator"
    assert record["user_id"] == key
    assert "key_preview" in record
