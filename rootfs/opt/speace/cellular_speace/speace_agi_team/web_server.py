"""SPEACE AGI Team — FastAPI web server for agent management & chat."""

import sys
import io

# Forza UTF-8 su Windows per output con caratteri italiani
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from contextlib import asynccontextmanager
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
except ImportError as exc:
    raise SystemExit(
        "FastAPI is not installed.\n"
        "Install it with: pip install fastapi uvicorn websockets"
    ) from exc

from speace_agi_team.config import AgentConfig, register_agent, AGENT_REGISTRY
from speace_agi_team.agent_base import AgentBase
from speace_agi_team.supervisor_agents import (
    ChiefArchitect, BrainSupervisor, DNASupervisor,
    OrganismSupervisor, MemorySupervisor, SelfImprovementSupervisor,
    EmbodiedCognitionSupervisor, AdvancedLanguageSupervisor,
    LongTermPlanningSupervisor, SelfAwarenessSupervisor,
    register_supervisors,
)
from speace_agi_team.technical_agents import (
    NeuronTechnician, SynapseTechnician, RegionTechnician,
    GenomeTechnician, RuntimeTechnician, DefenseTechnician,
    MemoryTechnician, EvolutionTechnician, NetworkTechnician,
    EmbodimentTechnician, register_technicians,
)
from speace_agi_team.engineering_plan import EngineeringPlan
from speace_agi_team.orchestrator import Orchestrator, get_orchestrator, LoadBalancer
from speace_agi_team.web_search import DocumentFetcher, WebSearcher, research


# ── Lifespan ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    config = AgentConfig()
    _build_agents(config)
    # Start orchestrator: auto-analysis, health monitor, load balancer
    global _orchestrator
    _orchestrator = get_orchestrator(_agents, _plan)
    _orchestrator.start()
    print(f"[AGI Team] {len(_agents)} agenti inizializzati con modello {config.model}")
    print(f"[AGI Team] Orchestrator avviato — auto-analisi e monitor attivi")
    yield
    if _orchestrator:
        _orchestrator.stop()


app = FastAPI(title="SPEACE AGI Team", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# ── Pydantic request/response models ─────────────────────────────────────
class ChatRequest(BaseModel):
    message: str = ""


class BroadcastRequest(BaseModel):
    message: str = ""


class TaskRequest(BaseModel):
    title: str = "Untitled"
    description: str = ""
    agent_id: str = "chief_architect"
    milestone_id: str = ""
    priority: str = "medium"


class CompleteTaskRequest(BaseModel):
    outcome: str = "success"


class MilestoneRequest(BaseModel):
    progress: float = 0.0
    status: Optional[str] = None


class ExecuteTaskRequest(BaseModel):
    task_id: Optional[str] = None
    title: str = "Untitled"
    description: str = ""
    agent_id: str = "auto"
    milestone_id: str = ""
    priority: str = "medium"


class AnalyzeAllRequest(BaseModel):
    sample: bool = False  # If True, run only on supervisors


class WebSearchRequest(BaseModel):
    query: str
    max_results: int = 5


class FetchRequest(BaseModel):
    url: str


class ResearchRequest(BaseModel):
    query: str
    max_results: int = 5
    fetch_top: int = 2
    fetch_max_chars: int = 6000


class AgentResearchRequest(BaseModel):
    query: str
    max_results: int = 5
    fetch_top: int = 2
    fetch_max_chars: int = 6000
    synthesis: bool = True  # If True, have the agent synthesize the results


# ── Agent Singleton Registry ─────────────────────────────────────────────
_agents: Dict[str, AgentBase] = {}
_plan = EngineeringPlan()
_ws_connections: List[WebSocket] = []
_orchestrator: Optional[Orchestrator] = None


def _build_agents(config: AgentConfig):
    global _agents
    supervisors = {
        "chief_architect": ChiefArchitect(config),
        "brain_supervisor": BrainSupervisor(config),
        "dna_supervisor": DNASupervisor(config),
        "organism_supervisor": OrganismSupervisor(config),
        "memory_supervisor": MemorySupervisor(config),
        "selfimprovement_supervisor": SelfImprovementSupervisor(config),
        "embodied_cognition_supervisor": EmbodiedCognitionSupervisor(config),
        "advanced_language_supervisor": AdvancedLanguageSupervisor(config),
        "longterm_planning_supervisor": LongTermPlanningSupervisor(config),
        "self_awareness_supervisor": SelfAwarenessSupervisor(config),
    }
    technicians = {
        "neuron_tech": NeuronTechnician(config),
        "synapse_tech": SynapseTechnician(config),
        "region_tech": RegionTechnician(config),
        "genome_tech": GenomeTechnician(config),
        "runtime_tech": RuntimeTechnician(config),
        "defense_tech": DefenseTechnician(config),
        "memory_tech": MemoryTechnician(config),
        "evolution_tech": EvolutionTechnician(config),
        "network_tech": NetworkTechnician(config),
        "embodiment_tech": EmbodimentTechnician(config),
    }
    _agents = {**supervisors, **technicians}

    register_supervisors()
    register_technicians()


def _get_speace_context() -> Dict[str, Any]:
    """Read live SPEACE state from data files.

    Primary source: live_context.json (written by integrated_speace_main brain_loop).
    Fallback: morphological snapshots + embodiment files.
    """
    ctx = {}

    # ── Primary: live context from brain loop ────────────────────────
    live_path = Path("data/agi_team/live_context.json")
    if live_path.exists():
        try:
            ctx = json.loads(live_path.read_text(encoding="utf-8"))
            return ctx  # Brain loop context is authoritative
        except (json.JSONDecodeError, OSError):
            pass

    # ── Fallback: morphological snapshots ────────────────────────────
    data_root = Path("data")

    # Morphological snapshots
    snap_path = data_root / "morphological_memory" / "snapshots.jsonl"
    if snap_path.exists():
        try:
            lines = snap_path.read_text(encoding="utf-8").strip().split("\n")
            if lines:
                last = json.loads(lines[-1])
                ctx["coherence_phi"] = last.get("coherence_phi", 0)
                ctx["mean_energy"] = last.get("average_energy", 0)
                ctx["active_neurons"] = last.get("active_synapse_count", 0)
                ctx["tick"] = last.get("tick", 0)
        except (json.JSONDecodeError, OSError):
            pass

    # Embodiment
    emb_path = data_root / "embodiment" / "environment_state.jsonl"
    if emb_path.exists():
        try:
            lines = emb_path.read_text(encoding="utf-8").strip().split("\n")
            if lines:
                last = json.loads(lines[-1])
                state = last.get("state", {})
                ctx["cpu"] = state.get("cpu_avg", 0)
                ctx["memory"] = state.get("mem_used", 0)
                ctx["disk"] = state.get("disk_used", 0)
                ctx["temperature"] = state.get("temp_avg", 0)
        except (json.JSONDecodeError, OSError):
            pass

    # Genoma
    ctx["speace_version"] = "0.9.0"
    ctx["cell_types"] = ["digital_neuron", "auditory", "broca", "wernicke",
                          "semantic_pointer", "astrocyte", "microglia", "oligodendrocyte",
                          "sensor", "actuator", "energy"]
    ctx["brain_regions"] = ["sensory", "limbic", "hippocampus", "default_mode",
                             "prefrontal", "cerebellar", "motor", "brainstem_homeostatic"]

    if not ctx:
        ctx["status"] = "no_data"
        ctx["message"] = "SPEACE data not available. Start SPEACE runtime first."

    return ctx


async def _broadcast(msg: Dict):
    dead = []
    for ws in _ws_connections:
        try:
            await ws.send_json(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_connections.remove(ws)


# ── REST API ─────────────────────────────────────────────────────────────

@app.get("/api/status")
def api_status():
    return {
        "status": "online",
        "agents_count": len(_agents),
        "plan_progress": _plan.overall_progress(),
        "model": AgentConfig().model,
    }


@app.get("/api/agents")
def api_list_agents(type_filter: Optional[str] = None):
    result = []
    for aid, agent in _agents.items():
        s = agent.get_status_summary()
        if type_filter and s.get("role") and type_filter not in str(s.get("role")).lower():
            continue
        result.append(s)
    return {"agents": result}


@app.get("/api/agents/{agent_id}")
def api_agent_detail(agent_id: str):
    agent = _agents.get(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent {agent_id} not found")
    return agent.get_status_summary()


@app.get("/api/agents/{agent_id}/conversation")
def api_agent_conversation(agent_id: str):
    agent = _agents.get(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent {agent_id} not found")
    return {"conversation": agent.get_conversation()}


@app.post("/api/agents/{agent_id}/chat")
async def api_agent_chat(agent_id: str, body: ChatRequest):
    agent = _agents.get(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent {agent_id} not found")
    message = body.message
    if not message:
        raise HTTPException(400, "Message is required")
    response = agent.chat(message)
    await _broadcast({
        "type": "agent_chat",
        "agent_id": agent_id,
        "message": message,
        "response": response,
    })
    return {"response": response}


@app.post("/api/agents/{agent_id}/analyze")
async def api_agent_analyze(agent_id: str):
    agent = _agents.get(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent {agent_id} not found")
    context = _get_speace_context()
    finding = agent.analyze(context)
    await _broadcast({
        "type": "agent_analysis",
        "agent_id": agent_id,
        "finding": finding,
    })
    return finding


@app.post("/api/agents/{agent_id}/clear")
def api_agent_clear(agent_id: str):
    agent = _agents.get(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent {agent_id} not found")
    agent.clear_conversation()
    return {"status": "cleared"}


# ── All-Agent Broadcast ──────────────────────────────────────────────────
@app.post("/api/broadcast")
async def api_broadcast(body: BroadcastRequest):
    message = body.message
    if not message:
        raise HTTPException(400, "Message is required")
    responses = {}
    for aid, agent in _agents.items():
        resp = agent.chat(message)
        responses[aid] = resp
    await _broadcast({
        "type": "broadcast",
        "message": message,
        "responses": responses,
    })
    return {"responses": responses}


# ── SPEACE Context ───────────────────────────────────────────────────────
@app.get("/api/speace/context")
def api_speace_context():
    return _get_speace_context()


# ── Engineering Plan ─────────────────────────────────────────────────────
@app.get("/api/plan")
def api_get_plan():
    return _plan.get_milestone_progress_report()


@app.get("/api/plan/tasks")
def api_list_tasks():
    return {"tasks": _plan.tasks}


@app.post("/api/plan/task")
async def api_add_task(body: TaskRequest):
    task = _plan.add_task(
        title=body.title,
        description=body.description,
        agent_id=body.agent_id,
        milestone_id=body.milestone_id,
        priority=body.priority,
    )
    await _broadcast({"type": "plan_task_added", "task": task})
    return task


@app.post("/api/plan/task/{task_id}/complete")
async def api_complete_task(task_id: str, body: CompleteTaskRequest):
    outcome = body.outcome
    success = _plan.complete_task(task_id, outcome)
    if not success:
        raise HTTPException(404, f"Task {task_id} not found")
    await _broadcast({
        "type": "plan_task_completed",
        "task_id": task_id,
        "outcome": outcome,
    })
    return {"status": "ok"}


@app.post("/api/plan/milestone/{milestone_id}")
async def api_update_milestone(milestone_id: str, body: MilestoneRequest):
    progress = body.progress
    status = body.status
    success = _plan.update_milestone(milestone_id, progress, status)
    if not success:
        raise HTTPException(404, f"Milestone {milestone_id} not found")
    await _broadcast({
        "type": "plan_milestone_updated",
        "milestone_id": milestone_id,
        "progress": progress,
        "status": status,
    })
    return {"status": "ok"}


# ── Orchestrator Endpoints (REPORT_FINALE §8) ──────────────────────────
@app.get("/api/orchestrator/status")
def api_orchestrator_status():
    if not _orchestrator:
        return {"running": False, "message": "Orchestrator not started"}
    return _orchestrator.get_status()


@app.post("/api/orchestrator/tick")
async def api_orchestrator_tick():
    """Force a single orchestrator tick (bypasses the wait timer).

    Runs in a background thread to avoid blocking the API while the LLM responds.
    """
    if not _orchestrator:
        raise HTTPException(503, "Orchestrator not started")

    def _do_tick():
        try:
            actions = _orchestrator.scheduler.tick()
            health = _orchestrator.health_monitor.check()
            if health.get("alerts"):
                import asyncio
                try:
                    loop = asyncio.new_event_loop()
                    loop.run_until_complete(_broadcast({"type": "health_alerts", "alerts": health["alerts"]}))
                    loop.close()
                except Exception:
                    pass
        except Exception as e:
            print(f"[orchestrator tick] error: {e}")

    threading.Thread(target=_do_tick, daemon=True).start()
    return {"status": "started", "message": "Tick in esecuzione in background"}


@app.get("/api/orchestrator/health")
def api_health():
    if not _orchestrator:
        raise HTTPException(503, "Orchestrator not started")
    return _orchestrator.health_monitor.check()


@app.get("/api/orchestrator/load")
def api_load():
    if not _orchestrator:
        return {"distribution": {}}
    return {"distribution": _orchestrator.load_balancer.distribution()}


@app.post("/api/plan/task/{task_id}/execute")
async def api_execute_task(task_id: str, body: Optional[ExecuteTaskRequest] = None):
    """End-to-end execution: technician analyzes + supervisor validates."""
    if not _orchestrator:
        raise HTTPException(503, "Orchestrator not started")

    # Look up existing task
    task = next((t for t in _plan.tasks if t["id"] == task_id), None)
    if not task:
        # Allow creating ad-hoc task via body
        if not body:
            raise HTTPException(404, f"Task {task_id} not found and no body provided")
        task = {
            "id": task_id,
            "title": body.title,
            "description": body.description,
            "agent_id": body.agent_id,
            "milestone_id": body.milestone_id,
            "priority": body.priority,
        }
    else:
        # Allow override via body
        if body and body.title != "Untitled":
            task = {**task, "title": body.title, "description": body.description,
                    "agent_id": body.agent_id or task.get("agent_id", "auto"),
                    "milestone_id": body.milestone_id or task.get("milestone_id", "")}

    record = _orchestrator.execute_task(task)
    await _broadcast({
        "type": "task_executed",
        "task_id": task_id,
        "outcome": record.get("outcome"),
        "agent_id": record.get("agent_id"),
    })
    return record


@app.post("/api/plan/task/{task_id}/auto-assign")
def api_auto_assign(task_id: str):
    """Apply load balancing to suggest the best technician for this task."""
    task = next((t for t in _plan.tasks if t["id"] == task_id), None)
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")
    suggested = _orchestrator._auto_pick_technician(task)
    task["agent_id"] = suggested
    _plan.save()
    return {"task_id": task_id, "assigned_to": suggested}


@app.post("/api/agents/analyze-all")
async def api_analyze_all(body: AnalyzeAllRequest = AnalyzeAllRequest()):
    """Run analyze() across multiple agents, with load balancing. Runs in background."""
    if not _orchestrator:
        raise HTTPException(503, "Orchestrator not started")

    ctx = _get_speace_context()
    results = []
    targets = [a for a in _agents.values()
               if (a.agent_id.endswith("_supervisor") or a.agent_id == "chief_architect")]
    if not body.sample:
        targets = list(_agents.values())

    def _do_analyze():
        completed = 0
        for agent in sorted(targets, key=lambda a: _orchestrator.load_balancer.workload_score(a.agent_id)):
            _orchestrator.load_balancer.record_analysis(agent.agent_id)
            try:
                f = agent.analyze(ctx)
                # Store result directly in agent's findings to avoid shared list race
                agent.findings.append({
                    "agent_id": agent.agent_id,
                    "name": agent.name,
                    "preview": f.get("analysis", "")[:500],
                    "ts": time.time(),
                })
            except Exception as e:
                agent.findings.append({
                    "agent_id": agent.agent_id,
                    "error": str(e),
                    "ts": time.time(),
                })
            completed += 1

    threading.Thread(target=_do_analyze, daemon=True).start()
    return {"status": "started", "total": len(targets), "message": f"Analisi di {len(targets)} agenti in background"}


# ── Auto-Analysis Findings ──────────────────────────────────────────────
@app.get("/api/auto-analysis/recent")
def api_auto_analysis_recent(n: int = 20):
    log_path = Path("data/agi_team/auto_analysis.jsonl")
    if not log_path.exists():
        return {"findings": []}
    try:
        lines = log_path.read_text(encoding="utf-8").strip().split("\n")
        findings = []
        for line in lines[-n:]:
            try:
                findings.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return {"findings": findings}
    except OSError:
        return {"findings": []}


@app.get("/api/health/alerts")
def api_health_alerts(n: int = 20):
    log_path = Path("data/agi_team/health_alerts.jsonl")
    if not log_path.exists():
        return {"alerts": []}
    try:
        lines = log_path.read_text(encoding="utf-8").strip().split("\n")
        alerts = []
        for line in lines[-n:]:
            try:
                alerts.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return {"alerts": alerts}
    except OSError:
        return {"alerts": []}


# ── Web Search & Document Fetch ───────────────────────────────────────
@app.post("/api/web/search")
async def api_web_search(body: WebSearchRequest):
    """Direct web search via DuckDuckGo. No agent involved."""
    s = WebSearcher()
    results = s.search(body.query, max_results=body.max_results)
    return {"query": body.query, "results": results, "count": len(results)}


@app.post("/api/web/fetch")
async def api_web_fetch(body: FetchRequest):
    """Fetch and extract text from a URL."""
    f = DocumentFetcher()
    doc = f.fetch(body.url)
    return doc


@app.post("/api/web/research")
async def api_web_research(body: ResearchRequest):
    """Combined search + fetch: returns top results with extracted text."""
    data = research(body.query, max_results=body.max_results,
                    fetch_top=body.fetch_top, fetch_max_chars=body.fetch_max_chars)
    return data


@app.post("/api/agents/{agent_id}/research")
async def api_agent_research(agent_id: str, body: AgentResearchRequest):
    """Let a specific agent run a web research and synthesize the results.

    The agent's LLM is queried with the research summary as context.
    """
    agent = _agents.get(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent {agent_id} not found")

    # Run the research (synchronous; cached after first call)
    research_data = agent.research_web(
        body.query, max_results=body.max_results,
        fetch_top=body.fetch_top, fetch_max_chars=body.fetch_max_chars,
    )
    history = agent.get_research_history(5)

    response_payload: Dict[str, Any] = {
        "agent_id": agent_id,
        "query": body.query,
        "results": research_data.get("results", []),
        "documents": research_data.get("documents", []),
        "synthesis": None,
        "research_history": history,
    }

    if body.synthesis:
        summary = agent.research_summary(
            body.query, fetch_top=body.fetch_top, fetch_max_chars=body.fetch_max_chars,
        )
        prompt = (
            f"Hai effettuato la seguente ricerca web per migliorare SPEACE:\n\n"
            f"Query: {body.query}\n\n"
            f"Risultati trovati:\n{summary}\n\n"
            f"Basandoti SOLO su queste fonti, fornisci una sintesi strutturata in italiano:\n"
            f"1. Sintesi dei punti chiave emersi dalla letteratura\n"
            f"2. Raccomandazioni concrete per SPEACE (cervello digitale neurocellulare)\n"
            f"3. Citazioni o riferimenti specifici dai documenti analizzati\n"
            f"4. Eventuali limitazioni o gap informativi riscontrati"
        )
        synthesis = agent.chat(prompt)
        response_payload["synthesis"] = synthesis
        await _broadcast({
            "type": "agent_research",
            "agent_id": agent_id,
            "query": body.query,
            "synthesis_preview": synthesis[:300],
        })

    return response_payload


@app.get("/api/agents/{agent_id}/research-history")
def api_agent_research_history(agent_id: str, n: int = 20):
    agent = _agents.get(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent {agent_id} not found")
    return {"agent_id": agent_id, "history": agent.get_research_history(n)}


# ── Websocket ────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    _ws_connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue
            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        _ws_connections.remove(websocket)
    except Exception:
        if websocket in _ws_connections:
            _ws_connections.remove(websocket)


# ── Frontend ─────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def root():
    index_path = static_dir / "index.html"
    if index_path.exists():
        return HTMLResponse(index_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>SPEACE AGI Team</h1><p>Frontend not found</p>")


# ── Runner ───────────────────────────────────────────────────────────────
def run_server(host: str = "127.0.0.1", port: int = 8686):
    import uvicorn
    print(f"\n{'='*50}")
    print(f"  SPEACE AGI TEAM - Dashboard & Chat")
    print(f"  URL: http://{host}:{port}")
    print(f"  Modello: {AgentConfig().model}")
    print(f"  Agenti: 20 (10 supervisor + 10 tecnici)")
    print(f"{'='*50}\n")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run_server()
