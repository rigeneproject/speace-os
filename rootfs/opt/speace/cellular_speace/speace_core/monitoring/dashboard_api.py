"""DashboardAPI — FastAPI application for SPEACE Local Organism Monitor.

Serves read-only HTTP endpoints and WebSocket live updates.
"""

import asyncio
import json
import os
import secrets
import time
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

from speace_core.cli import SPEACE_VERSION
from speace_core.monitoring.alert_engine import AlertEngine
from speace_core.monitoring.anomaly_panel import AnomalyPanel
from speace_core.monitoring.human_approval_gate import HumanApprovalGate
from speace_core.monitoring.longitudinal_memory import LongitudinalMemory
from speace_core.monitoring.metrics_bus import MetricsBus
from speace_core.monitoring.organism_state_collector import OrganismStateCollector
from speace_core.cellular_brain.language.dialogue_manager import DialogueManager
from speace_core.cellular_brain.language.linguistic_cortical_bridge import LinguisticCorticalBridge
from speace_core.monitoring.multi_node_aggregator import MultiNodeAggregator
from speace_core.monitoring.regulation_proposal_builder import RegulationProposalBuilder
from speace_core.monitoring.safety_status import SafetyStatus
from speace_core.monitoring.websocket_server import create_websocket_router
from speace_core.cellular_brain.experience.relational_memory import RelationalMemory
from speace_core.cellular_brain.experience.temporal_narrative_engine import TemporalNarrativeEngine
from speace_core.cellular_brain.experience.session_continuity_manager import SessionContinuityManager
from speace_core.cellular_brain.experience.adaptive_preference_model import AdaptivePreferenceModel
from speace_core.cellular_brain.experience.experiential_snapshot_store import ExperientialSnapshotStore
from speace_core.cellular_brain.metacognition.metacognitive_monitor import MetacognitiveMonitor
from speace_core.ecosystem.ecosystem_actuator import EcosystemActuator
from speace_core.ecosystem.observation_layer import EcosystemObservationLayer
from speace_core.dna.parser import load_genome
from speace_core.orchestrator import CellularBrainOrchestrator
from speace_core.runtime.continuous_runtime_engine import ContinuousRuntimeEngine

from contextlib import asynccontextmanager

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from fastapi.staticfiles import StaticFiles

    _HAS_FASTAPI = True
except Exception:  # pragma: no cover
    _HAS_FASTAPI = False
    FastAPI = Any  # type: ignore[misc,assignment]
    Request = Any  # type: ignore[misc,assignment]
    JSONResponse = Any  # type: ignore[misc,assignment]
    StaticFiles = Any  # type: ignore[misc,assignment]

# --------------------------------------------------------------------------- #
# Bootstrap
# --------------------------------------------------------------------------- #
_start_time = time.time()

_data_root = Path("data")
_collector = OrganismStateCollector(data_root=str(_data_root))
_safety = SafetyStatus(data_root=str(_data_root))
_anomaly = AnomalyPanel()
_alert_engine = AlertEngine()
_longitudinal_memory = LongitudinalMemory(health_score_func=_alert_engine.health_score)
_regulation_builder = RegulationProposalBuilder()
_approval_gate = HumanApprovalGate(builder=_regulation_builder)
_multi_node_aggregator = MultiNodeAggregator()
_linguistic_bridge = LinguisticCorticalBridge(language="it")
_dialogue_manager = DialogueManager(linguistic_bridge=_linguistic_bridge)

# T108 — Persistent Experiential Continuity
_relational_memory = RelationalMemory()
_narrative_engine = TemporalNarrativeEngine()
_session_continuity = SessionContinuityManager()
_preference_model = AdaptivePreferenceModel()
_experiential_snapshot_store = ExperientialSnapshotStore()

# T109 — Controlled Continuous Runtime (optional, lazy-init)
_runtime_engine: Any = None
# Guards concurrent /api/runtime/start requests so a second caller cannot
# build a second engine while the first is still in flight, and ensures
# partial state is cleaned up if start() raises.
_runtime_start_lock: Optional[asyncio.Lock] = None


def _get_runtime_start_lock() -> asyncio.Lock:
    global _runtime_start_lock
    if _runtime_start_lock is None:
        _runtime_start_lock = asyncio.Lock()
    return _runtime_start_lock

# T127 — Metacognitive Monitoring Layer
_metacognitive_monitor = MetacognitiveMonitor()

# T131-A — Ecosystem Observation Layer
_ecosystem_layer = EcosystemObservationLayer()

# T131-E — Controlled Ecosystem Interaction (stubbed by default)
_ecosystem_actuator = EcosystemActuator(allow_execution=False)

# Load genome thresholds if available
_genome_path = Path(__file__).resolve().parent.parent / "dna" / "genome" / "monitoring_dashboard.yaml"
if _genome_path.exists():
    try:
        import yaml

        _cfg = yaml.safe_load(_genome_path.read_text(encoding="utf-8"))
        _md = _cfg.get("monitoring_dashboard", {})
        _thresh = _md.get("anomaly_thresholds", {})
        if _thresh:
            _anomaly = AnomalyPanel(
                coherence_phi_min=_thresh.get("coherence_phi_min", 0.1),
                energy_min=_thresh.get("energy_min", 0.2),
                severity_max=_thresh.get("severity_max", 2.0),
                branching_ratio_deviation=_thresh.get("branching_ratio_deviation", 0.3),
            )
        _alert_thresh = _md.get("alert_thresholds", {})
        if _alert_thresh:
            _alert_engine = AlertEngine(thresholds=_alert_thresh)
    except Exception:
        pass

def _post_process(state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        state["anomaly_panel"] = _anomaly.analyze(state)
    except Exception:
        state["anomaly_panel"] = {"anomalies": [], "overall_status": "unknown", "anomaly_count": 0}
    try:
        alerts = _alert_engine.evaluate(state)
        state["alert_engine"] = {
            "alerts": alerts,
            "recent_alerts": _alert_engine.recent_alerts(limit=20),
            "health_score": _alert_engine.health_score(state),
        }
        # T104: build regulation proposals from critical/warning alerts
        try:
            proposals = _regulation_builder.build_from_alerts(alerts, state)
            state["regulation_proposals"] = {
                "pending_count": len([p for p in proposals if p.get("status") == "pending"]),
                "latest": proposals[:5],
            }
        except Exception:
            state["regulation_proposals"] = {"pending_count": 0, "latest": []}
    except Exception:
        state["alert_engine"] = {"alerts": [], "recent_alerts": [], "health_score": 0.0}
        state["regulation_proposals"] = {"pending_count": 0, "latest": []}
    try:
        _longitudinal_memory.record(state)
    except Exception:
        pass
    # T127: attach metacognitive snapshot
    try:
        state["meta_state"] = _metacognitive_monitor.generate_meta_state(state).model_dump(mode="json")
    except Exception:
        state["meta_state"] = None
    return state


_metrics_bus = MetricsBus(collector=_collector, interval_ms=1000.0, post_process=_post_process)

_static_dir = Path(__file__).resolve().parent.parent.parent / "web" / "dashboard"
if not _static_dir.exists():
    # Fallback for editable installs where cwd might differ
    _static_dir = Path("web") / "dashboard"

# --------------------------------------------------------------------------- #
# Guard
# --------------------------------------------------------------------------- #
if not _HAS_FASTAPI:
    raise ImportError(
        "FastAPI / Uvicorn are not installed.\n"
        "Install with: pip install \"speace-core[monitoring]\"\n"
        "or:          pip install fastapi uvicorn websockets"
    )

# --------------------------------------------------------------------------- #
# Lifecycle
# --------------------------------------------------------------------------- #


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    _metrics_bus.start()
    global _runtime_engine
    if _runtime_engine is None:
        try:
            _runtime_engine = _build_runtime_from_genome()
            await _runtime_engine.start()
        except Exception as exc:
            warnings.warn(f"Runtime auto-start failed: {exc}", stacklevel=2)
    yield
    if _runtime_engine is not None:
        try:
            await _runtime_engine.stop()
        except Exception:
            pass
    _metrics_bus.stop()


app = FastAPI(
    title="SPEACE Local Organism Monitor",
    description="T101 — Read-only organismic monitoring dashboard",
    version=SPEACE_VERSION,
    lifespan=_lifespan,
)

# --------------------------------------------------------------------------- #
# Local-auth guard for POST endpoints that mutate state
# --------------------------------------------------------------------------- #
_SENSITIVE_POST_PATHS: tuple[str, ...] = (
    "/api/runtime/start",
    "/api/runtime/control",
    "/api/regulation/approve",
    "/api/regulation/reject",
    "/api/dialogue/message",
    "/api/dialogue/speak",
    "/api/experience/snapshot",
    "/api/dialogue/evolution/approve",
    "/api/dialogue/evolution/reject",
    "/api/simulation/run",
    "/api/micro_actuator/propose",
    "/api/micro_actuator/approve",
    "/api/distributed_organism/node/register",
    "/api/distributed_organism/node/unregister",
    "/api/distributed_organism/action/propose",
)

_LOCAL_TOKEN = os.environ.get("SPEACE_LOCAL_TOKEN")
if not _LOCAL_TOKEN:
    _LOCAL_TOKEN = secrets.token_urlsafe(16)
    warnings.warn(
        f"SPEACE_LOCAL_TOKEN not set. Generated temporary token: {_LOCAL_TOKEN}",
        stacklevel=2,
    )


@app.middleware("http")
async def local_auth_middleware(request: Request, call_next: Any) -> Any:
    if request.method == "POST":
        for prefix in _SENSITIVE_POST_PATHS:
            if request.url.path.startswith(prefix):
                if getattr(request.app.state, "_testing", False):
                    break
                token = request.headers.get("x-local-token", "")
                if token != _LOCAL_TOKEN:
                    return JSONResponse(
                        {"error": "unauthorized", "detail": "x-local-token required"},
                        status_code=403,
                    )
                break
    return await call_next(request)


# --------------------------------------------------------------------------- #
# API — read-only granular endpoints
# --------------------------------------------------------------------------- #


@app.get("/api/health")
async def api_health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "uptime_seconds": int(time.time() - _start_time),
        "speace_version": SPEACE_VERSION,
    }


@app.get("/api/state")
async def api_state() -> Dict[str, Any]:
    state = _metrics_bus.latest()
    if not state:
        state = _collector.collect_all()
        state["timestamp"] = time.time()
    if "alert_engine" not in state:
        try:
            alerts = _alert_engine.evaluate(state)
            state["alert_engine"] = {
                "alerts": alerts,
                "recent_alerts": _alert_engine.recent_alerts(limit=20),
                "health_score": _alert_engine.health_score(state),
            }
        except Exception:
            state["alert_engine"] = {"alerts": [], "recent_alerts": [], "health_score": 0.0}
    anomalies = _anomaly.analyze(state)
    return {
        **state,
        "anomaly_panel": anomalies,
    }


@app.get("/api/body")
async def api_body() -> Dict[str, Any]:
    return _collector.collect_body()


@app.get("/api/cognition")
async def api_cognition() -> Dict[str, Any]:
    return _collector.collect_cognition()


@app.get("/api/dynamics")
async def api_dynamics() -> Dict[str, Any]:
    return _collector.collect_dynamics()


@app.get("/api/identity")
async def api_identity() -> Dict[str, Any]:
    return _collector.collect_identity()


@app.get("/api/drives")
async def api_drives() -> Dict[str, Any]:
    return _collector.collect_drives()


@app.get("/api/safety")
async def api_safety() -> Dict[str, Any]:
    safety = _safety.evaluate()
    safety["governance_mode"] = "observation_only"
    safety["allow_actuator_commands"] = False
    return safety


# --------------------------------------------------------------------------- #
# T102 — Alerts and Health Score
# --------------------------------------------------------------------------- #


@app.get("/api/alerts")
async def api_alerts(limit: int = 20) -> Dict[str, Any]:
    state = _metrics_bus.latest()
    if not state:
        state = _collector.collect_all()
        state["timestamp"] = time.time()
    alerts = _alert_engine.evaluate(state)
    recent = _alert_engine.recent_alerts(limit=limit)
    return {
        "alerts": alerts,
        "recent_alerts": recent,
        "health_score": _alert_engine.health_score(state),
        "timestamp": time.time(),
    }


@app.get("/api/health_score")
async def api_health_score() -> Dict[str, Any]:
    state = _metrics_bus.latest()
    if not state:
        state = _collector.collect_all()
        state["timestamp"] = time.time()
    return {
        "health_score": _alert_engine.health_score(state),
        "timestamp": time.time(),
    }


# --------------------------------------------------------------------------- #
# T103 — Observer Report
# --------------------------------------------------------------------------- #

@app.get("/api/report")
async def api_report(lookback: int = 24) -> Dict[str, Any]:
    from speace_core.monitoring.observer_report_generator import ObserverReportGenerator

    generator = ObserverReportGenerator()
    report = generator.generate(lookback_hours=lookback)
    return report.model_dump(mode="json")


# --------------------------------------------------------------------------- #
# T105 — Longitudinal Memory
# --------------------------------------------------------------------------- #

@app.get("/api/history/snapshot")
async def api_history_snapshot(hours: int = 24, limit: int = 100) -> Dict[str, Any]:
    now = time.time()
    cutoff = now - (hours * 3600)
    snapshots: List[Dict[str, Any]] = []
    path = _longitudinal_memory.history_path
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if entry.get("timestamp", 0) >= cutoff:
                        snapshots.append(entry)
        except OSError:
            pass
    if limit:
        snapshots = snapshots[-limit:]
    return {"hours": hours, "snapshots": snapshots}


@app.get("/api/history/{metric}")
async def api_history(metric: str, hours: int = 24, limit: int = 100) -> Dict[str, Any]:
    data = _longitudinal_memory.get_history(metric, hours=hours, limit=limit)
    return {"metric": metric, "hours": hours, "data": data}


@app.get("/api/history/trend/{metric}")
async def api_history_trend(metric: str, hours: int = 24) -> Dict[str, Any]:
    trend = _longitudinal_memory.get_trend(metric, hours=hours)
    return {"metric": metric, "hours": hours, **trend}


# --------------------------------------------------------------------------- #
# T104 — Regulation Proposals
# --------------------------------------------------------------------------- #

@app.get("/api/regulation/proposals")
async def api_regulation_proposals(status: str = "pending", limit: int = 100) -> Dict[str, Any]:
    proposals = _approval_gate.list_pending(limit=limit) if status == "pending" else _approval_gate.list_all(limit=limit)
    return {"status": status, "count": len(proposals), "proposals": proposals}


@app.post("/api/regulation/approve/{proposal_id}")
async def api_regulation_approve(proposal_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    reviewer = body.get("reviewer", "anonymous")
    health = _alert_engine.health_score(_metrics_bus.latest() or {})
    result = _approval_gate.approve(proposal_id, reviewer=reviewer, current_health=health)
    return result


@app.post("/api/regulation/reject/{proposal_id}")
async def api_regulation_reject(proposal_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    reviewer = body.get("reviewer", "anonymous")
    result = _approval_gate.reject(proposal_id, reviewer=reviewer)
    return result


# --------------------------------------------------------------------------- #
# T106 — Multi-node Monitoring
# --------------------------------------------------------------------------- #

@app.get("/api/nodes")
async def api_nodes() -> Dict[str, Any]:
    agg = _multi_node_aggregator.aggregate()
    return agg


@app.get("/api/nodes/{node_id}/state")
async def api_node_state(node_id: str) -> Dict[str, Any]:
    return _multi_node_aggregator._states.get(node_id, {"error": "node_not_found"})


@app.get("/api/distributed/divergence")
async def api_distributed_divergence() -> Dict[str, Any]:
    drift = _multi_node_aggregator._compute_personality_drift()
    return {
        "personality_drift": drift,
        "node_count": len(_multi_node_aggregator._states),
    }


# --------------------------------------------------------------------------- #
# T107 — Dialogue
# --------------------------------------------------------------------------- #

@app.post("/api/dialogue/message")
async def api_dialogue_message(body: Dict[str, Any]) -> Dict[str, Any]:
    msg = body.get("message", "")
    if not msg:
        return {"error": "empty_message"}
    runtime_state = _runtime_engine.snapshot() if _runtime_engine is not None else {}
    response = await _dialogue_manager.receive_async(msg, runtime_state=runtime_state)
    return response


@app.get("/api/dialogue/history")
async def api_dialogue_history(limit: int = 20) -> Dict[str, Any]:
    turns = _dialogue_manager.history(limit=limit)
    return {"turns": turns, "state": _dialogue_manager.state}


@app.post("/api/dialogue/speak")
async def api_dialogue_speak() -> Dict[str, Any]:
    result = _dialogue_manager.speak_last_response()
    return result


# --------------------------------------------------------------------------- #
# T145 — Dialogue Evolution Approval Dashboard
# --------------------------------------------------------------------------- #

@app.get("/api/dialogue/evolution/proposals")
async def api_dialogue_evolution_proposals(status: str = "pending", limit: int = 100) -> Dict[str, Any]:
    """List CLA proposals generated by T144."""
    proposals = _dialogue_manager._cla_feedback.list_all_proposals(status=status if status != "all" else None)
    return {"status": status, "count": len(proposals), "proposals": proposals[:limit]}


@app.get("/api/dialogue/evolution/proposals/{proposal_id}")
async def api_dialogue_evolution_proposal_detail(proposal_id: str) -> Dict[str, Any]:
    """Detail of a single CLA proposal."""
    proposal = _dialogue_manager._cla_feedback.get_proposal(proposal_id)
    if proposal is None:
        return {"error": "proposal_not_found"}
    return proposal


@app.post("/api/dialogue/evolution/approve/{proposal_id}")
async def api_dialogue_evolution_approve(proposal_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """Approve and apply a pending CLA proposal."""
    reviewer = body.get("reviewer", "anonymous")
    health = _alert_engine.health_score(_metrics_bus.latest() or {})
    result = _dialogue_manager._cla_feedback.approve_proposal(proposal_id, reviewer=reviewer, current_health=health)
    return result


@app.post("/api/dialogue/evolution/reject/{proposal_id}")
async def api_dialogue_evolution_reject(proposal_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """Reject a pending CLA proposal."""
    reviewer = body.get("reviewer", "anonymous")
    result = _dialogue_manager._cla_feedback.reject_proposal(proposal_id, reviewer=reviewer)
    return result


@app.get("/api/dialogue/evolution/audit")
async def api_dialogue_evolution_audit(hours: float = 24.0, limit: int = 100) -> Dict[str, Any]:
    """Audit log of CLA proposal lifecycle events."""
    events = _dialogue_manager._cla_feedback.audit_log(hours=hours, limit=limit)
    return {"hours": hours, "count": len(events), "events": events}


@app.get("/api/dialogue/evolution/summary")
async def api_dialogue_evolution_summary() -> Dict[str, Any]:
    """Summary of the CLA feedback layer state."""
    return _dialogue_manager._cla_feedback.summary()


# --------------------------------------------------------------------------- #
# T108 — Persistent Experiential Continuity
# --------------------------------------------------------------------------- #

@app.get("/api/experience/state")
async def api_experience_state() -> Dict[str, Any]:
    humans = _relational_memory.list_humans()
    latest_snapshot = _experiential_snapshot_store.latest()
    continuity = _session_continuity.load()
    preferences = _preference_model.summary()
    return {
        "relational_humans": humans,
        "relational_human_count": len(humans),
        "latest_snapshot": latest_snapshot,
        "session_continuity": continuity,
        "preferences": preferences,
        "resume_narrative": _session_continuity.build_resume_narrative(),
    }


@app.get("/api/experience/timeline")
async def api_experience_timeline(hours: float = 168, limit: int = 50) -> Dict[str, Any]:
    events = _narrative_engine.recent(hours=hours, limit=limit)
    summary = _narrative_engine.get_narrative_summary(hours=hours)
    return {
        "events": events,
        "summary": summary,
        "hours": hours,
        "count": len(events),
    }


@app.post("/api/experience/snapshot")
async def api_experience_snapshot(body: Dict[str, Any]) -> Dict[str, Any]:
    state = body.get("state", {})
    human_id = body.get("human_id")
    narrative_position = body.get("narrative_position")
    snapshot = _experiential_snapshot_store.save(
        state=state, human_id=human_id, narrative_position=narrative_position
    )
    return {"snapshot": snapshot}


# --------------------------------------------------------------------------- #
# T109 — Controlled Continuous Runtime
# --------------------------------------------------------------------------- #


def _build_runtime_from_genome(genome_path: Optional[str] = None) -> ContinuousRuntimeEngine:
    if genome_path:
        genome = load_genome(Path(genome_path))
    else:
        default = Path(__file__).resolve().parent.parent / "dna" / "genome" / "default_genome.yaml"
        genome = load_genome(default)
    orchestrator = CellularBrainOrchestrator.build_mvp(genome)
    # Load runtime config from monitoring_dashboard genome if present
    runtime_cfg: Dict[str, Any] = {}
    md_path = Path(__file__).resolve().parent.parent / "dna" / "genome" / "monitoring_dashboard.yaml"
    if md_path.exists():
        try:
            import yaml
            md_cfg = yaml.safe_load(md_path.read_text(encoding="utf-8"))
            runtime_cfg = md_cfg.get("monitoring_dashboard", {}).get("continuous_runtime", {})
        except Exception:
            pass
    return ContinuousRuntimeEngine(
        orchestrator=orchestrator,
        tick_interval=runtime_cfg.get("tick_interval", 1.0),
        checkpoint_interval_seconds=runtime_cfg.get("checkpoint_interval_seconds", 300.0),
        awake_duration=runtime_cfg.get("circadian", {}).get("awake_duration_seconds", 300.0),
        sleep_duration=runtime_cfg.get("circadian", {}).get("sleep_duration_seconds", 60.0),
        runtime_health_config=runtime_cfg.get("runtime_health", {}),
        emergency_halt_config=runtime_cfg.get("emergency_halt", {}),
        degradation_config=runtime_cfg.get("degradation", {}),
    )


@app.post("/api/runtime/start")
async def api_runtime_start(body: Dict[str, Any]) -> Dict[str, Any]:
    global _runtime_engine
    if _runtime_engine is not None:
        return {"error": "runtime_already_running", "state": _runtime_engine.snapshot()}
    lock = _get_runtime_start_lock()
    async with lock:
        # Re-check inside the lock to avoid races between concurrent callers
        if _runtime_engine is not None:
            return {
                "error": "runtime_already_running",
                "state": _runtime_engine.snapshot(),
            }
        genome_path = body.get("genome_path")
        new_engine = _build_runtime_from_genome(genome_path)
        try:
            result = await new_engine.start()
        except Exception as exc:
            # Best-effort cleanup: stop the partial engine so background tasks
            # (sensors, loops) are released. Then clear the global to allow a
            # retry. Swallow secondary errors so the caller still gets the
            # original failure.
            try:
                await new_engine.stop()
            except Exception:
                pass
            return {
                "status": "start_failed",
                "error": str(exc),
                "error_type": type(exc).__name__,
            }
        _runtime_engine = new_engine
        return {"status": "started", **result}


@app.post("/api/runtime/control")
async def api_runtime_control(body: Dict[str, Any]) -> Dict[str, Any]:
    global _runtime_engine
    if _runtime_engine is None:
        return {"error": "runtime_not_running"}
    action = body.get("action", "")
    if action == "pause":
        await _runtime_engine.pause()
    elif action == "resume":
        await _runtime_engine.resume()
    elif action == "halt":
        await _runtime_engine.halt()
    elif action == "checkpoint":
        cp = await _runtime_engine.force_checkpoint()
        return {"status": "checkpoint_forced", "checkpoint": cp}
    else:
        return {"error": "unknown_action", "allowed": ["pause", "resume", "halt", "checkpoint"]}
    return {"status": "ok", "state": _runtime_engine.snapshot()}


@app.get("/api/runtime/state")
async def api_runtime_state() -> Dict[str, Any]:
    if _runtime_engine is None:
        return {"status": "not_running"}
    return _runtime_engine.snapshot()


@app.get("/api/runtime/health")
async def api_runtime_health() -> Dict[str, Any]:
    if _runtime_engine is None:
        return {"status": "not_running"}
    return _runtime_engine.health_monitor.snapshot()


@app.get("/api/runtime/checkpoints")
async def api_runtime_checkpoints(limit: int = 10) -> Dict[str, Any]:
    if _runtime_engine is None:
        return {"checkpoints": []}
    return {"checkpoints": _runtime_engine.checkpoint_manager.list_checkpoints(limit=limit)}


# --------------------------------------------------------------------------- #
# T163 — Organism State Machine
# --------------------------------------------------------------------------- #

@app.get("/api/organism-state")
async def api_organism_state() -> Dict[str, Any]:
    if _runtime_engine is None:
        return {"status": "not_running"}
    return _runtime_engine.organism_state_machine.snapshot()


# --------------------------------------------------------------------------- #
# T164 — Behavior Tree Layer
# --------------------------------------------------------------------------- #

@app.get("/api/behavior_trees")
async def api_behavior_trees() -> Dict[str, Any]:
    if _runtime_engine is None:
        return {"status": "not_running"}
    return _runtime_engine.bt_integration.snapshot()


# --------------------------------------------------------------------------- #
# T165 — Utility AI Layer
# --------------------------------------------------------------------------- #

@app.get("/api/utility_drives")
async def api_utility_drives() -> Dict[str, Any]:
    if _runtime_engine is None:
        return {"status": "not_running"}
    return {
        "drives": _runtime_engine.utility_drive_system.snapshot(),
        "arbitration": _runtime_engine.utility_arbitration.snapshot(),
    }


# --------------------------------------------------------------------------- #
# T166 — GOAP Layer
# --------------------------------------------------------------------------- #

@app.get("/api/goap_plans")
async def api_goap_plans() -> Dict[str, Any]:
    if _runtime_engine is None:
        return {"status": "not_running"}
    return _runtime_engine.goap_integration.snapshot()


# --------------------------------------------------------------------------- #
# T167 — Social Cognition Layer
# --------------------------------------------------------------------------- #

@app.get("/api/social_cognition")
async def api_social_cognition() -> Dict[str, Any]:
    if _runtime_engine is None:
        return {"status": "not_running"}
    return {
        "social_cognition": _runtime_engine.social_cognition.snapshot(),
        "trust_reputation": _runtime_engine.trust_reputation.snapshot(),
        "social_coordinator": _runtime_engine.social_coordinator.snapshot(),
    }


# --------------------------------------------------------------------------- #
# T168 — Simulated Cognitive Nursery
# --------------------------------------------------------------------------- #

@app.get("/api/nursery")
async def api_nursery() -> Dict[str, Any]:
    if _runtime_engine is None:
        return {"status": "not_running"}
    return _runtime_engine.nursery_orchestrator.snapshot()


# --------------------------------------------------------------------------- #
# T169 — Game AI Integration Pipeline
# --------------------------------------------------------------------------- #

@app.get("/api/game_ai_pipeline")
async def api_game_ai_pipeline() -> Dict[str, Any]:
    if _runtime_engine is None:
        return {"status": "not_running"}
    return _runtime_engine.game_ai_coordinator.snapshot()


# --------------------------------------------------------------------------- #
# T170 — Linguistic Cortical Bridge
# --------------------------------------------------------------------------- #

@app.get("/api/linguistic_bridge/state")
async def api_linguistic_bridge_state() -> Dict[str, Any]:
    return _linguistic_bridge.snapshot()


# --------------------------------------------------------------------------- #
# T127 — Metacognitive Monitoring Layer
# --------------------------------------------------------------------------- #

@app.get("/api/metacognition/state")
async def api_metacognition_state() -> Dict[str, Any]:
    state = _metrics_bus.latest()
    if not state:
        state = _collector.collect_all()
        state["timestamp"] = time.time()
    meta = _metacognitive_monitor.generate_meta_state(state)
    return meta.model_dump(mode="json")


@app.get("/api/metacognition/report")
async def api_metacognition_report() -> Dict[str, Any]:
    state = _metrics_bus.latest()
    if not state:
        state = _collector.collect_all()
        state["timestamp"] = time.time()
    meta = _metacognitive_monitor.generate_meta_state(state)
    return {
        "reflective_narrative": meta.reflective_narrative,
        "meta_state_label": meta.meta_state_label,
        "timestamp": time.time(),
    }


# --------------------------------------------------------------------------- #
# T128 — Epistemic Confidence Engine
# --------------------------------------------------------------------------- #

@app.get("/api/metacognition/proposal/{proposal_id}/confidence")
async def api_proposal_confidence(proposal_id: str) -> Dict[str, Any]:
    state = _metrics_bus.latest()
    if not state:
        state = _collector.collect_all()
        state["timestamp"] = time.time()
    proposal = _approval_gate.builder.get_proposal(proposal_id)
    if proposal is None:
        return {"error": "proposal_not_found"}
    confidence = _metacognitive_monitor.confidence_for_proposal(proposal, state)
    return confidence.model_dump(mode="json")


@app.get("/api/metacognition/dialogue/confidence")
async def api_dialogue_confidence() -> Dict[str, Any]:
    state = _metrics_bus.latest()
    if not state:
        state = _collector.collect_all()
        state["timestamp"] = time.time()
    dialogue_state = {"turn_count": _dialogue_manager._turn_count, "state": _dialogue_manager.state}
    confidence = _metacognitive_monitor.confidence_for_dialogue(dialogue_state, state)
    return confidence.model_dump(mode="json")


# --------------------------------------------------------------------------- #
# T130 — Cognitive Strategy Evaluator
# --------------------------------------------------------------------------- #

@app.get("/api/metacognition/strategies")
async def api_metacognition_strategies() -> Dict[str, Any]:
    """List evaluated strategies and their efficacy."""
    return _metacognitive_monitor.evaluate_all_strategies()


@app.get("/api/metacognition/strategies/best")
async def api_metacognition_best_strategy() -> Dict[str, Any]:
    """Return the best-performing strategy."""
    best = _metacognitive_monitor.best_strategy()
    return {"best_strategy": best, "timestamp": time.time()}


# --------------------------------------------------------------------------- #
# T131-A — Ecosystem Observation Layer
# --------------------------------------------------------------------------- #

@app.get("/api/ecosystem/status")
async def api_ecosystem_status() -> Dict[str, Any]:
    """Ecosystem health summary (read-only)."""
    return _ecosystem_layer.health().model_dump(mode="json")


@app.get("/api/ecosystem/sources")
async def api_ecosystem_sources() -> Dict[str, Any]:
    """List all registered ecosystem sources."""
    sources = _ecosystem_layer.list_sources()
    return {
        "sources": [s.model_dump(mode="json") for s in sources],
        "count": len(sources),
        "timestamp": time.time(),
    }


@app.get("/api/ecosystem/sources/{source_id}")
async def api_ecosystem_source_detail(source_id: str) -> Dict[str, Any]:
    """Detail for a single ecosystem source with semantic mapping."""
    detail = _ecosystem_layer.describe_source(source_id)
    if detail is None:
        return {"error": "source_not_found"}
    return detail


@app.get("/api/ecosystem/graph")
async def api_ecosystem_graph() -> Dict[str, Any]:
    """T131-B: ecosystem relational graph summary."""
    summary = _ecosystem_layer.graph_summary()
    if summary is None:
        return {"error": "graph_unavailable"}
    return summary


@app.get("/api/ecosystem/graph/narrative")
async def api_ecosystem_graph_narrative() -> Dict[str, str]:
    """T131-B: reflective narrative of the ecosystem map."""
    return {"narrative": _ecosystem_layer.describe_graph()}


# --------------------------------------------------------------------------- #
# T131-E — Controlled Ecosystem Interaction (stubbed)
# --------------------------------------------------------------------------- #

@app.post("/api/ecosystem/actions/propose")
async def api_ecosystem_action_propose(body: Dict[str, Any]) -> Dict[str, Any]:
    """Propose an ecosystem action."""
    proposal = _ecosystem_actuator.propose(
        source_id=body.get("source_id", ""),
        action_type=body.get("action_type", ""),
        payload=body.get("payload", {}),
        requested_by=body.get("requested_by", ""),
    )
    return proposal.model_dump(mode="json")


@app.get("/api/ecosystem/actions")
async def api_ecosystem_actions_list(
    status: Optional[str] = None,
    source: Optional[str] = None,
) -> Dict[str, Any]:
    """List ecosystem action proposals."""
    proposals = _ecosystem_actuator.list_proposals(status_filter=status, source_filter=source)
    return {
        "proposals": [p.model_dump(mode="json") for p in proposals],
        "count": len(proposals),
    }


@app.get("/api/ecosystem/actions/{proposal_id}")
async def api_ecosystem_action_detail(proposal_id: str) -> Dict[str, Any]:
    """Detail of a single action proposal."""
    proposal = _ecosystem_actuator.get(proposal_id)
    if proposal is None:
        return {"error": "proposal_not_found"}
    return proposal.model_dump(mode="json")


@app.post("/api/ecosystem/actions/{proposal_id}/approve")
async def api_ecosystem_action_approve(proposal_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """Approve a pending ecosystem action proposal."""
    proposal = _ecosystem_actuator.approve(proposal_id, approver=body.get("approver", ""))
    if proposal is None:
        return {"error": "proposal_not_found_or_not_pending"}
    return proposal.model_dump(mode="json")


@app.post("/api/ecosystem/actions/{proposal_id}/reject")
async def api_ecosystem_action_reject(proposal_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """Reject a pending ecosystem action proposal."""
    proposal = _ecosystem_actuator.reject(proposal_id, reviewer=body.get("reviewer", ""))
    if proposal is None:
        return {"error": "proposal_not_found_or_not_pending"}
    return proposal.model_dump(mode="json")


@app.post("/api/ecosystem/actions/{proposal_id}/execute")
async def api_ecosystem_action_execute(proposal_id: str) -> Dict[str, Any]:
    """Execute an approved ecosystem action proposal (stubbed by default)."""
    proposal = _ecosystem_actuator.execute(proposal_id)
    if proposal is None:
        return {"error": "proposal_not_found_or_not_approved"}
    return proposal.model_dump(mode="json")


# --------------------------------------------------------------------------- #
# T147 — Embodied Sensory Stream
# --------------------------------------------------------------------------- #

@app.get("/api/embodiment/sensors")
async def api_embodiment_sensors() -> Dict[str, Any]:
    """Return latest cyber-physical sensor snapshot from the runtime orchestrator."""
    snapshot = None
    if _runtime_engine is not None:
        orch = _runtime_engine.orchestrator
        if orch.embodiment_enabled and orch._last_sensor_snapshot is not None:
            snapshot = orch._last_sensor_snapshot
    return {
        "runtime_running": _runtime_engine is not None,
        "embodiment_enabled": (
            _runtime_engine.orchestrator.embodiment_enabled if _runtime_engine is not None else False
        ),
        "snapshot": snapshot,
        "timestamp": time.time(),
    }


# --------------------------------------------------------------------------- #
# Phase 2 — Simulated Embodiment
# --------------------------------------------------------------------------- #

@app.get("/api/simulation/status")
async def api_simulation_status() -> Dict[str, Any]:
    """Return current digital twin and simulated environment status."""
    if _runtime_engine is None:
        return {"runtime_running": False}
    return {
        "runtime_running": True,
        "has_digital_twin": _runtime_engine._digital_twin is not None,
        "has_simulated_environment": _runtime_engine._simulated_environment is not None,
        "twin_summary": _runtime_engine._digital_twin.summary() if _runtime_engine._digital_twin else None,
        "timestamp": time.time(),
    }


@app.get("/api/simulation/experiments")
async def api_simulation_experiments(limit: int = 20) -> Dict[str, Any]:
    """List recent sandboxed experiment results."""
    if _runtime_engine is None or _runtime_engine._simulated_environment is None:
        return {"experiments": [], "count": 0}
    experiments = _runtime_engine._simulated_environment.list_experiments(limit=limit)
    return {"experiments": experiments, "count": len(experiments)}


@app.post("/api/simulation/run")
async def api_simulation_run(body: Dict[str, Any]) -> Dict[str, Any]:
    """Run a single sandboxed experiment (simulation only, no physical action)."""
    if _runtime_engine is None or _runtime_engine._simulated_environment is None:
        return {"error": "simulation_not_available"}
    experiment_type = body.get("experiment_type", "perturbation")
    params = body.get("params", {})
    result = _runtime_engine._simulated_environment.run_experiment(experiment_type, params)
    return result


@app.get("/api/simulation/summary")
async def api_simulation_summary() -> Dict[str, Any]:
    """Summary of all sandboxed experiments."""
    if _runtime_engine is None or _runtime_engine._simulated_environment is None:
        return {"error": "simulation_not_available"}
    return _runtime_engine._simulated_environment.summary()


# --------------------------------------------------------------------------- #
# Phase 3 — Limited Physical Embodiment (Micro Actuator)
# --------------------------------------------------------------------------- #

@app.get("/api/micro_actuator/status")
async def api_micro_actuator_status() -> Dict[str, Any]:
    """Return micro-actuator controller status."""
    if _runtime_engine is None or _runtime_engine._micro_actuator is None:
        return {"available": False}
    return {
        "available": True,
        "summary": _runtime_engine._micro_actuator.summary(),
    }


@app.post("/api/micro_actuator/propose")
async def api_micro_actuator_propose(body: Dict[str, Any]) -> Dict[str, Any]:
    """Propose a micro-actuation action."""
    if _runtime_engine is None or _runtime_engine._micro_actuator is None:
        return {"error": "micro_actuator_not_available"}
    action_type = body.get("action_type", "")
    params = body.get("params", {})
    proposal_id = _runtime_engine._micro_actuator.propose_action(action_type, params)
    return {
        "proposal_id": proposal_id,
        "status": _runtime_engine._micro_actuator.get_proposal_status(proposal_id),
    }


@app.post("/api/micro_actuator/approve/{proposal_id}")
async def api_micro_actuator_approve(proposal_id: str) -> Dict[str, Any]:
    """Approve and execute a pending micro-actuation proposal."""
    if _runtime_engine is None or _runtime_engine._micro_actuator is None:
        return {"error": "micro_actuator_not_available"}
    return _runtime_engine._micro_actuator.approve_action(proposal_id)


@app.get("/api/micro_actuator/history")
async def api_micro_actuator_history(limit: int = 50) -> Dict[str, Any]:
    """Return micro-actuator action history."""
    if _runtime_engine is None or _runtime_engine._micro_actuator is None:
        return {"history": [], "count": 0}
    history = _runtime_engine._micro_actuator.get_action_history()
    if limit:
        history = history[-limit:]
    return {"history": history, "count": len(history)}


# --------------------------------------------------------------------------- #
# Phase 4 — Distributed Mature Organism
# --------------------------------------------------------------------------- #

@app.get("/api/distributed_organism/status")
async def api_distributed_organism_status() -> Dict[str, Any]:
    """Return distributed organism controller status."""
    if _runtime_engine is None or _runtime_engine._distributed_organism is None:
        return {"available": False}
    return {
        "available": True,
        "summary": _runtime_engine._distributed_organism.summary(),
    }


@app.post("/api/distributed_organism/node/register")
async def api_distributed_organism_register_node(body: Dict[str, Any]) -> Dict[str, Any]:
    """Register a node in the distributed organism."""
    if _runtime_engine is None or _runtime_engine._distributed_organism is None:
        return {"error": "distributed_organism_not_available"}
    node_id = body.get("node_id", "")
    node_type = body.get("node_type", "generic")
    capabilities = body.get("capabilities", {})
    health_score = body.get("health_score", 1.0)
    _runtime_engine._distributed_organism.register_node(
        node_id=node_id,
        node_type=node_type,
        capabilities=capabilities,
        health_score=health_score,
    )
    return {"success": True, "node_id": node_id}


@app.post("/api/distributed_organism/node/unregister/{node_id}")
async def api_distributed_organism_unregister_node(node_id: str) -> Dict[str, Any]:
    """Unregister a node from the distributed organism."""
    if _runtime_engine is None or _runtime_engine._distributed_organism is None:
        return {"error": "distributed_organism_not_available"}
    result = _runtime_engine._distributed_organism.unregister_node(node_id)
    return {"success": result, "node_id": node_id}


@app.get("/api/distributed_organism/nodes")
async def api_distributed_organism_nodes() -> Dict[str, Any]:
    """List all registered nodes."""
    if _runtime_engine is None or _runtime_engine._distributed_organism is None:
        return {"nodes": [], "count": 0}
    nodes = _runtime_engine._distributed_organism.list_nodes()
    return {"nodes": nodes, "count": len(nodes)}


@app.get("/api/distributed_organism/state")
async def api_distributed_organism_state() -> Dict[str, Any]:
    """Observe the current distributed organism state."""
    if _runtime_engine is None or _runtime_engine._distributed_organism is None:
        return {"error": "distributed_organism_not_available"}
    return _runtime_engine._distributed_organism.observe_distributed_state()


@app.post("/api/distributed_organism/action/propose")
async def api_distributed_organism_propose(body: Dict[str, Any]) -> Dict[str, Any]:
    """Propose a distributed physical action (blocked by default)."""
    if _runtime_engine is None or _runtime_engine._distributed_organism is None:
        return {"error": "distributed_organism_not_available"}
    proposal_id = _runtime_engine._distributed_organism.propose_distributed_action(body)
    return {
        "proposal_id": proposal_id,
        "status": _runtime_engine._distributed_organism._proposals.get(proposal_id, {}).get("status", "unknown"),
    }


@app.get("/api/distributed_organism/history")
async def api_distributed_organism_history(limit: int = 50) -> Dict[str, Any]:
    """Return distributed organism action history."""
    if _runtime_engine is None or _runtime_engine._distributed_organism is None:
        return {"history": [], "count": 0}
    history = _runtime_engine._distributed_organism.get_action_history()
    if limit:
        history = history[-limit:]
    return {"history": history, "count": len(history)}


# --------------------------------------------------------------------------- #
# T162 — Cognitive Integration & Systemic Harmony
# --------------------------------------------------------------------------- #

@app.get("/api/harmony/state")
async def api_harmony_state() -> Dict[str, Any]:
    """Return latest systemic harmony snapshot."""
    if _runtime_engine is None:
        return {"runtime_running": False, "harmony": None}
    orch = _runtime_engine.orchestrator
    layer = getattr(orch, "_systemic_harmony_layer", None)
    if layer is None:
        return {
            "runtime_running": True,
            "systemic_harmony_enabled": getattr(orch, "systemic_harmony_enabled", False),
            "harmony": None,
        }
    return {
        "runtime_running": True,
        "systemic_harmony_enabled": True,
        "harmony": layer.to_state_dict(),
        "timestamp": time.time(),
    }


# --------------------------------------------------------------------------- #
# WebSocket
# --------------------------------------------------------------------------- #

app.include_router(create_websocket_router(_metrics_bus))

# --------------------------------------------------------------------------- #
# T120 — Mobile Companion Node
# --------------------------------------------------------------------------- #

try:
    from speace_core.mobile.mobile_api import router as _mobile_router
    app.include_router(_mobile_router)
except Exception:
    pass

# --------------------------------------------------------------------------- #
# Static frontend (mounted last so API routes take precedence)
# --------------------------------------------------------------------------- #

if _static_dir.exists():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="dashboard")
