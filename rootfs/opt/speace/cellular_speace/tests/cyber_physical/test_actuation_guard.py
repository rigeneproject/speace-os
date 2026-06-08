import pytest
from speace_core.cellular_brain.cyber_physical.actuation_guard import ActuationGuard
from speace_core.cellular_brain.cyber_physical.cyber_physical_models import (
    ActuationRequest,
)


class TestActuationGuard:
    def test_blocks_all_actuation_requests(self):
        guard = ActuationGuard()
        req = ActuationRequest(
            request_id="req_1",
            target_system="motor",
            action="actuate",
            payload={"speed": 100},
            risk_score=0.3,
        )
        result = guard.evaluate_actuation_request(req)
        assert result.blocked is True
        assert "T60" in result.reason

    def test_block_actuation_returns_decision(self):
        guard = ActuationGuard()
        req = ActuationRequest(
            request_id="req_1",
            target_system="valve",
            action="open",
            risk_score=0.8,
        )
        decision = guard.block_actuation(req)
        assert decision.accepted is False
        assert decision.action == "block_actuation"
        assert decision.safety_relevant is True

    def test_block_actuation_low_risk(self):
        guard = ActuationGuard()
        req = ActuationRequest(
            request_id="req_2",
            target_system="light",
            action="on",
            risk_score=0.1,
        )
        decision = guard.block_actuation(req)
        assert decision.accepted is False
        assert decision.safety_relevant is False

    def test_simulate_actuation_dry_run(self):
        guard = ActuationGuard()
        req = ActuationRequest(
            request_id="req_1",
            target_system="motor",
            action="actuate",
            payload={"speed": 100},
        )
        sim = guard.simulate_actuation_dry_run(req)
        assert sim["would_execute"] is False
        assert sim["blocked"] is True
        assert sim["reason"] == "dry_run_simulation_only"

    def test_requires_human_approval(self):
        guard = ActuationGuard()
        req = ActuationRequest(
            request_id="req_1",
            target_system="motor",
            action="actuate",
        )
        assert ActuationGuard.requires_human_approval(req) is True

    def test_evaluate_actuation_request_various_actions(self):
        guard = ActuationGuard()
        for action in ["actuate", "control", "command", "write", "modify", "execute"]:
            req = ActuationRequest(
                request_id=f"req_{action}",
                target_system="sys",
                action=action,
            )
            result = guard.evaluate_actuation_request(req)
            assert result.blocked is True

    def test_evaluate_actuation_request_preserves_payload(self):
        guard = ActuationGuard()
        req = ActuationRequest(
            request_id="req_1",
            target_system="motor",
            action="actuate",
            payload={"angle": 45},
        )
        result = guard.evaluate_actuation_request(req)
        assert result.payload == {"angle": 45}

    def test_simulate_dry_run_preserves_target(self):
        guard = ActuationGuard()
        req = ActuationRequest(
            request_id="req_1",
            target_system="robot_arm",
            action="move",
            payload={"x": 10},
        )
        sim = guard.simulate_actuation_dry_run(req)
        assert sim["target_system"] == "robot_arm"
        assert sim["action"] == "move"
