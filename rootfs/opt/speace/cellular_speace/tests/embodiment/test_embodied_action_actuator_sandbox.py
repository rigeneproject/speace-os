"""Tests for the sandbox-profile extension of EmbodiedActionActuator.

These tests cover the opt-in sandbox behaviour introduced in Stage 2.5. They
verify that:

  - the default constructor still behaves exactly as before (no sandbox).
  - a sandbox_profile name alone is NOT enough; SPEACE_SANDBOX=1 is required.
  - when both are present, the profile extends (never replaces) the standard
    guardrails.
  - dangerous actions and standard blocked fragments still work as before
    even when the sandbox is active.
  - missing sandbox_profile.yaml fails gracefully and keeps the standard
    guardrails.
  - every action emits a record into data/sandbox/audit.jsonl.

All filesystem side-effects are routed to ``tmp_path`` (the pytest fixture)
so that the project's working tree is never touched.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Optional

import pytest
import yaml  # type: ignore

from speace_core.cellular_brain.embodiment.embodied_action_actuator import (
    EmbodiedActionActuator,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _make_project_root(tmp_path: Path) -> Path:
    """Create a minimal project root that satisfies the standard guardrails.

    The standard ALLOWED_SUBDIRS are ``data``, ``reports``, ``logs`` and
    ``temp``.  We pre-create them so that file actions can succeed.
    """
    root = tmp_path / "project"
    root.mkdir()
    for sub in ("data", "reports", "logs", "temp"):
        (root / sub).mkdir()
    return root


def _write_sandbox_profile(
    project_root: Path,
    *,
    additional_allowed_subdirs: Optional[list] = None,
    additional_allowed_cmd_patterns: Optional[list] = None,
    always_blocked_fragments: Optional[list] = None,
) -> Path:
    """Write a minimal but valid ``sandbox/sandbox_profile.yaml`` for tests.

    The structure mirrors the one that Punto 2 of the plan will create. Only
    the keys the actuator actually reads are populated.
    """
    sandbox_dir = project_root / "sandbox"
    sandbox_dir.mkdir(parents=True, exist_ok=True)
    profile = {
        "name": "lab_sandbox",
        "description": "Test-only sandbox profile.",
        "extended_capabilities": {
            "actuator": {
                "additional_allowed_subdirs": list(
                    additional_allowed_subdirs or []
                ),
                "additional_allowed_cmd_patterns": list(
                    additional_allowed_cmd_patterns or []
                ),
                "always_blocked_fragments": list(
                    always_blocked_fragments or []
                ),
            }
        },
    }
    profile_path = sandbox_dir / "sandbox_profile.yaml"
    profile_path.write_text(
        yaml.safe_dump(profile, sort_keys=False), encoding="utf-8"
    )
    return profile_path


# --------------------------------------------------------------------------- #
# Default behaviour (no sandbox)
# --------------------------------------------------------------------------- #


class TestDefaultNoSandbox:
    def test_default_no_sandbox(self, tmp_path, monkeypatch):
        """No sandbox_profile passed -> sandbox_active False, default caps."""
        monkeypatch.delenv("SPEACE_SANDBOX", raising=False)
        root = _make_project_root(tmp_path)

        act = EmbodiedActionActuator(project_root=root)

        assert act.sandbox_active is False
        # Standard ALLOWED_SUBDIRS must be intact.
        assert act.ALLOWED_SUBDIRS == {"data", "reports", "logs", "temp"}
        # Standard BLOCKED fragments are still loaded.
        assert "rm" in act.BLOCKED_CMD_FRAGMENTS
        # No additional sandbox state.
        assert act._allowed_subdirs_sandbox == set()
        assert act._allowed_cmd_patterns_sandbox == []
        assert act._always_blocked_fragments == set()

    def test_empty_string_sandbox_profile_is_ignored(self, tmp_path, monkeypatch):
        """An empty sandbox_profile string is treated like ``None``."""
        monkeypatch.setenv("SPEACE_SANDBOX", "1")
        root = _make_project_root(tmp_path)
        act = EmbodiedActionActuator(project_root=root, sandbox_profile="")
        assert act.sandbox_active is False


# --------------------------------------------------------------------------- #
# Activation conditions
# --------------------------------------------------------------------------- #


class TestSandboxActivation:
    def test_sandbox_requires_env_var(self, tmp_path, monkeypatch):
        """sandbox_profile name alone is not enough without SPEACE_SANDBOX=1."""
        monkeypatch.delenv("SPEACE_SANDBOX", raising=False)
        root = _make_project_root(tmp_path)
        _write_sandbox_profile(
            root,
            additional_allowed_subdirs=["lab_data"],
            additional_allowed_cmd_patterns=[r"^ls\s*"],
        )

        act = EmbodiedActionActuator(project_root=root, sandbox_profile="lab_sandbox")

        # Without the env var the profile is ignored.
        assert act.sandbox_active is False
        assert act._allowed_subdirs_sandbox == set()
        assert act._allowed_cmd_patterns_sandbox == []
        # An activation record was still written, but as ``sandbox_ignored``.
        activations_path = root / "data" / "sandbox" / "activations.jsonl"
        assert activations_path.exists()
        records = [
            json.loads(line)
            for line in activations_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert any(r["event"] == "sandbox_ignored" for r in records)

    def test_sandbox_activated_with_env(self, tmp_path, monkeypatch):
        """sandbox_profile + SPEACE_SANDBOX=1 -> sandbox_active is True."""
        monkeypatch.setenv("SPEACE_SANDBOX", "1")
        root = _make_project_root(tmp_path)
        _write_sandbox_profile(
            root,
            additional_allowed_subdirs=["lab_data"],
            additional_allowed_cmd_patterns=[r"^ls\s*"],
        )

        act = EmbodiedActionActuator(project_root=root, sandbox_profile="lab_sandbox")

        assert act.sandbox_active is True
        assert "lab_data" in act._allowed_subdirs_sandbox
        assert act._allowed_cmd_patterns_sandbox == [r"^ls\s*"]

        # An ``sandbox_activated`` record is written to activations.jsonl.
        activations_path = root / "data" / "sandbox" / "activations.jsonl"
        records = [
            json.loads(line)
            for line in activations_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        activated = [r for r in records if r["event"] == "sandbox_activated"]
        assert len(activated) == 1
        assert activated[0]["profile"] == "lab_sandbox"
        assert "timestamp" in activated[0]
        assert "in_container" in activated[0]

    def test_env_var_without_profile_is_logged_and_ignored(
        self, tmp_path, monkeypatch
    ):
        """SPEACE_SANDBOX=1 with no profile name -> ignored."""
        monkeypatch.setenv("SPEACE_SANDBOX", "1")
        root = _make_project_root(tmp_path)

        act = EmbodiedActionActuator(project_root=root)

        assert act.sandbox_active is False
        activations_path = root / "data" / "sandbox" / "activations.jsonl"
        assert activations_path.exists()
        records = [
            json.loads(line)
            for line in activations_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert any(r["event"] == "sandbox_no_profile_specified" for r in records)


# --------------------------------------------------------------------------- #
# Guardrails still apply with sandbox active
# --------------------------------------------------------------------------- #


class TestSandboxGuardrails:
    def test_sandbox_blocked_fragments_always_blocked(self, tmp_path, monkeypatch):
        """``rm -rf /`` is blocked even when the sandbox is active."""
        monkeypatch.setenv("SPEACE_SANDBOX", "1")
        root = _make_project_root(tmp_path)
        _write_sandbox_profile(
            root,
            additional_allowed_subdirs=["lab_data"],
            additional_allowed_cmd_patterns=[r"^ls\s*", r"^cat\s+"],
        )
        act = EmbodiedActionActuator(
            project_root=root, sandbox_profile="lab_sandbox"
        )
        assert act.sandbox_active is True

        res = act.execute_action(
            "execute_command",
            {"cmd": "rm -rf /"},
            approval_level="human_review",
        )
        assert res["success"] is False
        assert "command_blocked_by_safety_policy" in res["error"]

    def test_sandbox_extends_patterns_not_replaces(
        self, tmp_path, monkeypatch
    ):
        """Sandbox adds patterns; the standard ones are still accepted."""
        monkeypatch.setenv("SPEACE_SANDBOX", "1")
        root = _make_project_root(tmp_path)
        _write_sandbox_profile(
            root,
            additional_allowed_subdirs=["lab_data"],
            # Add an extra pattern that was not in the standard set.
            additional_allowed_cmd_patterns=[r"^ls\s*"],
        )
        act = EmbodiedActionActuator(
            project_root=root, sandbox_profile="lab_sandbox"
        )
        assert act.sandbox_active is True

        # Sandbox-only pattern works.
        res_ls = act.execute_action(
            "execute_command",
            {"cmd": "ls"},
            approval_level="human_review",
        )
        assert res_ls["success"] is True, res_ls

        # Standard pattern still works.
        res_cat = act.execute_action(
            "execute_command",
            {"cmd": "cat data/test.txt"},
            approval_level="human_review",
        )
        assert res_cat["success"] is True, res_cat

    def test_sandbox_does_not_remove_existing_guards(self, tmp_path, monkeypatch):
        """delete_file still requires human_review with sandbox active."""
        monkeypatch.setenv("SPEACE_SANDBOX", "1")
        root = _make_project_root(tmp_path)
        # Pre-create the file to delete.
        target = root / "data" / "to_delete.txt"
        target.write_text("bye", encoding="utf-8")
        _write_sandbox_profile(
            root,
            additional_allowed_subdirs=["lab_data"],
            additional_allowed_cmd_patterns=[r"^ls\s*"],
        )
        act = EmbodiedActionActuator(
            project_root=root, sandbox_profile="lab_sandbox"
        )
        assert act.sandbox_active is True

        # Without human_review, delete_file is still blocked.
        res = act.execute_action("delete_file", {"path": str(target)})
        assert res["success"] is False
        assert "dangerous_action_requires_human_review" in res["error"]
        # And the file is still there.
        assert target.exists()

        # With human_review, it succeeds.
        res2 = act.execute_action(
            "delete_file",
            {"path": str(target)},
            approval_level="human_review",
        )
        assert res2["success"] is True
        assert not target.exists()

    def test_sandbox_always_blocked_fragments_block_even_in_sandbox(
        self, tmp_path, monkeypatch
    ):
        """A fragment in ``always_blocked_fragments`` is blocked in sandbox."""
        monkeypatch.setenv("SPEACE_SANDBOX", "1")
        root = _make_project_root(tmp_path)
        _write_sandbox_profile(
            root,
            additional_allowed_subdirs=["lab_data"],
            additional_allowed_cmd_patterns=[r"^ls\s*"],
            # Note: "wget" is not in the standard BLOCKED_CMD_FRAGMENTS,
            # so without the sandbox always-blocked list it would be allowed.
            always_blocked_fragments=["wget"],
        )
        act = EmbodiedActionActuator(
            project_root=root, sandbox_profile="lab_sandbox"
        )
        assert act.sandbox_active is True

        res = act.execute_action(
            "execute_command",
            {"cmd": "wget http://example.com"},
            approval_level="human_review",
        )
        assert res["success"] is False
        assert "command_blocked_by_safety_policy" in res["error"]


# --------------------------------------------------------------------------- #
# Missing-profile fallback
# --------------------------------------------------------------------------- #


class TestMissingProfile:
    def test_sandbox_missing_profile_file(self, tmp_path, monkeypatch):
        """Missing sandbox_profile.yaml -> graceful fallback, no activation."""
        monkeypatch.setenv("SPEACE_SANDBOX", "1")
        root = _make_project_root(tmp_path)
        # NOTE: we deliberately do NOT create sandbox/sandbox_profile.yaml.
        assert not (root / "sandbox" / "sandbox_profile.yaml").exists()

        act = EmbodiedActionActuator(
            project_root=root, sandbox_profile="lab_sandbox"
        )

        # Sandbox is NOT active.
        assert act.sandbox_active is False
        # The standard caps are still in place.
        assert act.ALLOWED_SUBDIRS == {"data", "reports", "logs", "temp"}
        assert "rm" in act.BLOCKED_CMD_FRAGMENTS

        # An activation record was written as ``sandbox_profile_missing``.
        activations_path = root / "data" / "sandbox" / "activations.jsonl"
        records = [
            json.loads(line)
            for line in activations_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert any(r["event"] == "sandbox_profile_missing" for r in records)

        # And a blocked command is still blocked.
        res = act.execute_action(
            "execute_command",
            {"cmd": "rm -rf /"},
            approval_level="human_review",
        )
        assert res["success"] is False


# --------------------------------------------------------------------------- #
# Audit log
# --------------------------------------------------------------------------- #


class TestAuditLog:
    def test_audit_log_written_on_propose(self, tmp_path, monkeypatch):
        """``propose_action`` writes a record into audit.jsonl."""
        monkeypatch.delenv("SPEACE_SANDBOX", raising=False)
        root = _make_project_root(tmp_path)
        act = EmbodiedActionActuator(project_root=root)
        # Sandbox is inactive -> no audit file is required to exist, but
        # propose_action still emits a record (best-effort, always-on).
        pid = act.propose_action(
            "read_file", {"path": str(root / "data" / "x.txt")}
        )
        assert pid.startswith("prop_")

        audit_path = root / "data" / "sandbox" / "audit.jsonl"
        assert audit_path.exists()
        records = [
            json.loads(line)
            for line in audit_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert any(
            r.get("action_id") == pid
            and r.get("action_type") == "read_file"
            and r.get("phase") == "propose"
            for r in records
        )
        # Sandbox is inactive so the record carries ``sandbox_active=False``.
        match = next(r for r in records if r.get("action_id") == pid)
        assert match["sandbox_active"] is False

    def test_audit_log_written_on_execute(self, tmp_path, monkeypatch):
        """``execute_action`` writes a record into audit.jsonl."""
        monkeypatch.setenv("SPEACE_SANDBOX", "1")
        root = _make_project_root(tmp_path)
        _write_sandbox_profile(
            root,
            additional_allowed_subdirs=["lab_data"],
        )
        act = EmbodiedActionActuator(
            project_root=root, sandbox_profile="lab_sandbox"
        )
        assert act.sandbox_active is True

        res = act.execute_action(
            "write_text_file",
            {"path": str(root / "data" / "audit_target.txt"), "content": "ok"},
        )
        assert res["success"] is True

        audit_path = root / "data" / "sandbox" / "audit.jsonl"
        assert audit_path.exists()
        records = [
            json.loads(line)
            for line in audit_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        match = next(
            (
                r
                for r in records
                if r.get("action_type") == "write_text_file"
                and r.get("phase") == "execute"
            ),
            None,
        )
        assert match is not None
        # sandbox_active is True and the file content is NOT in the audit log.
        assert match["sandbox_active"] is True
        assert "content" not in match.get("params", {})
        assert "path" in match.get("params", {})

    def test_audit_log_written_on_revert(self, tmp_path, monkeypatch):
        """``revert_last_action`` writes a record into audit.jsonl."""
        monkeypatch.delenv("SPEACE_SANDBOX", raising=False)
        root = _make_project_root(tmp_path)
        act = EmbodiedActionActuator(project_root=root)
        path = str(root / "data" / "to_revert.txt")
        act.execute_action("write_text_file", {"path": path, "content": "v1"})
        rev = act.revert_last_action()
        assert rev["success"] is True

        audit_path = root / "data" / "sandbox" / "audit.jsonl"
        assert audit_path.exists()
        records = [
            json.loads(line)
            for line in audit_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert any(
            r.get("phase") == "revert" and r.get("outcome") == "reverted"
            for r in records
        )

    def test_audit_log_does_not_leak_file_content(self, tmp_path, monkeypatch):
        """The audit record must never persist the file body."""
        monkeypatch.delenv("SPEACE_SANDBOX", raising=False)
        root = _make_project_root(tmp_path)
        act = EmbodiedActionActuator(project_root=root)
        secret = "TOP_SECRET_TOKEN_42"
        act.execute_action(
            "write_text_file",
            {
                "path": str(root / "data" / "secret.txt"),
                "content": secret,
            },
        )

        audit_path = root / "data" / "sandbox" / "audit.jsonl"
        raw = audit_path.read_text(encoding="utf-8")
        assert secret not in raw
        for line in raw.splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            assert "content" not in rec.get("params", {})


# --------------------------------------------------------------------------- #
# Path-extension via sandbox subdirs
# --------------------------------------------------------------------------- #


class TestSandboxExtendsSubdirs:
    def test_sandbox_additional_subdir_is_accepted(self, tmp_path, monkeypatch):
        """A subdir in ``additional_allowed_subdirs`` becomes allowed in sandbox."""
        monkeypatch.setenv("SPEACE_SANDBOX", "1")
        root = _make_project_root(tmp_path)
        (root / "lab_data").mkdir()
        _write_sandbox_profile(
            root,
            additional_allowed_subdirs=["lab_data"],
        )
        act = EmbodiedActionActuator(
            project_root=root, sandbox_profile="lab_sandbox"
        )
        assert act.sandbox_active is True

        # Writing inside lab_data must be allowed.
        target = root / "lab_data" / "experiment.txt"
        res = act.execute_action(
            "write_text_file",
            {"path": str(target), "content": "hello"},
        )
        assert res["success"] is True
        assert target.read_text(encoding="utf-8") == "hello"

    def test_sandbox_inactive_keeps_standard_subdirs_only(
        self, tmp_path, monkeypatch
    ):
        """When the sandbox is not active, lab_data stays blocked."""
        monkeypatch.delenv("SPEACE_SANDBOX", raising=False)
        root = _make_project_root(tmp_path)
        (root / "lab_data").mkdir()
        _write_sandbox_profile(
            root,
            additional_allowed_subdirs=["lab_data"],
        )
        act = EmbodiedActionActuator(project_root=root)
        assert act.sandbox_active is False

        target = root / "lab_data" / "experiment.txt"
        res = act.execute_action(
            "write_text_file",
            {"path": str(target), "content": "hello"},
        )
        assert res["success"] is False
        assert "path_outside_allowed_directories" in res["error"]


# --------------------------------------------------------------------------- #
# Property and introspection
# --------------------------------------------------------------------------- #


class TestPublicIntrospection:
    def test_sandbox_active_property_reflects_state(self, tmp_path, monkeypatch):
        """``sandbox_active`` is a read-only property bound to internal state."""
        monkeypatch.delenv("SPEACE_SANDBOX", raising=False)
        root = _make_project_root(tmp_path)
        act = EmbodiedActionActuator(project_root=root)
        assert act.sandbox_active is False
        # Mutate the internal flag and confirm the property follows.
        act._sandbox_active = True
        assert act.sandbox_active is True
