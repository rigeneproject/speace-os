"""Tests for T131-B — Semantic Ecosystem Mapping."""

import pytest

from speace_core.ecosystem.ecosystem_graph import EcosystemGraph
from speace_core.ecosystem.ecosystem_state import EcosystemSource
from speace_core.ecosystem.semantic_mapper import SemanticMapper


# ------------------------------------------------------------------ #
# SemanticMapper enrichment
# ------------------------------------------------------------------ #


def test_system_class():
    mapper = SemanticMapper()
    assert mapper.system_class("iot_sensor") == "sensory"
    assert mapper.system_class("cloud_cluster") == "nervous"
    assert mapper.system_class("blockchain") == "memory"
    assert mapper.system_class("unknown") is None


def test_functional_role():
    mapper = SemanticMapper()
    assert mapper.functional_role("camera") == "input"
    assert mapper.functional_role("llm_agent") == "processing"
    assert mapper.functional_role("database") == "storage"
    assert mapper.functional_role("robot") == "output"


def test_relationship_hints():
    mapper = SemanticMapper()
    hints = mapper.relationship_hints("iot_sensor")
    assert "cognitive_tissue" in hints
    assert "neural_cluster" in hints


def test_describe_enriched():
    mapper = SemanticMapper()
    desc = mapper.describe("smart_grid")
    assert desc["system_class"] == "circulatory"
    assert desc["functional_role"] == "energy_transport"
    assert "typical_relationships" in desc


def test_classify_by_system():
    mapper = SemanticMapper()
    groups = mapper.classify_by_system()
    assert "sensory" in groups
    assert "nervous" in groups
    assert "iot_sensor" in groups["sensory"]


def test_infer_relationship_afferent():
    mapper = SemanticMapper()
    # sensor -> cognitive_tissue is afferent from sensor perspective
    assert mapper.infer_relationship("iot_sensor", "llm_agent") == "afferent"


def test_infer_relationship_homologous():
    mapper = SemanticMapper()
    assert mapper.infer_relationship("camera", "microphone") == "homologous"


def test_infer_relationship_unrelated():
    mapper = SemanticMapper()
    # file and weather_station have no direct relationship hints
    assert mapper.infer_relationship("file", "weather_station") == "unrelated"


# ------------------------------------------------------------------ #
# EcosystemGraph
# ------------------------------------------------------------------ #


def test_graph_add_and_remove():
    graph = EcosystemGraph()
    src = EcosystemSource(source_id="s1", source_type="iot_sensor", uri="/tmp/1.json")
    graph.add_source(src)
    assert graph.get_node("s1") is not None
    graph.remove_source("s1")
    assert graph.get_node("s1") is None


def test_graph_infer_edges():
    graph = EcosystemGraph()
    graph.add_source(EcosystemSource(source_id="s1", source_type="iot_sensor", uri="/tmp/1.json"))
    graph.add_source(EcosystemSource(source_id="s2", source_type="llm_agent", uri="/tmp/2.json"))
    graph.infer_edges()
    edges = graph.edges_for("s1")
    assert any(e["to"] == "s2" for e in edges)


def test_graph_clusters():
    graph = EcosystemGraph()
    graph.add_source(EcosystemSource(source_id="s1", source_type="iot_sensor", uri="/tmp/1.json"))
    graph.add_source(EcosystemSource(source_id="s2", source_type="camera", uri="/tmp/2.json"))
    clusters = graph.clusters_by_system()
    assert "sensory" in clusters
    assert set(clusters["sensory"]) == {"s1", "s2"}


def test_graph_pathways():
    graph = EcosystemGraph()
    graph.add_source(EcosystemSource(source_id="inp", source_type="iot_sensor", uri="/tmp/in.json"))
    graph.add_source(EcosystemSource(source_id="proc", source_type="llm_agent", uri="/tmp/proc.json"))
    graph.add_source(EcosystemSource(source_id="out", source_type="robot", uri="/tmp/out.json"))
    graph.infer_edges()
    pathways = graph.functional_pathways()
    assert len(pathways) > 0


def test_graph_summary():
    graph = EcosystemGraph()
    graph.add_source(EcosystemSource(source_id="s1", source_type="iot_sensor", uri="/tmp/1.json"))
    graph.infer_edges()
    summary = graph.summary()
    assert summary["node_count"] == 1
    assert summary["edge_count"] == 0
    assert "systems" in summary


def test_graph_describe_map():
    graph = EcosystemGraph()
    graph.add_source(EcosystemSource(source_id="s1", source_type="iot_sensor", uri="/tmp/1.json"))
    graph.infer_edges()
    text = graph.describe_map()
    assert "Ecosystem Cognitive Map" in text
    assert "sensory" in text


# ------------------------------------------------------------------ #
# Dashboard API
# ------------------------------------------------------------------ #


def test_dashboard_ecosystem_graph():
    from fastapi.testclient import TestClient
    from speace_core.monitoring.dashboard_api import app as dashboard_app

    dashboard_app.state._testing = True
    with TestClient(dashboard_app) as client:
        res = client.get("/api/ecosystem/graph")
        assert res.status_code == 200
        data = res.json()
        assert "node_count" in data


def test_dashboard_ecosystem_graph_narrative():
    from fastapi.testclient import TestClient
    from speace_core.monitoring.dashboard_api import app as dashboard_app

    dashboard_app.state._testing = True
    with TestClient(dashboard_app) as client:
        res = client.get("/api/ecosystem/graph/narrative")
        assert res.status_code == 200
        data = res.json()
        assert "narrative" in data
        assert "Ecosystem Cognitive Map" in data["narrative"]


# ------------------------------------------------------------------ #
# Gateway API
# ------------------------------------------------------------------ #


def test_gateway_ecosystem_graph():
    from speace_core.web_gateway.auth_engine import AuthEngine
    from speace_core.web_gateway import gateway_api

    auth = AuthEngine(data_root="data/test_web_gateway_t131b")
    for key in list(auth._keys.keys()):
        auth.revoke_key(key)
    observer = auth.generate_key(role="observer")
    gateway_api._auth_engine = auth

    from fastapi.testclient import TestClient
    client = TestClient(gateway_api.app)
    res = client.get("/api/ecosystem/graph", headers={"X-API-Key": observer})
    assert res.status_code == 200
    data = res.json()
    assert "node_count" in data


def test_gateway_ecosystem_graph_narrative():
    from speace_core.web_gateway.auth_engine import AuthEngine
    from speace_core.web_gateway import gateway_api

    auth = AuthEngine(data_root="data/test_web_gateway_t131b")
    for key in list(auth._keys.keys()):
        auth.revoke_key(key)
    observer = auth.generate_key(role="observer")
    gateway_api._auth_engine = auth

    from fastapi.testclient import TestClient
    client = TestClient(gateway_api.app)
    res = client.get("/api/ecosystem/graph/narrative", headers={"X-API-Key": observer})
    assert res.status_code == 200
    data = res.json()
    assert "narrative" in data


def test_gateway_ecosystem_graph_unauthorized():
    from speace_core.web_gateway.auth_engine import AuthEngine
    from speace_core.web_gateway import gateway_api

    auth = AuthEngine(data_root="data/test_web_gateway_t131b")
    for key in list(auth._keys.keys()):
        auth.revoke_key(key)
    gateway_api._auth_engine = auth

    from fastapi.testclient import TestClient
    client = TestClient(gateway_api.app)
    res = client.get("/api/ecosystem/graph")
    assert res.status_code == 401
