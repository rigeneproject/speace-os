import os
import time

import pytest

from speace_core.cellular_brain.embodiment.embodied_action_actuator import (
    ActionOutcome,
    EmbodiedActionActuator,
)


class TestEmbodiedActionActuator:
    @pytest.fixture
    def actuator(self, tmp_path):
        # Override project_root to a temp directory so we can test safely
        root = tmp_path / "project"
        root.mkdir()
        for sub in ("data", "reports", "logs", "temp"):
            (root / sub).mkdir()
        return EmbodiedActionActuator(project_root=root)

    # ------------------------------------------------------------------ #
    # Safe file operations
    # ------------------------------------------------------------------ #

    def test_safe_file_write_and_read(self, actuator):
        path = os.path.join(str(actuator.project_root), "data", "test_write.txt")
        res = actuator.execute_action(
            "write_text_file",
            {"path": path, "content": "hello speace"},
        )
        assert res["success"] is True
        assert res["result"]["bytes_written"] == 12

        res_read = actuator.execute_action(
            "read_file",
            {"path": path},
        )
        assert res_read["success"] is True
        assert res_read["result"]["content"] == "hello speace"

    def test_write_text_file_creates_parents(self, actuator):
        path = os.path.join(str(actuator.project_root), "data", "nested", "file.txt")
        res = actuator.execute_action(
            "write_text_file",
            {"path": path, "content": "nested"},
        )
        assert res["success"] is True
        assert os.path.exists(path)

    def test_write_text_file_max_1mb(self, actuator):
        path = os.path.join(str(actuator.project_root), "data", "big.txt")
        big_content = "x" * (1_048_576 + 1)
        res = actuator.execute_action(
            "write_text_file",
            {"path": path, "content": big_content},
        )
        assert res["success"] is False
        assert "content_exceeds_1mb" in res["error"]

    # ------------------------------------------------------------------ #
    # Directory operations
    # ------------------------------------------------------------------ #

    def test_create_directory(self, actuator):
        path = os.path.join(str(actuator.project_root), "temp", "new_dir")
        res = actuator.execute_action(
            "create_directory",
            {"path": path},
        )
        assert res["success"] is True
        assert os.path.isdir(path)

    def test_list_directory(self, actuator):
        data_dir = os.path.join(str(actuator.project_root), "data")
        # create a couple of files
        open(os.path.join(data_dir, "a.txt"), "w").close()
        open(os.path.join(data_dir, "b.txt"), "w").close()
        res = actuator.execute_action(
            "list_directory",
            {"path": data_dir},
        )
        assert res["success"] is True
        assert "a.txt" in res["result"]["entries"]
        assert "b.txt" in res["result"]["entries"]

    # ------------------------------------------------------------------ #
    # Command execution safety
    # ------------------------------------------------------------------ #

    def test_blocked_dangerous_command(self, actuator):
        res = actuator.execute_action(
            "execute_command",
            {"cmd": "rm -rf /"},
        )
        assert res["success"] is False
        assert "command_blocked_by_safety_policy" in res["error"]

    def test_blocked_command_with_del(self, actuator):
        res = actuator.execute_action(
            "execute_command",
            {"cmd": "del important.txt"},
        )
        assert res["success"] is False
        assert "command_blocked_by_safety_policy" in res["error"]

    def test_blocked_powershell_command(self, actuator):
        res = actuator.execute_action(
            "execute_command",
            {"cmd": 'powershell -Command "Remove-Item foo.txt"'},
        )
        assert res["success"] is False
        assert "command_blocked_by_safety_policy" in res["error"]

    def test_allowed_echo_command(self, actuator):
        res = actuator.execute_action(
            "execute_command",
            {"cmd": "echo hello"},
            approval_level="human_review",
        )
        assert res["success"] is True
        assert "hello" in res["result"]["stdout"].lower()

    def test_allowed_dir_command(self, actuator):
        res = actuator.execute_action(
            "execute_command",
            {"cmd": "dir"},
            approval_level="human_review",
        )
        assert res["success"] is True

    def test_execute_command_timeout(self, actuator):
        # A command that sleeps longer than timeout should fail
        res = actuator.execute_action(
            "execute_command",
            {"cmd": "python -c \"import time; time.sleep(10)\"", "timeout": 0.5},
        )
        assert res["success"] is False

    # ------------------------------------------------------------------ #
    # Allowed directory checks
    # ------------------------------------------------------------------ #

    def test_allowed_directory_check(self, actuator):
        for subdir in ("data", "reports", "logs", "temp"):
            path = os.path.join(str(actuator.project_root), subdir, "file.txt")
            assert actuator._is_allowed_path(path) is True

    def test_blocked_outside_directory(self, actuator):
        outside = os.path.join(str(actuator.project_root), "..", "outside.txt")
        res = actuator.execute_action(
            "write_text_file",
            {"path": outside, "content": "bad"},
        )
        assert res["success"] is False
        assert "path_outside_allowed_directories" in res["error"]

    def test_blocked_project_root_file(self, actuator):
        root_file = os.path.join(str(actuator.project_root), "root_file.txt")
        res = actuator.execute_action(
            "write_text_file",
            {"path": root_file, "content": "bad"},
        )
        assert res["success"] is False

    # ------------------------------------------------------------------ #
    # Dangerous actions & approval levels
    # ------------------------------------------------------------------ #

    def test_delete_file_blocked_without_human_review(self, actuator):
        path = os.path.join(str(actuator.project_root), "data", "to_delete.txt")
        with open(path, "w") as f:
            f.write("delete me")
        res = actuator.execute_action(
            "delete_file",
            {"path": path},
        )
        assert res["success"] is False
        assert "dangerous_action_requires_human_review" in res["error"]

    def test_delete_file_with_human_review(self, actuator):
        path = os.path.join(str(actuator.project_root), "data", "to_delete.txt")
        with open(path, "w") as f:
            f.write("delete me")
        res = actuator.execute_action(
            "delete_file",
            {"path": path},
            approval_level="human_review",
        )
        assert res["success"] is True
        assert not os.path.exists(path)

    def test_delete_file_rejects_directory(self, actuator):
        dir_path = os.path.join(str(actuator.project_root), "data", "a_dir")
        os.makedirs(dir_path, exist_ok=True)
        res = actuator.execute_action(
            "delete_file",
            {"path": dir_path},
            approval_level="human_review",
        )
        assert res["success"] is False
        assert "not_a_file_or_does_not_exist" in res["error"]

    def test_delete_file_rejects_wildcards(self, actuator):
        # Pass a wildcard path without creating the file (Windows forbids * in filenames)
        path = os.path.join(str(actuator.project_root), "data", "*.txt")
        res = actuator.execute_action(
            "delete_file",
            {"path": path},
            approval_level="human_review",
        )
        assert res["success"] is False
        assert "wildcards_not_allowed" in res["error"]

    def test_execute_command_blocked_without_human_review(self, actuator):
        res = actuator.execute_action(
            "execute_command",
            {"cmd": "echo hello"},
        )
        # execute_command is dangerous, so blocked without human_review
        assert res["success"] is False
        assert "dangerous_action_requires_human_review" in res["error"]

    def test_execute_command_allowed_with_human_review(self, actuator):
        res = actuator.execute_action(
            "execute_command",
            {"cmd": "echo hello"},
            approval_level="human_review",
        )
        assert res["success"] is True
        assert "hello" in res["result"]["stdout"].lower()

    # ------------------------------------------------------------------ #
    # Action history tracking
    # ------------------------------------------------------------------ #

    def test_action_history_tracking(self, actuator):
        path = os.path.join(str(actuator.project_root), "data", "hist.txt")
        actuator.execute_action("write_text_file", {"path": path, "content": "a"})
        actuator.execute_action("read_file", {"path": path})
        actuator.execute_action("list_directory", {"path": str(actuator.project_root / "data")})
        history = actuator.get_action_history()
        assert len(history) == 3
        for record in history:
            assert "timestamp" in record
            assert "action_type" in record
            assert "outcome" in record
            assert record["outcome"] in (ActionOutcome.SUCCESS, ActionOutcome.FAILURE, ActionOutcome.BLOCKED, ActionOutcome.REVERTED)

    # ------------------------------------------------------------------ #
    # Revert
    # ------------------------------------------------------------------ #

    def test_revert_last_action_write(self, actuator):
        path = os.path.join(str(actuator.project_root), "data", "rev.txt")
        actuator.execute_action("write_text_file", {"path": path, "content": "version 1"})
        rev = actuator.revert_last_action()
        assert rev["success"] is True
        assert rev["reverted_action_type"] == "write_text_file"
        # File should be gone because there was no prior backup
        assert not os.path.exists(path)

    def test_revert_last_action_overwrite(self, actuator):
        path = os.path.join(str(actuator.project_root), "data", "rev2.txt")
        # Pre-existing file
        with open(path, "w") as f:
            f.write("original")
        actuator.execute_action("write_text_file", {"path": path, "content": "changed"})
        with open(path) as f:
            assert f.read() == "changed"
        rev = actuator.revert_last_action()
        assert rev["success"] is True
        with open(path) as f:
            assert f.read() == "original"

    def test_revert_last_action_create_directory(self, actuator):
        path = os.path.join(str(actuator.project_root), "temp", "rev_dir")
        actuator.execute_action("create_directory", {"path": path})
        assert os.path.isdir(path)
        rev = actuator.revert_last_action()
        assert rev["success"] is True
        assert rev["reverted_action_type"] == "create_directory"
        assert not os.path.exists(path)

    def test_revert_last_action_delete_file(self, actuator):
        path = os.path.join(str(actuator.project_root), "data", "rev_del.txt")
        with open(path, "w") as f:
            f.write("restore me")
        actuator.execute_action(
            "delete_file",
            {"path": path},
            approval_level="human_review",
        )
        assert not os.path.exists(path)
        rev = actuator.revert_last_action()
        assert rev["success"] is True
        assert os.path.exists(path)
        with open(path) as f:
            assert f.read() == "restore me"

    def test_revert_no_actions(self, actuator):
        rev = actuator.revert_last_action()
        assert rev["success"] is False
        assert rev["error"] == "no_actions_to_revert"

    # ------------------------------------------------------------------ #
    # Signals
    # ------------------------------------------------------------------ #

    def test_send_signal_to_self(self, actuator):
        for signal in ("request_pause", "request_sleep", "request_resume", "request_shutdown"):
            res = actuator.execute_action(
                "send_signal_to_self",
                {"signal_type": signal},
            )
            assert res["success"] is True
            assert res["result"]["signal_type"] == signal
            assert res["result"]["delivered"] is True

    def test_send_signal_to_self_rejects_invalid(self, actuator):
        res = actuator.execute_action(
            "send_signal_to_self",
            {"signal_type": "request_destroy"},
        )
        assert res["success"] is False
        assert "invalid_signal_type" in res["error"]

    def test_audit_log_written(self, actuator):
        import json
        path = os.path.join(str(actuator.project_root), "data", "audit.txt")
        actuator.execute_action("write_text_file", {"path": path, "content": "audit"})
        audit_path = actuator._audit_path
        assert audit_path.exists()
        lines = audit_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) >= 1
        record = json.loads(lines[0])
        assert "timestamp" in record
        assert "action_id" in record

    # ------------------------------------------------------------------ #
    # Proposal / approval flow
    # ------------------------------------------------------------------ #

    def test_propose_and_approve_safe_action(self, actuator):
        path = os.path.join(str(actuator.project_root), "data", "prop.txt")
        pid = actuator.propose_action("write_text_file", {"path": path, "content": "proposed"})
        assert pid.startswith("prop_")
        res = actuator.approve_action(pid)
        assert res["success"] is True
        with open(path) as f:
            assert f.read() == "proposed"

    def test_propose_blocked_then_approve_fails(self, actuator):
        # execute_command proposed without human_review will be blocked by the
        # dangerous-action gate inside execute_action, but propose_action itself
        # does not block unless governance blocks it.  So we test the governance
        # blocked path by forcing a real execution attempt.
        pid = actuator.propose_action("execute_command", {"cmd": "echo hello"})
        # It should be in queue because propose_action only blocks if governance blocks.
        # But our current actuator marks execute_command as dangerous requiring
        # human_review at execute time, not at propose time.
        # So approve with automatic should fail.
        res = actuator.approve_action(pid)
        assert res["success"] is False
        assert "dangerous_action_requires_human_review" in res["error"]

    def test_approve_unknown_proposal(self, actuator):
        res = actuator.approve_action("prop_does_not_exist")
        assert res["success"] is False
        assert res["error"] == "proposal_not_found"

    def test_approve_already_processed(self, actuator):
        path = os.path.join(str(actuator.project_root), "data", "dup.txt")
        pid = actuator.propose_action("write_text_file", {"path": path, "content": "x"})
        actuator.approve_action(pid)
        res = actuator.approve_action(pid)
        assert res["success"] is False
        assert res["error"] == "proposal_already_processed"

    # ------------------------------------------------------------------ #
    # Governance integration
    # ------------------------------------------------------------------ #

    def test_governance_integration(self, actuator):
        # Verify that propose_action populates governance_decision when
        # ActionGovernance is installed.
        pid = actuator.propose_action("read_file", {"path": os.path.join(str(actuator.project_root), "data", "g.txt")})
        proposal = actuator._proposals[pid]
        if actuator._policy_engine is not None:
            assert proposal["governance_decision"] is not None
            # read_file maps to OBSERVE_ONLY which is low risk -> not blocked
            assert proposal["status"] == "proposed"
        else:
            assert proposal["governance_decision"] is None

    # ------------------------------------------------------------------ #
    # Monitor process
    # ------------------------------------------------------------------ #

    def test_monitor_process(self, actuator):
        # Monitor the current Python process
        import os as _os
        res = actuator.execute_action("monitor_process", {"pid": _os.getpid()})
        assert res["success"] is True
        assert res["result"]["pid"] == _os.getpid()
