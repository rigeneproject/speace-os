"""EcosystemObservationLayer — T131-A: read-only passive observation of external sources.

Security rules:
- Only HTTP GET or file read — no POST/PUT/DELETE/EXEC
- Max payload size 1MB
- All payloads validated as JSON (Pydantic)
- Trust scoring blocks untrusted sources automatically
- No code execution on external data
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from speace_core.ecosystem.adapter_registry import AdapterRegistry
from speace_core.ecosystem.ecosystem_audit import EcosystemAudit
from speace_core.ecosystem.ecosystem_boundary_layer import EcosystemBoundaryLayer
from speace_core.ecosystem.ecosystem_graph import EcosystemGraph
from speace_core.ecosystem.ecosystem_registry import EcosystemRegistry
from speace_core.ecosystem.ecosystem_state import EcosystemHealth, EcosystemObservation, EcosystemSource
from speace_core.ecosystem.semantic_mapper import SemanticMapper
from speace_core.ecosystem.trust_governor import TrustGovernor


class EcosystemObservationLayer:
    """Polls external sources in read-only mode and records observations."""

    MAX_PAYLOAD_BYTES = 1_048_576  # 1 MB

    def __init__(
        self,
        data_root: str = "data/ecosystem",
        poll_interval_seconds: int = 60,
    ) -> None:
        self._data_root = Path(data_root)
        self._data_root.mkdir(parents=True, exist_ok=True)
        self._observations_path = self._data_root / "observations.jsonl"
        self._registry = EcosystemRegistry(data_root=data_root)
        self._trust_governor = TrustGovernor()
        self._semantic_mapper = SemanticMapper()
        self._graph = EcosystemGraph(mapper=self._semantic_mapper)
        self._adapters = AdapterRegistry()
        self._boundary = EcosystemBoundaryLayer(data_root=data_root)
        self._audit = EcosystemAudit(
            semantic_mapper=self._semantic_mapper,
            trust_governor=self._trust_governor,
        )
        self._poll_interval = poll_interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task[Any]] = None

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    async def start(self) -> None:
        """Start background polling."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        """Stop background polling."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    # ------------------------------------------------------------------ #
    # Polling loop
    # ------------------------------------------------------------------ #

    async def _poll_loop(self) -> None:
        while self._running:
            await self._tick()
            await asyncio.sleep(self._poll_interval)

    async def _tick(self) -> None:
        """Poll all active sources once."""
        for source in self._registry.list_sources(active_only=True):
            await self._observe_source(source)

    async def _observe_source(self, source: EcosystemSource) -> None:
        """Poll a single source and record the observation."""
        raw_payload: Dict[str, Any] = {}
        status = "ok"
        trust = source.trust_score
        start = time.time()

        # T131-C: rate limiting
        if not self._trust_governor.check_rate(source.source_id):
            status = "blocked"
            new_trust = self._trust_governor.evaluate_observation(trust, status)
            self._registry.update_trust(source.source_id, new_trust - trust)
            self._registry.touch(source.source_id)
            observation = EcosystemObservation(
                timestamp=time.time(),
                source_id=source.source_id,
                raw_payload={"_blocked_reason": "rate_limit_exceeded"},
                payload_truncated=False,
                trust_score_at_observation=new_trust,
                status=status,
            )
            self._persist_observation(observation)
            return

        self._trust_governor.record_request(source.source_id)

        # T131-D: use adapter registry for protocol-specific fetching
        result = await self._adapters.fetch(source.source_type, source.uri, source.metadata)
        raw_payload = result.payload
        status = result.status

        # T131-C: sandbox validation
        if status == "ok" and not self._trust_governor.validate_sandbox(raw_payload):
            status = "blocked"
            raw_payload = {"_blocked_reason": "sandbox_validation_failed"}

        # Update trust
        new_trust = self._trust_governor.evaluate_observation(trust, status)
        self._registry.update_trust(source.source_id, new_trust - trust)
        self._registry.touch(source.source_id)

        # Truncate if needed
        payload_truncated = False
        payload_str = json.dumps(raw_payload)
        if len(payload_str.encode("utf-8")) > self.MAX_PAYLOAD_BYTES:
            raw_payload = {"_truncated": True, "_original_length": len(payload_str)}
            payload_truncated = True

        # Anomaly detection
        recent = self._recent_observations(source.source_id, limit=10)
        recent.append({"timestamp": time.time(), "raw_payload": raw_payload})
        anomaly = self._trust_governor.assess_anomaly(recent)
        if anomaly:
            status = "blocked"
            self._registry.update_trust(source.source_id, -0.2)

        observation = EcosystemObservation(
            timestamp=time.time(),
            source_id=source.source_id,
            raw_payload=raw_payload,
            payload_truncated=payload_truncated,
            trust_score_at_observation=new_trust,
            status=status,
        )
        self._persist_observation(observation)

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _persist_observation(self, observation: EcosystemObservation) -> None:
        try:
            with self._observations_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(observation.model_dump(mode="json")) + "\n")
        except OSError:
            pass

    def _recent_observations(self, source_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Return recent observation records for anomaly detection."""
        if not self._observations_path.exists():
            return []
        records: List[Dict[str, Any]] = []
        try:
            with self._observations_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obs = json.loads(line)
                        if obs.get("source_id") == source_id:
                            records.append(obs)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass
        return records[-limit:]

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def health(self) -> EcosystemHealth:
        """Current ecosystem health summary."""
        sources = self._registry.list_sources()
        active = self._registry.list_sources(active_only=True)
        avg_trust = sum(s.trust_score for s in sources) / len(sources) if sources else 0.0

        # Count observations in last hour
        count_last_hour = 0
        now = time.time()
        if self._observations_path.exists():
            try:
                with self._observations_path.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obs = json.loads(line)
                            if now - obs.get("timestamp", 0) < 3600:
                                count_last_hour += 1
                        except json.JSONDecodeError:
                            continue
            except OSError:
                pass

        status = "observing"
        if not active:
            status = "isolated"
        elif avg_trust < 0.3:
            status = "degraded"

        boundary_counts = {"observed": 0, "trusted": 0, "assimilated": 0}
        for s in sources:
            boundary_counts[s.boundary_status] = boundary_counts.get(s.boundary_status, 0) + 1

        return EcosystemHealth(
            total_sources=len(sources),
            active_sources=len(active),
            avg_trust_score=round(avg_trust, 4),
            observations_last_hour=count_last_hour,
            status=status,
            timestamp=time.time(),
            boundary_counts=boundary_counts,
        )

    def describe_source(self, source_id: str) -> Optional[Dict[str, Any]]:
        """Return source info with semantic mapping, boundary status, and T131-C governance status."""
        source = self._registry.get(source_id)
        if source is None:
            return None
        semantic = self._semantic_mapper.describe(source.source_type)
        rate = self._trust_governor.rate_status(source_id)
        observations = self._recent_observations(source_id, limit=50)
        audit = self._audit.full_audit(source, observations)
        return {
            **source.model_dump(mode="json"),
            "semantic_mapping": semantic,
            "rate_limit": rate,
            "permissions": self._trust_governor.list_permissions(source_id),
            "has_identity": self._trust_governor.has_identity(source_id),
            "boundary_status": source.boundary_status,
            "audit": audit,
            "can_assimilate": audit["overall_passed"] and source.boundary_status == "trusted",
        }

    def list_sources(self) -> List[EcosystemSource]:
        return self._registry.list_sources()

    def rebuild_graph(self) -> None:
        """Rebuild the ecosystem graph from current registry sources."""
        self._graph = EcosystemGraph(mapper=self._semantic_mapper)
        for source in self._registry.list_sources():
            self._graph.add_source(source)
        self._graph.infer_edges()

    def graph_summary(self) -> Optional[Dict[str, Any]]:
        """Return T131-B ecosystem graph summary."""
        if not self._graph.list_nodes():
            self.rebuild_graph()
        return self._graph.summary()

    def describe_graph(self) -> str:
        """Return T131-B reflective narrative of the ecosystem map."""
        if not self._graph.list_nodes():
            self.rebuild_graph()
        return self._graph.describe_map()

    # ------------------------------------------------------------------ #
    # T131 Boundary Layer public API
    # ------------------------------------------------------------------ #

    def promote_to_trusted(self, source_id: str) -> bool:
        """Promote a source from observed to trusted after audit."""
        source = self._registry.get(source_id)
        if source is None or source.boundary_status != "observed":
            return False
        observations = self._recent_observations(source_id, limit=50)
        audit = self._audit.full_audit(source, observations)
        if not audit["overall_passed"]:
            return False
        recommended = self._boundary.evaluate_transition(
            source,
            observation_count=len(observations),
            first_seen=source.last_seen - (3600 * 24),  # conservative estimate
            audit_results={
                "stability": audit["stability"],
                "semantic": audit["semantic"],
                "trust": audit["trust"],
                "identity_drift": audit["identity_drift"],
            },
        )
        if recommended == "trusted":
            self._registry.update_boundary_status(source_id, "trusted")
            return True
        return False

    def request_assimilation(self, source_id: str, approver: str) -> bool:
        """Request human-approved assimilation for a trusted source."""
        source = self._registry.get(source_id)
        if source is None or source.boundary_status != "trusted":
            return False
        observations = self._recent_observations(source_id, limit=50)
        audit = self._audit.full_audit(source, observations)
        if not audit["overall_passed"]:
            return False
        self._boundary.approve_assimilation(source_id, approver)
        recommended = self._boundary.evaluate_transition(
            source,
            observation_count=len(observations),
            first_seen=source.last_seen - (3600 * 24),
            audit_results={
                "stability": audit["stability"],
                "semantic": audit["semantic"],
                "trust": audit["trust"],
                "identity_drift": audit["identity_drift"],
            },
        )
        if recommended == "assimilated":
            self._registry.update_boundary_status(source_id, "assimilated")
            return True
        return False

    def demote_to_observed(self, source_id: str, reviewer: str) -> bool:
        """Emergency demote any source back to observed."""
        source = self._registry.get(source_id)
        if source is None:
            return False
        self._boundary.revoke_assimilation(source_id, reviewer)
        self._registry.update_boundary_status(source_id, "observed")
        return True

    def boundary_summary(self) -> Dict[str, Any]:
        """Return boundary layer summary."""
        return {
            "boundary_layer": self._boundary.summary(),
            "sources_by_status": {
                "observed": len([s for s in self._registry.list_sources() if s.boundary_status == "observed"]),
                "trusted": len([s for s in self._registry.list_sources() if s.boundary_status == "trusted"]),
                "assimilated": len([s for s in self._registry.list_sources() if s.boundary_status == "assimilated"]),
            },
        }
