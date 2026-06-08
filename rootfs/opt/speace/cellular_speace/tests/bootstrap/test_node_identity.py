"""Tests for bootstrap node identity manager (T115)."""

import json

import pytest

from speace_core.bootstrap.node_identity import NodeIdentityManager


def test_generate_node_id_format():
    mgr = NodeIdentityManager()
    node_id = mgr.generate_node_id()
    assert node_id.startswith("speace-")
    parts = node_id.split("-")
    assert len(parts) == 3
    assert len(parts[1]) == 16
    assert len(parts[2]) == 8


def test_node_id_uniqueness():
    mgr = NodeIdentityManager()
    ids = {mgr.generate_node_id() for _ in range(100)}
    assert len(ids) == 100


def test_save_and_load(tmp_path):
    mgr = NodeIdentityManager(base_path=tmp_path / "node_id")
    config = mgr.save("speace-test-1234", "0.1.0", paired_nodes=["peer-a"], trust_level=0.5)
    assert config["node_id"] == "speace-test-1234"
    assert config["bootstrap_version"] == "0.1.0"
    assert config["paired_nodes"] == ["peer-a"]
    assert config["trust_level"] == 0.5
    assert config["safe_mode"] is True
    assert config["localhost_only"] is True

    loaded = mgr.load()
    assert loaded is not None
    assert loaded["node_id"] == "speace-test-1234"


def test_ensure_identity_creates_new(tmp_path):
    mgr = NodeIdentityManager(base_path=tmp_path / "node_id")
    config = mgr.ensure_identity(bootstrap_version="0.1.0")
    assert "node_id" in config
    assert config["bootstrap_version"] == "0.1.0"
    assert config["trust_level"] == 0.1


def test_ensure_identity_returns_existing(tmp_path):
    mgr = NodeIdentityManager(base_path=tmp_path / "node_id")
    first = mgr.ensure_identity()
    second = mgr.ensure_identity()
    assert first["node_id"] == second["node_id"]


def test_load_missing_returns_none(tmp_path):
    mgr = NodeIdentityManager(base_path=tmp_path / "node_id")
    assert mgr.load() is None
