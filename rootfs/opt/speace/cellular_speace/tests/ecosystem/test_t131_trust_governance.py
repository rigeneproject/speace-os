"""Tests for T131-C — Trust & Governance."""

import pytest

from speace_core.ecosystem.ecosystem_state import EcosystemSource
from speace_core.ecosystem.trust_governor import TrustGovernor


# ------------------------------------------------------------------ #
# Sandboxing
# ------------------------------------------------------------------ #


def test_validate_sandbox_clean():
    gov = TrustGovernor()
    assert gov.validate_sandbox({"temperature": 22.5}) is True


def test_validate_sandbox_dangerous():
    gov = TrustGovernor()
    assert gov.validate_sandbox("eval(os.system('rm -rf /'))") is False
    assert gov.validate_sandbox("<script>alert('xss')</script>") is False


# ------------------------------------------------------------------ #
# Origin verification
# ------------------------------------------------------------------ #


def test_verify_origin_no_expected():
    gov = TrustGovernor()
    assert gov.verify_origin({"data": 1}, None) is True


def test_verify_origin_match():
    gov = TrustGovernor()
    import hashlib

    payload = "hello"
    expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    assert gov.verify_origin(payload, expected) is True


def test_verify_origin_mismatch():
    gov = TrustGovernor()
    assert gov.verify_origin("hello", "wrong_hash") is False


# ------------------------------------------------------------------ #
# Permission gates
# ------------------------------------------------------------------ #


def test_permission_grant_and_check():
    gov = TrustGovernor()
    gov.grant_permission("s1", "observe")
    assert gov.check_permission("s1", "observe") is True
    assert gov.check_permission("s1", "actuate") is False


def test_permission_revoke():
    gov = TrustGovernor()
    gov.grant_permission("s1", "observe")
    gov.revoke_permission("s1", "observe")
    assert gov.check_permission("s1", "observe") is False


def test_permission_list():
    gov = TrustGovernor()
    gov.grant_permission("s1", "observe")
    gov.grant_permission("s1", "read")
    perms = gov.list_permissions("s1")
    assert set(perms) == {"observe", "read"}


# ------------------------------------------------------------------ #
# Rate limiting
# ------------------------------------------------------------------ #


def test_rate_limit_within_bounds():
    gov = TrustGovernor(rate_limit_window_seconds=60.0, rate_limit_max_requests=5)
    for _ in range(4):
        gov.record_request("s1")
    assert gov.check_rate("s1") is True
    gov.record_request("s1")
    assert gov.check_rate("s1") is False


def test_rate_limit_exceeded():
    gov = TrustGovernor(rate_limit_window_seconds=60.0, rate_limit_max_requests=2)
    gov.record_request("s1")
    gov.record_request("s1")
    gov.record_request("s1")
    assert gov.check_rate("s1") is False


def test_rate_status():
    gov = TrustGovernor(rate_limit_window_seconds=60.0, rate_limit_max_requests=10)
    gov.record_request("s1")
    status = gov.rate_status("s1")
    assert status["current_requests"] == 1
    assert status["remaining"] == 9


# ------------------------------------------------------------------ #
# Identity validation
# ------------------------------------------------------------------ #


def test_identity_register_and_validate():
    gov = TrustGovernor()
    gov.register_identity("s1", "token_abc")
    assert gov.validate_identity("s1", "token_abc") is True
    assert gov.validate_identity("s1", "wrong") is False


def test_identity_has_identity():
    gov = TrustGovernor()
    assert gov.has_identity("s1") is False
    gov.register_identity("s1", "token")
    assert gov.has_identity("s1") is True


# ------------------------------------------------------------------ #
# Integration: observation layer uses T131-C
# ------------------------------------------------------------------ #


def test_layer_describe_includes_governance(tmp_path):
    from speace_core.ecosystem.observation_layer import EcosystemObservationLayer

    layer = EcosystemObservationLayer(data_root=str(tmp_path / "eco_c"))
    layer._registry.register(
        EcosystemSource(source_id="s1", source_type="iot_sensor", uri="/tmp/a.json")
    )
    layer._trust_governor.grant_permission("s1", "observe")
    layer._trust_governor.register_identity("s1", "tok")
    detail = layer.describe_source("s1")
    assert detail is not None
    assert "rate_limit" in detail
    assert "permissions" in detail
    assert detail["has_identity"] is True
    assert "observe" in detail["permissions"]


def test_layer_rate_limit_blocks(tmp_path):
    from speace_core.ecosystem.observation_layer import EcosystemObservationLayer
    from speace_core.ecosystem.ecosystem_state import EcosystemSource

    layer = EcosystemObservationLayer(
        data_root=str(tmp_path / "eco_c2"),
        poll_interval_seconds=3600,
    )
    layer._registry.register(
        EcosystemSource(source_id="s1", source_type="file", uri="/tmp/a.json")
    )
    # Force rate limit exceeded: set max=0 and pre-record one request
    layer._trust_governor.rate_limit_max = 0
    layer._trust_governor.record_request("s1")
    import asyncio

    asyncio.run(layer._observe_source(layer._registry.get("s1")))
    # Check that the observation was blocked
    recent = layer._recent_observations("s1", limit=2)
    blocked = [r for r in recent if r.get("status") == "blocked"]
    assert len(blocked) == 1
    assert blocked[0]["raw_payload"]["_blocked_reason"] == "rate_limit_exceeded"
