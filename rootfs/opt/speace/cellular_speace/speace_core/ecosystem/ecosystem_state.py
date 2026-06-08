"""EcosystemState — Pydantic models for T131-A."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class EcosystemSource(BaseModel):
    source_id: str
    source_type: str  # e.g. "rest_api", "mqtt", "file", "sensor"
    uri: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    trust_score: float = 0.5
    active: bool = True
    last_seen: float = 0.0
    poll_interval_seconds: int = 60
    boundary_status: str = "observed"  # observed | trusted | assimilated
    assimilation_count: int = 0
    last_assimilated_at: float = 0.0
    last_revoked_at: float = 0.0


class EcosystemObservation(BaseModel):
    timestamp: float
    source_id: str
    raw_payload: Dict[str, Any] = Field(default_factory=dict)
    payload_truncated: bool = False
    trust_score_at_observation: float = 0.5
    status: str = "ok"  # ok | timeout | error | blocked


class EcosystemHealth(BaseModel):
    total_sources: int = 0
    active_sources: int = 0
    avg_trust_score: float = 0.0
    observations_last_hour: int = 0
    status: str = "observing"  # observing | degraded | isolated
    timestamp: float = 0.0
    boundary_counts: Dict[str, int] = Field(default_factory=dict)
