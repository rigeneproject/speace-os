"""Tests for T131-D — Adaptive Connectors."""

import asyncio
import tempfile
from pathlib import Path

import pytest

from speace_core.ecosystem.adapter_registry import AdapterRegistry
from speace_core.ecosystem.adapters.base_adapter import AdapterResult
from speace_core.ecosystem.adapters.file_adapter import FileAdapter
from speace_core.ecosystem.adapters.http_adapter import HTTPAdapter
from speace_core.ecosystem.adapters.llm_adapter import LLMAdapter
from speace_core.ecosystem.adapters.mqtt_adapter import MQTTAdapter
from speace_core.ecosystem.adapters.blockchain_adapter import BlockchainAdapter


# ------------------------------------------------------------------ #
# BaseAdapter
# ------------------------------------------------------------------ #


def test_adapter_result_defaults():
    r = AdapterResult()
    assert r.is_ok() is True
    assert r.payload == {}


def test_adapter_result_not_ok():
    r = AdapterResult(status="error")
    assert r.is_ok() is False


# ------------------------------------------------------------------ #
# FileAdapter
# ------------------------------------------------------------------ #


@pytest.mark.asyncio
async def test_file_adapter_reads_json(tmp_path):
    path = tmp_path / "test.json"
    path.write_text('{"temperature": 22}', encoding="utf-8")
    adapter = FileAdapter()
    result = await adapter.fetch(str(path))
    assert result.is_ok()
    assert result.payload["temperature"] == 22


@pytest.mark.asyncio
async def test_file_adapter_not_found():
    adapter = FileAdapter()
    result = await adapter.fetch("/nonexistent/path.json")
    assert result.status == "error"
    assert "file_not_found" in result.payload["_error"]


@pytest.mark.asyncio
async def test_file_adapter_raw_text(tmp_path):
    path = tmp_path / "test.txt"
    path.write_text("hello world", encoding="utf-8")
    adapter = FileAdapter()
    result = await adapter.fetch(str(path))
    assert result.is_ok()
    assert result.payload["_raw"] == "hello world"


# ------------------------------------------------------------------ #
# HTTPAdapter
# ------------------------------------------------------------------ #


@pytest.mark.asyncio
async def test_http_adapter_unsupported():
    adapter = HTTPAdapter()
    # This test works even without httpx because the adapter handles absence
    # But since we likely have httpx, we test a real 404
    result = await adapter.fetch("http://localhost:59999/nonexistent")
    assert result.status == "error"


# ------------------------------------------------------------------ #
# MQTTAdapter
# ------------------------------------------------------------------ #


@pytest.mark.asyncio
async def test_mqtt_adapter_stub():
    adapter = MQTTAdapter()
    result = await adapter.fetch("sensors/temp")
    assert result.is_ok()
    assert result.payload["topic"] == "sensors/temp"


# ------------------------------------------------------------------ #
# LLMAdapter
# ------------------------------------------------------------------ #


@pytest.mark.asyncio
async def test_llm_adapter_unsupported():
    # If httpx is present, it will try to GET /health on the URI
    # We test against a non-existent endpoint to verify error handling
    adapter = LLMAdapter()
    result = await adapter.fetch("http://localhost:59999/llm")
    assert result.status == "error"


# ------------------------------------------------------------------ #
# BlockchainAdapter
# ------------------------------------------------------------------ #


@pytest.mark.asyncio
async def test_blockchain_adapter_unsupported():
    adapter = BlockchainAdapter()
    result = await adapter.fetch("http://localhost:59999/chain")
    assert result.status == "error"


# ------------------------------------------------------------------ #
# AdapterRegistry
# ------------------------------------------------------------------ #


def test_registry_supported_types():
    reg = AdapterRegistry()
    types = reg.list_supported_types()
    assert "rest_api" in types
    assert "file" in types
    assert "mqtt_broker" in types
    assert "llm_agent" in types
    assert "blockchain" in types


@pytest.mark.asyncio
async def test_registry_fetch_file(tmp_path):
    path = tmp_path / "data.json"
    path.write_text('{"key": "value"}', encoding="utf-8")
    reg = AdapterRegistry()
    result = await reg.fetch("file", str(path))
    assert result.is_ok()
    assert result.payload["key"] == "value"


@pytest.mark.asyncio
async def test_registry_fetch_unsupported():
    reg = AdapterRegistry()
    result = await reg.fetch("unknown_type", "http://example.com")
    assert result.status == "unsupported"


def test_registry_register_override(tmp_path):
    reg = AdapterRegistry()
    custom = FileAdapter()
    reg.register_adapter("custom_file", custom)
    assert reg.get_adapter("custom_file") is custom


# ------------------------------------------------------------------ #
# ObservationLayer integration
# ------------------------------------------------------------------ #


def test_layer_uses_adapter_registry(tmp_path):
    from speace_core.ecosystem.ecosystem_state import EcosystemSource
    from speace_core.ecosystem.observation_layer import EcosystemObservationLayer

    layer = EcosystemObservationLayer(data_root=str(tmp_path / "eco_d"))
    # The layer should have an adapter registry
    assert hasattr(layer, "_adapters")
    assert isinstance(layer._adapters, AdapterRegistry)
