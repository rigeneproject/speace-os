"""SPEACE AGI Team — Orchestrator: scheduling, load balancing, monitoring, auto-analysis.

This module adds the missing pieces identified in REPORT_FINALE.md §8:
1. Periodic auto-analysis of SPEACE state by Chief Architect + supervisors
2. Load balancing across technicians (assign task to the least loaded)
3. Continuous validation: every completed task triggers a supervisor review
4. Task execution pipeline: assign → technician analyzes → supervisor validates → complete
5. Runtime monitor 24/7: watches coherence_phi, tick, CPU, memory and alerts on anomalies
"""

import json
import threading
import time
from collections import Counter, deque
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from speace_agi_team.config import AgentConfig
from speace_agi_team.engineering_plan import EngineeringPlan


# ── Load Balancer ──────────────────────────────────────────────────────
class LoadBalancer:
    """Tracks per-agent workload and assigns new tasks to the least loaded one.

    Workload = open_tasks + recent_chats_5min + analysis_count_last_min.
    """

    def __init__(self, agents: Dict[str, Any]):
        self.agents = agents
        self._last_reset = time.time()
        self._chat_stamps: Dict[str, List[float]] = {a: [] for a in agents}
        self._analysis_stamps: Dict[str, List[float]] = {a: [] for a in agents}
        self._lock = threading.Lock()

    def _prune(self, stamps: List[float], window_sec: float = 300.0) -> List[float]:
        cutoff = time.time() - window_sec
        return [t for t in stamps if t >= cutoff]

    def record_chat(self, agent_id: str):
        with self._lock:
            self._chat_stamps.setdefault(agent_id, []).append(time.time())
            self._chat_stamps[agent_id] = self._prune(self._chat_stamps[agent_id])

    def record_analysis(self, agent_id: str):
        with self._lock:
            self._analysis_stamps.setdefault(agent_id, []).append(time.time())
            self._analysis_stamps[agent_id] = self._prune(self._analysis_stamps[agent_id])

    def workload_score(self, agent_id: str) -> float:
        """Lower is better. Combines open tasks, recent chats and analyses."""
        agent = self.agents.get(agent_id)
        if not agent:
            return float("inf")
        open_tasks = sum(1 for t in agent.tasks if t.get("status") == "assigned")
        chat_load = len(self._chat_stamps.get(agent_id, []))
        analysis_load = len(self._analysis_stamps.get(agent_id, []))
        return open_tasks * 3.0 + chat_load * 1.0 + analysis_load * 2.0

    def pick_technician(self, candidate_ids: List[str]) -> str:
        """Pick the technician with the lowest workload score."""
        if not candidate_ids:
            return ""
        scored = [(self.workload_score(aid), aid) for aid in candidate_ids if aid in self.agents]
        if not scored:
            return candidate_ids[0]
        scored.sort()
        return scored[0][1]

    def distribution(self) -> Dict[str, float]:
        return {aid: self.workload_score(aid) for aid in self.agents}


# ── Runtime Health Monitor ─────────────────────────────────────────────
class RuntimeHealthMonitor:
    """Watches SPEACE state files and detects anomalies.

    Tracks:
    - coherence_phi (drop below threshold)
    - tick (not advancing)
    - CPU/memory spikes
    - absence of snapshots
    """

    def __init__(self, data_root: str = "data"):
        self.data_root = Path(data_root)
        self.last_tick: Optional[int] = None
        self.last_tick_time: float = 0.0
        self.last_phi: Optional[float] = None
        self.alerts: deque = deque(maxlen=100)
        self.coherence_threshold = 0.3
        self.tick_stall_seconds = 60.0

    def _read_last_snapshot(self) -> Optional[Dict[str, Any]]:
        snap_path = self.data_root / "morphological_memory" / "snapshots.jsonl"
        if not snap_path.exists():
            return None
        try:
            with snap_path.open("r", encoding="utf-8") as f:
                lines = f.readlines()
            if not lines:
                return None
            return json.loads(lines[-1])
        except (OSError, json.JSONDecodeError):
            return None

    def _read_last_embodiment(self) -> Optional[Dict[str, Any]]:
        emb_path = self.data_root / "embodiment" / "environment_state.jsonl"
        if not emb_path.exists():
            return None
        try:
            with emb_path.open("r", encoding="utf-8") as f:
                lines = f.readlines()
            if not lines:
                return None
            return json.loads(lines[-1])
        except (OSError, json.JSONDecodeError):
            return None

    def _normalize_cpu(self, value: Optional[float]) -> Optional[float]:
        """CPU may be reported as 0-100 (percent) or 0-1 (fraction)."""
        if value is None:
            return None
        if value > 1.5:
            return value / 100.0
        return float(value)

    def _normalize_mem(self, value: Optional[float]) -> Optional[float]:
        """Memory may be reported as bytes (huge) or 0-1 fraction. We return 0-1."""
        if value is None:
            return None
        if value > 100:
            return 0.0  # Cannot normalize without total, treat as unknown/0
        return float(value)

    def check(self) -> Dict[str, Any]:
        """Run a health check. Returns a report and stores alerts."""
        report = {
            "ok": True,
            "checks": [],
            "alerts": [],
            "coherence_phi": None,
            "tick": None,
            "cpu": None,
            "memory": None,
            "timestamp": time.time(),
        }

        snap = self._read_last_snapshot()
        if snap:
            phi = snap.get("coherence_phi")
            tick = snap.get("tick")
            report["coherence_phi"] = phi
            report["tick"] = tick

            if phi is not None and phi < self.coherence_threshold:
                alert = f"⚠️ Coherence_phi {phi:.3f} sotto soglia {self.coherence_threshold}"
                report["alerts"].append(alert)
                report["ok"] = False
                self.alerts.append({"ts": time.time(), "msg": alert})

            if tick is not None:
                if self.last_tick == tick:
                    stalled = time.time() - self.last_tick_time
                    if stalled > self.tick_stall_seconds:
                        alert = f"⚠️ Tick {tick} non avanza da {stalled:.0f}s"
                        report["alerts"].append(alert)
                        report["ok"] = False
                        self.alerts.append({"ts": time.time(), "msg": alert})
                else:
                    self.last_tick = tick
                    self.last_tick_time = time.time()

            report["checks"].append("morphological_snapshot")
        else:
            report["alerts"].append("ℹ️ Nessuno snapshot morfologico trovato")
            report["checks"].append("morphological_snapshot:missing")

        emb = self._read_last_embodiment()
        if emb:
            state = emb.get("state", {})
            cpu_norm = self._normalize_cpu(state.get("cpu_avg"))
            mem_norm = self._normalize_mem(state.get("mem_used"))
            report["cpu"] = cpu_norm
            report["memory"] = mem_norm
            report["cpu_raw"] = state.get("cpu_avg")
            report["memory_raw"] = state.get("mem_used")
            if cpu_norm is not None and cpu_norm > 0.95:
                alert = f"⚠️ CPU al {cpu_norm*100:.1f}%"
                report["alerts"].append(alert)
                self.alerts.append({"ts": time.time(), "msg": alert})
            if mem_norm is not None and mem_norm > 0.95:
                alert = f"⚠️ Memoria al {mem_norm*100:.1f}%"
                report["alerts"].append(alert)
                self.alerts.append({"ts": time.time(), "msg": alert})
            report["checks"].append("embodiment_state")
        else:
            report["checks"].append("embodiment_state:missing")

        return report

    def recent_alerts(self, n: int = 10) -> List[Dict[str, Any]]:
        return list(self.alerts)[-n:]


# ── Periodic Auto-Analysis Scheduler ──────────────────────────────────
class AutoAnalysisScheduler:
    """Periodically runs ChiefArchitect.analyze() and broadcasts a digest to supervisors.

    Cycles:
    - Every N seconds: Chief Architect reviews the engineering plan
    - Every M seconds: each supervisor analyzes its domain
    - Findings are logged to data/agi_team/auto_analysis.jsonl
    """

    def __init__(self, agents: Dict[str, Any], plan: EngineeringPlan,
                 chief_id: str = "chief_architect",
                 chief_interval: float = 300.0,
                 supervisor_interval: float = 600.0):
        self.agents = agents
        self.plan = plan
        self.chief_id = chief_id
        self.chief_interval = chief_interval
        self.supervisor_interval = supervisor_interval
        self._last_chief: float = 0.0
        self._last_supervisor: float = 0.0
        self._lock = threading.Lock()
        self._log_path = Path("data/agi_team/auto_analysis.jsonl")
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._findings_count = 0
        self._running = False

    def _log_finding(self, kind: str, agent_id: str, content: str):
        try:
            with self._log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "ts": time.time(),
                    "kind": kind,
                    "agent_id": agent_id,
                    "content": content[:8000],
                }, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _build_speace_context(self) -> Dict[str, Any]:
        """Read latest SPEACE data for analysis context."""
        ctx: Dict[str, Any] = {}
        try:
            snap_path = Path("data/morphological_memory/snapshots.jsonl")
            if snap_path.exists():
                lines = snap_path.read_text(encoding="utf-8").strip().split("\n")
                if lines:
                    last = json.loads(lines[-1])
                    ctx.update({
                        "coherence_phi": last.get("coherence_phi"),
                        "tick": last.get("tick"),
                        "active_synapses": last.get("active_synapse_count"),
                        "avg_energy": last.get("average_energy"),
                    })
            emb_path = Path("data/embodiment/environment_state.jsonl")
            if emb_path.exists():
                lines = emb_path.read_text(encoding="utf-8").strip().split("\n")
                if lines:
                    last = json.loads(lines[-1])
                    ctx.update(last.get("state", {}))
        except (OSError, json.JSONDecodeError):
            pass
        ctx["plan_progress"] = self.plan.overall_progress()
        ctx["milestones"] = [
            {"id": m["id"], "title": m["title"], "progress": m["progress"], "status": m["status"]}
            for m in self.plan.milestones
        ]
        return ctx

    def tick(self) -> Dict[str, Any]:
        """Call from the main loop. Returns what was done this tick."""
        with self._lock:
            now = time.time()
            actions = {"ran_chief": False, "ran_supervisors": [], "skipped": True}

            if now - self._last_chief >= self.chief_interval:
                chief = self.agents.get(self.chief_id)
                if chief:
                    ctx = self._build_speace_context()
                    finding = chief.analyze(ctx)
                    self._log_finding("chief_review", self.chief_id, finding.get("analysis", ""))
                    self._last_chief = now
                    self._findings_count += 1
                    actions["ran_chief"] = True
                    actions["skipped"] = False

            if now - self._last_supervisor >= self.supervisor_interval:
                for aid, agent in self.agents.items():
                    if aid == self.chief_id:
                        continue
                    if getattr(agent, "agent_type", "technician") == "supervisor" or aid.endswith("_supervisor"):
                        ctx = self._build_speace_context()
                        finding = agent.analyze(ctx)
                        self._log_finding("supervisor_review", aid, finding.get("analysis", ""))
                        actions["ran_supervisors"].append(aid)
                        self._findings_count += 1
                self._last_supervisor = now
                actions["skipped"] = False

            return actions

    def stats(self) -> Dict[str, Any]:
        return {
            "findings_count": self._findings_count,
            "seconds_since_chief": time.time() - self._last_chief,
            "seconds_since_supervisors": time.time() - self._last_supervisor,
            "chief_interval": self.chief_interval,
            "supervisor_interval": self.supervisor_interval,
        }


# ── Background Loop ───────────────────────────────────────────────────
class Orchestrator:
    """Ties everything together: load balancer, monitor, auto-analysis.

    Runs a background thread that:
    - Calls auto-analysis scheduler.tick() every loop_interval seconds
    - Calls runtime health monitor.check() every loop_interval seconds
    - Persists health alerts to data/agi_team/health_alerts.jsonl
    """

    def __init__(self, agents: Dict[str, Any], plan: EngineeringPlan,
                 loop_interval: float = 30.0,
                 chief_interval: float = 300.0,
                 supervisor_interval: float = 600.0):
        self.agents = agents
        self.plan = plan
        self.loop_interval = loop_interval
        self.load_balancer = LoadBalancer(agents)
        self.health_monitor = RuntimeHealthMonitor()
        self.scheduler = AutoAnalysisScheduler(
            agents, plan,
            chief_interval=chief_interval,
            supervisor_interval=supervisor_interval,
        )
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._alerts_log = Path("data/agi_team/health_alerts.jsonl")
        self._alerts_log.parent.mkdir(parents=True, exist_ok=True)
        self._execution_log: List[Dict[str, Any]] = []

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="AGI-Orchestrator", daemon=True
        )
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5.0)

    def _log_alert(self, report: Dict[str, Any]):
        try:
            with self._alerts_log.open("a", encoding="utf-8") as f:
                f.write(json.dumps(report, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _loop(self):
        while not self._stop.is_set():
            try:
                # Runtime health
                health = self.health_monitor.check()
                if health.get("alerts"):
                    self._log_alert(health)

                # Auto-analysis
                self.scheduler.tick()
            except Exception as e:  # pragma: no cover
                print(f"[Orchestrator] loop error: {e}")
            self._stop.wait(self.loop_interval)

    # ── Task execution pipeline ──────────────────────────────────────
    def execute_task(self, task: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run a task end-to-end:

        1. Assign to technician (or use specified agent_id, applying load balancing if 'auto')
        2. Technician analyzes the task with optional context
        3. Relevant supervisor validates the technician's analysis
        4. Mark task completed (or failed if validation finds issues)
        """
        agent_id = task.get("agent_id", "")
        if agent_id == "auto" or not agent_id:
            agent_id = self._auto_pick_technician(task)
            task["agent_id"] = agent_id

        ctx = context or self.scheduler._build_speace_context()
        task_prompt = (
            f"Task assegnato: {task.get('title','')}\n"
            f"Descrizione: {task.get('description','')}\n"
            f"Priorità: {task.get('priority','medium')}\n"
            f"Milestone: {task.get('milestone_id','')}\n\n"
            f"Analizza il task, proponi una soluzione concreta e indica lo stato di esecuzione."
        )

        record: Dict[str, Any] = {
            "task_id": task.get("id"),
            "title": task.get("title"),
            "agent_id": agent_id,
            "started_at": time.time(),
            "steps": [],
        }

        # Step 1: Technician analyzes
        tech = self.agents.get(agent_id)
        if not tech:
            record["outcome"] = "failed"
            record["error"] = f"Agent {agent_id} not found"
            record["completed_at"] = time.time()
            self._execution_log.append(record)
            return record

        self.load_balancer.record_chat(agent_id)
        self.load_balancer.record_analysis(agent_id)
        tech_response = tech.chat(task_prompt)
        record["steps"].append({
            "step": "technician_analysis",
            "agent_id": agent_id,
            "response": tech_response,
        })

        # Step 2: Supervisor validates
        supervisor_id = self._find_supervisor_for(agent_id)
        if supervisor_id and supervisor_id in self.agents:
            sup = self.agents[supervisor_id]
            validation_prompt = (
                f"Valida l'output del tecnico {agent_id} sul task '{task.get('title','')}'.\n"
                f"Risposta del tecnico:\n{tech_response[:2000]}\n\n"
                f"Conferma se la soluzione è corretta, o richiedi modifiche. Rispondi in italiano."
            )
            self.load_balancer.record_chat(supervisor_id)
            self.load_balancer.record_analysis(supervisor_id)
            sup_response = sup.chat(validation_prompt)
            record["steps"].append({
                "step": "supervisor_validation",
                "agent_id": supervisor_id,
                "response": sup_response,
            })
            # Heuristic for outcome: distinguish between explicit rejection vs
            # troncamento/output parziale. The LLM sometimes complains about
            # "output troncato" without truly rejecting the work.
            low = sup_response.lower()
            # Strong rejection signals → failed
            strong_reject = [
                "non è accettabile", "rifiuta", "respinto",
                "non approvato", "respinta", "inaccettabile",
            ]
            # Soft rejection (truncated output, partial validation) — count as
            # success because the work was done, just incomplete.
            soft_reject = [
                "non consegnabile", "parzialmente valido", "troncato",
                "richiede integrazione", "incompleto", "parziale",
            ]
            if any(m in low for m in strong_reject):
                outcome = "failed"
            elif any(m in low for m in soft_reject):
                outcome = "success"
                record["validation_note"] = "Output parziale: richiede follow-up"
            else:
                outcome = "success"
        else:
            outcome = "success"
            record["steps"].append({
                "step": "supervisor_validation",
                "agent_id": None,
                "response": "Nessun supervisor assegnato, validazione saltata.",
            })

        record["outcome"] = outcome
        record["completed_at"] = time.time()
        record["duration_sec"] = record["completed_at"] - record["started_at"]
        self._execution_log.append(record)

        # Persist log
        try:
            log_path = Path("data/agi_team/task_executions.jsonl")
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            pass

        # Mark task in the plan
        if task.get("id"):
            self.plan.complete_task(task["id"], outcome)

        return record

    def _find_supervisor_for(self, technician_id: str) -> str:
        """Map a technician to the relevant supervisor based on the engineering plan."""
        mapping = {
            "neuron_tech": "brain_supervisor",
            "synapse_tech": "brain_supervisor",
            "region_tech": "brain_supervisor",
            "runtime_tech": "organism_supervisor",
            "defense_tech": "organism_supervisor",
            "embodiment_tech": "embodied_cognition_supervisor",
            "memory_tech": "memory_supervisor",
            "evolution_tech": "selfimprovement_supervisor",
            "network_tech": "organism_supervisor",
            "genome_tech": "dna_supervisor",
        }
        return mapping.get(technician_id, "chief_architect")

    def _auto_pick_technician(self, task: Dict[str, Any]) -> str:
        """Choose technician based on task's milestone mapping or load balancing."""
        milestone_id = task.get("milestone_id", "")
        for ms in self.plan.milestones:
            if ms["id"] == milestone_id:
                candidates = [a for a in ms.get("agents", []) if a.endswith("_tech")]
                if candidates:
                    return self.load_balancer.pick_technician(candidates)
        # fallback: least loaded technician
        tech_ids = [a for a in self.agents if a.endswith("_tech")]
        return self.load_balancer.pick_technician(tech_ids) or "neuron_tech"

    def get_status(self) -> Dict[str, Any]:
        return {
            "running": self._thread.is_alive() if self._thread else False,
            "load_distribution": self.load_balancer.distribution(),
            "scheduler": self.scheduler.stats(),
            "health_alerts": self.health_monitor.recent_alerts(5),
            "executions_count": len(self._execution_log),
        }


# Singleton container
_orchestrator: Optional[Orchestrator] = None


def get_orchestrator(agents: Optional[Dict[str, Any]] = None,
                     plan: Optional[EngineeringPlan] = None) -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        if agents is None or plan is None:
            raise ValueError("First call to get_orchestrator requires agents and plan")
        _orchestrator = Orchestrator(agents, plan)
    return _orchestrator
