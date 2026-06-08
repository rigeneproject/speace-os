"""Tests for bootstrap seed engine (T115)."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from speace_core.bootstrap import SeedEngine
from speace_core.bootstrap.verifier import HashAllowlist


def test_verify_environment_ok():
    engine = SeedEngine()
    env = engine.verify_environment()
    assert env["ok"] is True
    assert env["python_version"]
    assert env["git_path"] is not None
    assert env["pip_path"] is not None


def test_verify_environment_missing_git(monkeypatch):
    monkeypatch.setattr(SeedEngine, "_which", lambda _, cmd: None)
    engine = SeedEngine()
    env = engine.verify_environment()
    assert env["ok"] is False
    assert any("git" in e for e in env["errors"])


def test_repo_not_in_allowlist():
    allowlist = HashAllowlist()
    allowlist._entries = {}  # empty
    engine = SeedEngine(repo="https://github.com/other/repo", allowlist=allowlist)
    with pytest.raises(RuntimeError, match="not in the allowlist"):
        engine.download_repo()


def test_download_repo_target_exists(tmp_path):
    allowlist = HashAllowlist()
    allowlist.add_hash("https://github.com/rigeneproject/cellular_speace", "abc")
    engine = SeedEngine(
        repo="https://github.com/rigeneproject/cellular_speace",
        target_dir=tmp_path,
        allowlist=allowlist,
    )
    (tmp_path / "cellular_speace").mkdir()
    with pytest.raises(RuntimeError, match="already exists"):
        engine.download_repo()


def test_verify_package_empty_allowlist_auto_approves(tmp_path):
    allowlist = HashAllowlist()
    # allowlist has repo but no hashes
    engine = SeedEngine(
        repo="https://github.com/rigeneproject/cellular_speace",
        allowlist=allowlist,
    )
    # Mock git repo with a fake commit
    fake_git = tmp_path / "cellular_speace" / ".git"
    fake_git.mkdir(parents=True)
    with patch.object(
        engine, "get_commit_hash", return_value="deadbeef"
    ):
        assert engine.verify_package(tmp_path / "cellular_speace") is True
        # hash should now be auto-approved
        assert allowlist.is_approved(
            "https://github.com/rigeneproject/cellular_speace", "deadbeef"
        )


def test_verify_package_hash_mismatch(tmp_path):
    allowlist = HashAllowlist()
    allowlist.add_hash("https://github.com/rigeneproject/cellular_speace", "abc123")
    engine = SeedEngine(
        repo="https://github.com/rigeneproject/cellular_speace",
        allowlist=allowlist,
    )
    with patch.object(
        engine, "get_commit_hash", return_value="def456"
    ):
        with pytest.raises(RuntimeError, match="Hash verification failed"):
            engine.verify_package(tmp_path / "cellular_speace")


def test_generate_node_identity(tmp_path):
    engine = SeedEngine(target_dir=tmp_path)
    identity = engine.generate_node_identity()
    assert identity["node_id"].startswith("speace-")
    assert identity["bootstrap_version"] == "0.1.0"


def test_bootstrap_user_decline(tmp_path, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "n")
    engine = SeedEngine(target_dir=tmp_path)
    result = engine.bootstrap(skip_confirm=False)
    assert result["status"] == "aborted"
    assert result["reason"] == "user_declined"


def test_bootstrap_skip_confirm_missing_deps(tmp_path, monkeypatch):
    monkeypatch.setattr(SeedEngine, "_which", lambda _, cmd: None)
    engine = SeedEngine(target_dir=tmp_path)
    result = engine.bootstrap(skip_confirm=True)
    assert result["status"] == "failed"
    assert result["stage"] == "environment"


def test_generate_pairing_token(tmp_path):
    engine = SeedEngine(target_dir=tmp_path)
    identity = engine.generate_node_identity()
    token = engine.generate_pairing_token(identity, "target-node")
    assert isinstance(token, str)
    assert len(token) > 0


def test_verify_pairing_token_valid(tmp_path):
    engine = SeedEngine(target_dir=tmp_path)
    identity = engine.generate_node_identity()
    token = engine.generate_pairing_token(identity, "target-node")
    engine.pairing_token_str = token
    result = engine.verify_pairing_token({"node_id": "target-node"})
    assert result is not None
    assert result["source_node"] == identity["node_id"]


def test_verify_pairing_token_invalid(tmp_path):
    engine = SeedEngine(target_dir=tmp_path)
    engine.pairing_token_str = "bad-token"
    with pytest.raises(RuntimeError, match="Invalid pairing token"):
        engine.verify_pairing_token({"node_id": "target-node"})
