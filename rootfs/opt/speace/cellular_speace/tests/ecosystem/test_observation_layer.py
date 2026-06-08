"""Tests for T131-A — Ecosystem Observation Layer."""

import json
import time
from pathlib import Path

import pytest

from speace_core.ecosystem.ecosystem_registry import EcosystemRegistry
from speace_core.ecosystem.ecosystem_state import EcosystemObservation, EcosystemSource
from speace_core.ecosystem.observation_layer import EcosystemObservationLayer
from speace_core.ecosystem.semantic_mapper import SemanticMapper
from speace_core.ecosystem.trust_governor import TrustGovernor


# ------------------------------------------------------------------ #
# SemanticMapper
# ------------------------------------------------------------------ #


def test_semantic_mapper_known_type():
    mapper = SemanticMapper()
    assert mapper.map("iot_sensor") == "sensory_termination"


def test_semantic_mapper_unknown_type():
    mapper = SemanticMapper()
    assert mapper.map("unknown_xyz") is None


def test_semantic_mapper_describe():
    mapper = SemanticMapper()
    desc = mapper.describe("smart_grid")
    assert desc["organismic_metaphor"] == "circulatory_energetic"


# ------------------------------------------------------------------ #
# TrustGovernor
# ------------------------------------------------------------------ #


def test_trust_success():
    gov = TrustGovernor()
    assert gov.evaluate_observation(0.5, "ok") == 0.55


def test_trust_failure():
    gov = TrustGovernor()
    assert gov.evaluate_observation(0.5, "error") == 0.4


def test_trust_should_block():
    gov = TrustGovernor()
    assert gov.should_block(0.1) is True
    assert gov.should_block(0.3) is False


def test_assess_anomaly_spam():
    gov = TrustGovernor()
    obs = [{"timestamp": i * 0.5, "raw_payload": {}} for i in range(5)]
    assert gov.assess_anomaly(obs) == "spam"


def test_assess_anomaly_none():
    gov = TrustGovernor()
    obs = [{"timestamp": i * 20.0, "raw_payload": {}} for i in range(3)]
    assert gov.assess_anomaly(obs) is None


# ------------------------------------------------------------------ #
# EcosystemRegistry
# ------------------------------------------------------------------ #


def test_registry_crud(tmp_path):
    registry = EcosystemRegistry(data_root=str(tmp_path / "ecosystem"))
    source = EcosystemSource(source_id="s1", source_type="file", uri="/tmp/test.json")
    registry.register(source)
    assert registry.get("s1") is not None
    assert len(registry.list_sources()) == 1

    registry.unregister("s1")
    assert registry.get("s1") is None


def test_registry_trust_deactivation(tmp_path):
    registry = EcosystemRegistry(data_root=str(tmp_path / "ecosystem"))
    source = EcosystemSource(source_id="s1", source_type="file", uri="/tmp/test.json", trust_score=0.25)
    registry.register(source)
    registry.update_trust("s1", -0.1)  # 0.15 -> below 0.2
    updated = registry.get("s1")
    assert updated is not None
    assert updated.active is False


# ------------------------------------------------------------------ #
# EcosystemObservationLayer
# ------------------------------------------------------------------ #


def test_layer_health_empty():
    layer = EcosystemObservationLayer(data_root="data/test_ecosystem_empty")
    health = layer.health()
    assert health.total_sources == 0
    assert health.status == "isolated"


def test_layer_health_with_sources(tmp_path):
    layer = EcosystemObservationLayer(data_root=str(tmp_path / "eco"))
    layer._registry.register(
        EcosystemSource(source_id="s1", source_type="file", uri="/tmp/a.json", trust_score=0.8)
    )
    layer._registry.register(
        EcosystemSource(source_id="s2", source_type="file", uri="/tmp/b.json", trust_score=0.1, active=False)
    )
    health = layer.health()
    assert health.total_sources == 2
    assert health.active_sources == 1
    assert health.avg_trust_score > 0.4


def test_layer_describe_source(tmp_path):
    layer = EcosystemObservationLayer(data_root=str(tmp_path / "eco"))
    layer._registry.register(
        EcosystemSource(source_id="s1", source_type="iot_sensor", uri="/tmp/a.json")
    )
    detail = layer.describe_source("s1")
    assert detail is not None
    assert detail["semantic_mapping"]["organismic_metaphor"] == "sensory_termination"


def test_layer_describe_missing():
    layer = EcosystemObservationLayer(data_root="data/test_ecosystem_missing")
    detail = layer.describe_source("nonexistent")
    assert detail is None


# ------------------------------------------------------------------ #
# API tests (dashboard)
# ------------------------------------------------------------------ #


def test_dashboard_ecosystem_status():
    from fastapi.testclient import TestClient
    from speace_core.monitoring.dashboard_api import app as dashboard_app

    dashboard_app.state._testing = True
    with TestClient(dashboard_app) as client:
        res = client.get("/api/ecosystem/status")
        assert res.status_code == 200
        data = res.json()
        assert "status" in data
        assert data["status"] in ("observing", "degraded", "isolated")


def test_dashboard_ecosystem_sources():
    from fastapi.testclient import TestClient
    from speace_core.monitoring.dashboard_api import app as dashboard_app

    dashboard_app.state._testing = True
    with TestClient(dashboard_app) as client:
        res = client.get("/api/ecosystem/sources")
        assert res.status_code == 200
        data = res.json()
        assert "sources" in data
        assert isinstance(data["sources"], list)


# ------------------------------------------------------------------ #
# API tests (gateway)
# ------------------------------------------------------------------ #


def test_gateway_ecosystem_status():
    from speace_core.web_gateway.auth_engine import AuthEngine
    from speace_core.web_gateway import gateway_api

    auth = AuthEngine(data_root="data/test_web_gateway_t131")
    for key in list(auth._keys.keys()):
        auth.revoke_key(key)
    observer = auth.generate_key(role="observer")
    gateway_api._auth_engine = auth

    from fastapi.testclient import TestClient
    client = TestClient(gateway_api.app)
    res = client.get("/api/ecosystem/status", headers={"X-API-Key": observer})
    assert res.status_code == 200
    data = res.json()
    assert "status" in data


def test_gateway_ecosystem_sources():
    from speace_core.web_gateway.auth_engine import AuthEngine
    from speace_core.web_gateway import gateway_api

    auth = AuthEngine(data_root="data/test_web_gateway_t131")
    for key in list(auth._keys.keys()):
        auth.revoke_key(key)
    observer = auth.generate_key(role="observer")
    gateway_api._auth_engine = auth

    from fastapi.testclient import TestClient
    client = TestClient(gateway_api.app)
    res = client.get("/api/ecosystem/sources", headers={"X-API-Key": observer})
    assert res.status_code == 200
    data = res.json()
    assert "sources" in data


def test_gateway_ecosystem_unauthorized():
    from speace_core.web_gateway.auth_engine import AuthEngine
    from speace_core.web_gateway import gateway_api

    auth = AuthEngine(data_root="data/test_web_gateway_t131")
    for key in list(auth._keys.keys()):
        auth.revoke_key(key)
    gateway_api._auth_engine = auth

    from fastapi.testclient import TestClient
    client = TestClient(gateway_api.app)
    res = client.get("/api/ecosystem/status")
    assert res.status_code == 401
