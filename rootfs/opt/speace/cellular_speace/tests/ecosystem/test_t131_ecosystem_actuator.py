"""Tests for T131-E — Controlled Ecosystem Interaction."""

import pytest

from speace_core.ecosystem.ecosystem_actuator import EcosystemActuator, EcosystemActionProposal


# ------------------------------------------------------------------ #
# Unit tests
# ------------------------------------------------------------------ #


def test_propose(tmp_path):
    act = EcosystemActuator(data_root=str(tmp_path / "actuator"))
    p = act.propose("s1", "mqtt_publish", {"topic": "test", "msg": "hello"})
    assert p.status == "pending"
    assert p.source_id == "s1"
    assert p.action_type == "mqtt_publish"


def test_approve(tmp_path):
    act = EcosystemActuator(data_root=str(tmp_path / "actuator"))
    p = act.propose("s1", "mqtt_publish", {})
    approved = act.approve(p.proposal_id, approver="admin1")
    assert approved is not None
    assert approved.status == "approved"
    assert approved.approved_by == "admin1"


def test_approve_not_pending(tmp_path):
    act = EcosystemActuator(data_root=str(tmp_path / "actuator"))
    p = act.propose("s1", "mqtt_publish", {})
    act.approve(p.proposal_id)
    assert act.approve(p.proposal_id) is None  # already approved


def test_reject(tmp_path):
    act = EcosystemActuator(data_root=str(tmp_path / "actuator"))
    p = act.propose("s1", "mqtt_publish", {})
    rejected = act.reject(p.proposal_id, reviewer="admin1")
    assert rejected is not None
    assert rejected.status == "rejected"


def test_execute_stub(tmp_path):
    act = EcosystemActuator(data_root=str(tmp_path / "actuator"), allow_execution=False)
    p = act.propose("s1", "mqtt_publish", {"topic": "test"})
    act.approve(p.proposal_id)
    executed = act.execute(p.proposal_id)
    assert executed is not None
    assert executed.status == "executed"
    assert executed.result["_mode"] == "stub"
    assert "No external action was taken" in executed.result["_note"]


def test_execute_not_approved(tmp_path):
    act = EcosystemActuator(data_root=str(tmp_path / "actuator"))
    p = act.propose("s1", "mqtt_publish", {})
    assert act.execute(p.proposal_id) is None  # not approved yet


def test_list_and_filter(tmp_path):
    act = EcosystemActuator(data_root=str(tmp_path / "actuator"))
    a = act.propose("s1", "mqtt_publish", {})
    b = act.propose("s2", "http_post", {})
    act.approve(a.proposal_id)
    pending = act.list_proposals(status_filter="pending")
    assert len(pending) == 1
    assert pending[0].proposal_id == b.proposal_id


def test_summary(tmp_path):
    act = EcosystemActuator(data_root=str(tmp_path / "actuator"))
    act.propose("s1", "mqtt_publish", {})
    act.propose("s2", "http_post", {})
    s = act.summary()
    assert s["total"] == 2
    assert s["execution_enabled"] is False


def test_persistence(tmp_path):
    data_root = str(tmp_path / "actuator")
    act1 = EcosystemActuator(data_root=data_root)
    p = act1.propose("s1", "mqtt_publish", {})
    act1.approve(p.proposal_id)

    act2 = EcosystemActuator(data_root=data_root)
    loaded = act2.get(p.proposal_id)
    assert loaded is not None
    assert loaded.status == "approved"


# ------------------------------------------------------------------ #
# Dashboard API
# ------------------------------------------------------------------ #


def test_dashboard_action_lifecycle():
    from fastapi.testclient import TestClient
    from speace_core.monitoring.dashboard_api import app as dashboard_app

    dashboard_app.state._testing = True
    with TestClient(dashboard_app) as client:
        # Propose
        res = client.post("/api/ecosystem/actions/propose", json={
            "source_id": "s1",
            "action_type": "mqtt_publish",
            "payload": {"topic": "test"},
        })
        assert res.status_code == 200
        pid = res.json()["proposal_id"]

        # List
        res = client.get("/api/ecosystem/actions")
        assert res.status_code == 200
        assert any(p["proposal_id"] == pid for p in res.json()["proposals"])

        # Detail
        res = client.get(f"/api/ecosystem/actions/{pid}")
        assert res.status_code == 200
        assert res.json()["status"] == "pending"

        # Approve
        res = client.post(f"/api/ecosystem/actions/{pid}/approve", json={"approver": "admin"})
        assert res.status_code == 200
        assert res.json()["status"] == "approved"

        # Execute (stubbed)
        res = client.post(f"/api/ecosystem/actions/{pid}/execute")
        assert res.status_code == 200
        assert res.json()["status"] == "executed"
        assert res.json()["result"]["_mode"] == "stub"


# ------------------------------------------------------------------ #
# Gateway API
# ------------------------------------------------------------------ #


def test_gateway_action_rbac():
    from speace_core.web_gateway.auth_engine import AuthEngine
    from speace_core.web_gateway import gateway_api

    auth = AuthEngine(data_root="data/test_web_gateway_t131e")
    for key in list(auth._keys.keys()):
        auth.revoke_key(key)
    observer = auth.generate_key(role="observer")
    operator = auth.generate_key(role="operator")
    reviewer = auth.generate_key(role="reviewer")
    gateway_api._auth_engine = auth

    from fastapi.testclient import TestClient
    client = TestClient(gateway_api.app)

    # Observer cannot propose
    res = client.post("/api/ecosystem/actions/propose", json={
        "source_id": "s1", "action_type": "mqtt_publish", "payload": {},
    }, headers={"X-API-Key": observer})
    assert res.status_code == 403

    # Operator can propose
    res = client.post("/api/ecosystem/actions/propose", json={
        "source_id": "s1", "action_type": "mqtt_publish", "payload": {},
    }, headers={"X-API-Key": operator})
    assert res.status_code == 200
    pid = res.json()["proposal_id"]

    # Operator cannot approve
    res = client.post(f"/api/ecosystem/actions/{pid}/approve", headers={"X-API-Key": operator})
    assert res.status_code == 403

    # Reviewer can approve
    res = client.post(f"/api/ecosystem/actions/{pid}/approve", headers={"X-API-Key": reviewer})
    assert res.status_code == 200
    assert res.json()["status"] == "approved"

    # Reviewer can execute
    res = client.post(f"/api/ecosystem/actions/{pid}/execute", headers={"X-API-Key": reviewer})
    assert res.status_code == 200
    assert res.json()["status"] == "executed"
