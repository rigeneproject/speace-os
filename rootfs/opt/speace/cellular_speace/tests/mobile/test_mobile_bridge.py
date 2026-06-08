"""Tests for T120 — Mobile Companion Node bridge."""

import time

import pytest

from speace_core.mobile.mobile_bridge import MobilePairingManager, PairedDevice


def test_generate_token():
    mgr = MobilePairingManager()
    token = mgr.generate_token()
    assert len(token) == 6
    assert token.isdigit()


def test_verify_token_success():
    mgr = MobilePairingManager()
    token = mgr.generate_token()
    device = mgr.verify_token(token, "device_001")
    assert device is not None
    assert device.device_id == "device_001"
    assert "dashboard" in device.permissions


def test_verify_token_expired():
    mgr = MobilePairingManager()
    token = mgr.generate_token()
    # Force expiration by manipulating internal state
    mgr._pending_tokens[token] = time.time() - 400
    device = mgr.verify_token(token, "device_001")
    assert device is None


def test_verify_token_invalid():
    mgr = MobilePairingManager()
    device = mgr.verify_token("000000", "device_001")
    assert device is None


def test_heartbeat_and_session_expiry():
    mgr = MobilePairingManager()
    token = mgr.generate_token()
    mgr.verify_token(token, "device_001")
    assert mgr.get_device("device_001") is not None
    # Force session expiry
    mgr._devices["device_001"].last_seen = time.time() - 4000
    assert mgr.get_device("device_001") is None


def test_revoke_device():
    mgr = MobilePairingManager()
    token = mgr.generate_token()
    mgr.verify_token(token, "device_001")
    assert mgr.revoke_device("device_001") is True
    assert mgr.get_device("device_001") is None
    assert mgr.revoke_device("device_001") is False


def test_list_devices():
    mgr = MobilePairingManager()
    t1 = mgr.generate_token()
    t2 = mgr.generate_token()
    mgr.verify_token(t1, "d1")
    mgr.verify_token(t2, "d2")
    devices = mgr.list_devices()
    assert len(devices) == 2


def test_sensor_consent_microphone_always_false():
    mgr = MobilePairingManager()
    token = mgr.generate_token()
    mgr.verify_token(token, "device_001")
    mgr.update_sensor_consent("device_001", {"battery": True, "microphone": True})
    dev = mgr.get_device("device_001")
    assert dev is not None
    assert dev.sensor_consent["battery"] is True
    assert dev.sensor_consent["microphone"] is False


def test_is_authorized():
    mgr = MobilePairingManager()
    token = mgr.generate_token()
    mgr.verify_token(token, "device_001")
    assert mgr.is_authorized("device_001", "dashboard") is True
    assert mgr.is_authorized("device_001", "admin") is False
    assert mgr.is_authorized("unknown", "dashboard") is False
