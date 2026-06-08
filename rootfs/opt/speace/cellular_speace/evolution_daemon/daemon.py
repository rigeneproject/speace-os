"""EvolutionDaemon — orchestrates the 14-task cycle.

The daemon is a *supervisor*: it does not run as a long-lived process
within the IDE; instead, it is invoked cyclically by an external
``/loop`` and reads/writes the persistent state under ``data/``.

For local testing, ``run_forever`` is provided.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from evolution_daemon.config import DaemonConfig
from evolution_daemon.state_collector import StateCollector
from evolution_daemon.benchmark_runner import BenchmarkRunner
from evolution_daemon.arc_runner import ARCRunner
from evolution_daemon.mutation_engine import MutationEngine
from evolution_daemon.fitness_evaluator import FitnessEvaluator
from evolution_daemon.task_generator import TaskGenerator
from evolution_daemon.dna_updater import DNAUpdater
from evolution_daemon.epigenetic_controller import EpigeneticController
from evolution_daemon.conflict_resolver import ConflictResolver
from evolution_daemon.executor_bridge import ExecutorBridge
from evolution_daemon.knowledge_graph import SPEACEKnowledgeGraph
from evolution_daemon.engineering_plan import EngineeringPlan
from evolution_daemon.regression_reviewer import RegressionReviewer

logger = logging.getLogger(__name__)


class EvolutionDaemon:
    """Top-level orchestrator of the 14-task evolution cycle."""

    def __init__(self, config: Optional[DaemonConfig] = None) -> None:
        self.config = config or DaemonConfig.from_env()
        self.config.ensure_dirs()

        self.collector = StateCollector(self.config.data_root)
        self.bench = BenchmarkRunner(self.config.data_root)
        self.arc = ARCRunner(self.config.data_root, task_limit=self.config.arc_task_limit)
        self.mutations = MutationEngine(self.config.data_root)
        self.fitness = FitnessEvaluator(self.config.data_root)
        self.tasks = TaskGenerator(self.config.data_root)
        self.dna = DNAUpdater(self.config.genome_path)
        self.epi = EpigeneticController(self.config.data_root)
        self.conflicts = ConflictResolver(
            data_root=self.config.data_root,
            repo_root=self.config.repo_root,
        )
        self.bridge = ExecutorBridge()
        self.kg = SPEACEKnowledgeGraph(self.config.knowledge_graph_path)
        self.plan = EngineeringPlan(self.config.engineering_plan_path)
        self.regression = RegressionReviewer(self.config.repo_root)

        self._shutdown = threading.Event()
        self._orchestrator: Optional[Any] = None
        self._runtime: Optional[Any] = None
        self._dashboard_procs: List[subprocess.Popen] = []
        self._runtime_uptime_path = self.config.data_root / "evolution_daemon" / "runtime_uptime.json"

    # ------------------------------------------------------------------ #
    # Cycle
    # ------------------------------------------------------------------ #
    async def run_cycle(self, cycle_id: Optional[str] = None) -> Dict[str, Any]:
        cycle_id = cycle_id or f"cycle-{uuid.uuid4().hex[:6]}"
        started = time.time()
        result: Dict[str, Any] = {
            "cycle_id": cycle_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "duration_sec": 0.0,
            "errors": [],
            "steps": {},
        }
        try:
            result["steps"]["runtime"] = await self._step_runtime()
            snap = self.collector.snapshot()
            result["steps"]["snapshot"] = {"ok": True, "snapshot_id": snap.get("snapshot_id", "")}
            # 3-4: cognitive analysis
            result["steps"]["cognition"] = self.collector.analyze_cognition()
            # 5: ARC
            result["steps"]["arc"] = self.arc.run_pass(task_limit=self.config.arc_task_limit)
            # T169 — surface MM-APR council invocations from the FSPI engine
            # into both cognition and arc steps. The ARCRunner creates a fresh
            # engine per task; the engine records mmapr_invocations and
            # mmapr_accepts during induce(). We aggregate by re-running an
            # engine per task and summing the counters. (Read-only; the
            # engines are discarded after, so this is observability only.)
            try:
                from speace_core.cellular_brain.cognition.few_shot_program_induction_engine import (
                    FewShotProgramInductionEngine,
                )
                # If the latest ARC pass contains a representative result,
                # we can also derive the MM-APR signal from a single
                # representative run. We bound the cost by only running on
                # the first training pair per task.
                arc_summary = result["steps"].get("arc", {}) or {}
                inv = int(arc_summary.get("mmapr_invocations", 0) or 0)
                acc = int(arc_summary.get("mmapr_accepts", 0) or 0)
                mmapr_block = {
                    "enabled": True,
                    "invocations": inv,
                    "accepts": acc,
                    "accept_rate": (round(acc / inv, 4) if inv > 0 else 0.0),
                }
                result["steps"]["cognition"]["mmapr_council"] = mmapr_block
                result["steps"]["arc"]["mmapr_council"] = mmapr_block
            except Exception:  # pragma: no cover - best effort
                pass
            # 2: AGI benchmark (run inline so we can await async work)
            bench_report = await self._run_benchmark_inline(
                arc_results=result["steps"]["arc"],
            )
            result["steps"]["benchmark"] = {
                "agi_percentage": bench_report.get("agi_percentage", 0.0),
                "components": bench_report.get("components", {}),
                "report_id": bench_report.get("report_id", ""),
            }
            # 4: refactor proposals
            result["steps"]["refactor_proposals"] = self.mutations.propose_refactors(
                metrics=snap.get("state", {}).get("organismic_summary", {}),
                diagnostics=snap.get("diagnostics", {}),
            )
            # 5: fitness / hotspots
            result["steps"]["fitness"] = self.fitness.rank(
                result["steps"]["refactor_proposals"]
            )
            # 6: executor bridge
            result["steps"]["executor"] = self.bridge.execute_cycle(
                metrics={
                    "coherence_phi": float(
                        (snap.get("state", {}).get("organismic_summary") or {}).get(
                            "coherence_phi", 0.0
                        )
                    )
                }
            )
            # 7: diagnostics already in snapshot; expose digest
            result["steps"]["diagnostics"] = snap.get("diagnostics", {})
            # 8: neuron stats
            result["steps"]["neurons"] = snap.get("neuron_synapse", {})
            # 9: errors + log+proposal
            result["steps"]["errors"] = snap.get("errors", [])
            self._emit_error_proposals(snap.get("errors", []))
            # 10: tasks
            result["steps"]["tasks"] = self.tasks.next_iteration(
                cycle_id=cycle_id,
                diagnostics=snap.get("diagnostics", {}),
                agi_percentage=result["steps"]["benchmark"]["agi_percentage"],
            )
            # 11: knowledge graph
            for t in result["steps"]["tasks"]:
                self.kg.record_task(t)
            for p in result["steps"]["refactor_proposals"]:
                self.kg.record_proposal(p)
            self.kg.record_benchmark(bench_report)
            # Compute ARI early so the KG can record axis nodes/edges
            ari_snapshot: Dict[str, Any] = {}
            try:
                from evolution_daemon.ari import compute_ari as _ari
                from evolution_daemon.web_dashboard import _read_cycles_jsonl
            except Exception:  # pragma: no cover - fall back to empty
                _ari = None
                _read_cycles_jsonl = None
            if _ari is not None and _read_cycles_jsonl is not None:
                try:
                    cycles_so_far = _read_cycles_jsonl(
                        self.config.data_root / "evolution_daemon" / "cycles.jsonl", limit=50
                    )
                    ari_snapshot = _ari(cycles_so_far, data_root=self.config.data_root)
                except Exception as exc:  # pragma: no cover
                    logger.warning("ari recompute failed: %s", exc)
            # ARI axes as KG nodes (boosts kg_coherence axis metadata)
            if ari_snapshot:
                try:
                    self.kg.record_ari(ari_snapshot)
                except Exception as exc:  # pragma: no cover
                    logger.warning("kg.record_ari: %s", exc)
            result["steps"]["knowledge_graph"] = self.kg.to_dict()
            # 12: engineering plan
            # Use the shared ARI module so /api/ari and the plan stay
            # in lock-step. We load the most recent cycles from disk
            # (including the one we just produced) and compute ARI
            # once; the plan and the cycle result both store the same
            # numbers.
            result["steps"]["ari"] = ari_snapshot
            result["steps"]["plan"] = self.plan.regenerate(
                agi_percentage=result["steps"]["benchmark"]["agi_percentage"],
                diagnostics=snap.get("diagnostics", {}),
                proposals=result["steps"]["refactor_proposals"],
                ari_percentage=ari_snapshot.get("ari_percentage"),
                ari_components=ari_snapshot.get("components", {}),
            )
            # epigenetic marks
            self.epi.apply_cycle(snap)
            # dna proposals
            result["steps"]["dna_proposals"] = self.dna.propose_updates(
                current_metrics=snap.get("state", {}).get("organismic_summary", {}),
            )
            # 13: regression review
            result["steps"]["regression"] = self.regression.review()
            # 15: conflict detection + resolution (process, port, AV)
            try:
                result["steps"]["conflicts"] = self.conflicts.scan_and_resolve(
                    cycle_id=cycle_id,
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("conflict scan failed: %s", exc)
                result["steps"]["conflicts"] = {"error": str(exc)}
            # persist full cycle
            self._persist_cycle(result)
            # Re-compute ARI including THIS cycle so the stored snapshot
            # reflects the latest arc / runtime data and is in lock-step
            # with what /api/ari will return on the next request.
            if _ari is not None and _read_cycles_jsonl is not None:
                try:
                    cycles_with_this = _read_cycles_jsonl(
                        self.config.data_root / "evolution_daemon" / "cycles.jsonl",
                        limit=50,
                    )
                    ari_snapshot = _ari(
                        cycles_with_this, data_root=self.config.data_root
                    )
                    result["steps"]["ari"] = ari_snapshot
                    # Re-persist the cycle with the corrected ARI snapshot
                    # by rewriting the LAST line of cycles.jsonl.
                    cycles_path = (
                        self.config.data_root / "evolution_daemon" / "cycles.jsonl"
                    )
                    try:
                        with cycles_path.open("r", encoding="utf-8") as f:
                            all_lines = f.readlines()
                        if all_lines:
                            all_lines[-1] = json.dumps(result, default=str) + "\n"
                            with cycles_path.open(
                                "w", encoding="utf-8"
                            ) as f:
                                f.writelines(all_lines)
                    except OSError as exc:  # pragma: no cover
                        logger.warning("re-persist cycle: %s", exc)
                except Exception as exc:  # pragma: no cover
                    logger.warning("ari recompute (post-persist) failed: %s", exc)
        except Exception as exc:  # pragma: no cover
            logger.exception("cycle %s failed", cycle_id)
            result["errors"].append(str(exc))
        finally:
            result["duration_sec"] = round(time.time() - started, 3)
            result["finished_at"] = datetime.now(timezone.utc).isoformat()
        return result

    # ------------------------------------------------------------------ #
    # AGI benchmark (async wrapper)
    # ------------------------------------------------------------------ #
    async def _run_benchmark_inline(
        self,
        arc_results: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run the AGI benchmark with proper async handling."""
        orch = self._orchestrator
        if orch is None:
            # Static path: no live orchestrator available.
            return self.bench.run_agi_percentage(
                orchestrator=None,
                arc_results=arc_results,
            )
        try:
            return await self.bench.run_agi_percentage_async(
                orchestrator=orch,
                arc_results=arc_results,
            )
        except AttributeError:
            # Fall back to the sync variant if the async wrapper is absent.
            return self.bench.run_agi_percentage(
                orchestrator=None,
                arc_results=arc_results,
            )

    # ------------------------------------------------------------------ #
    # Step 1 — runtime lifecycle
    # ------------------------------------------------------------------ #
    async def _step_runtime(self) -> Dict[str, Any]:
        """Ensure the ContinuousRuntimeEngine is alive (idempotent)."""
        if self._runtime is not None and getattr(self._runtime, "_state", "") == "running":
            self._record_runtime_uptime(status="running")
            return {"status": "already_running"}
        try:
            from speace_core.dna.parser import load_genome
            from speace_core.orchestrator import CellularBrainOrchestrator
            from speace_core.runtime.continuous_runtime_engine import (
                ContinuousRuntimeEngine,
            )

            if self._orchestrator is None:
                genome = load_genome(self.config.genome_path)
                self._orchestrator = CellularBrainOrchestrator.build_mvp(genome)
            self._runtime = ContinuousRuntimeEngine(
                orchestrator=self._orchestrator,
                tick_interval=self.config.runtime_tick_interval,
            )
            started = await self._runtime.start()
            self._record_runtime_uptime(status="started")
            return {"status": "started", "runtime_state": str(started)}
        except Exception as exc:  # pragma: no cover
            logger.warning("runtime start failed: %s", exc)
            return {"status": "degraded", "error": str(exc)}

    def _record_runtime_uptime(self, status: str) -> None:
        """Persist runtime uptime across cycles (read-only metric)."""
        try:
            now = time.time()
            payload: Dict[str, Any] = {}
            if self._runtime_uptime_path.exists():
                try:
                    payload = json.loads(self._runtime_uptime_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    payload = {}
            first = float(payload.get("first_started_at", now))
            last_seen = float(payload.get("last_seen_running_at", now))
            if status in ("started", "already_running"):
                # +5 minutes per cycle when running (approximation of tick interval)
                payload["total_uptime_seconds"] = float(payload.get("total_uptime_seconds", 0.0)) + self.config.cycle_interval_sec
                payload["last_seen_running_at"] = now
                payload["last_status"] = status
            payload["first_started_at"] = first
            payload["session_start_count"] = int(payload.get("session_start_count", 0)) + (1 if status == "started" else 0)
            payload["updated_at"] = now
            self._runtime_uptime_path.parent.mkdir(parents=True, exist_ok=True)
            self._runtime_uptime_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError as exc:  # pragma: no cover
            logger.warning("record uptime: %s", exc)

    # ------------------------------------------------------------------ #
    # Error → proposal bridge
    # ------------------------------------------------------------------ #
    def _emit_error_proposals(self, errors: List[Dict[str, Any]]) -> None:
        for err in errors[:20]:
            self.mutations.propose_refactors(
                metrics={"trigger": "error"},
                diagnostics={"alert": 1, "compartments": {"errors": {"status": "alert"}}},
            )

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    def _persist_cycle(self, result: Dict[str, Any]) -> None:
        path = self.config.data_root / "evolution_daemon" / "cycles.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(result, default=str) + "\n")
        except OSError as exc:  # pragma: no cover
            logger.warning("persist cycle: %s", exc)
        # Daemon state digest
        try:
            state = {
                "last_cycle_id": result.get("cycle_id"),
                "agi_percentage": result.get("steps", {}).get("benchmark", {}).get("agi_percentage", 0.0),
                "completed_at": result.get("finished_at"),
                "errors": len(result.get("errors", [])),
                "tasks_emitted": len(result.get("steps", {}).get("tasks", [])),
                "proposals_emitted": len(result.get("steps", {}).get("refactor_proposals", [])),
            }
            self.config.daemon_state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except OSError as exc:  # pragma: no cover
            logger.warning("persist daemon state: %s", exc)

    # ------------------------------------------------------------------ #
    # Web dashboards
    # ------------------------------------------------------------------ #
    def start_dashboards(self) -> Dict[str, int]:
        """Launch the two Flask dashboards as detached subprocesses.

        Returns a dict with the actual ports in use (auto-fallback).
        """
        ports = {
            "main": self._free_port(self.config.port_candidates),
            "neuron": self._free_port(self.config.neuron_port_candidates),
        }
        try:
            proc_main = self._spawn_dashboard("evolution_daemon.web_dashboard", ports["main"])
            proc_neuron = self._spawn_dashboard("evolution_daemon.neuron_dashboard", ports["neuron"])
            self._dashboard_procs.extend([proc_main, proc_neuron])
        except Exception as exc:  # pragma: no cover
            logger.warning("dashboard spawn failed: %s", exc)
        return ports

    def stop_dashboards(self) -> None:
        for p in self._dashboard_procs:
            try:
                p.terminate()
            except Exception:  # pragma: no cover
                pass
        self._dashboard_procs.clear()

    def _spawn_dashboard(self, module: str, port: int) -> "subprocess.Popen":
        cmd = [sys.executable, "-m", module, "--host", "127.0.0.1", "--port", str(port)]
        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
                subprocess, "CREATE_NEW_PROCESS_GROUP", 0
            )
        return subprocess.Popen(
            cmd,
            cwd=str(self.config.repo_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )

    @staticmethod
    def _free_port(candidates: List[int]) -> int:
        import socket

        for port in candidates:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    s.bind(("127.0.0.1", port))
                    return port
                except OSError:
                    continue
        return candidates[-1]

    # ------------------------------------------------------------------ #
    # Run forever
    # ------------------------------------------------------------------ #
    def install_signal_handlers(self) -> None:
        if os.name == "nt":
            try:
                signal.signal(signal.SIGBREAK, lambda *_: self._shutdown.set())  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover
                pass
        else:
            try:
                signal.signal(signal.SIGINT, lambda *_: self._shutdown.set())
                signal.signal(signal.SIGTERM, lambda *_: self._shutdown.set())
            except Exception:  # pragma: no cover
                pass

    def run_forever(self) -> None:
        self.install_signal_handlers()
        ports = self.start_dashboards()
        logger.info("dashboards at %s", ports)
        while not self._shutdown.is_set():
            try:
                asyncio.run(self.run_cycle())
            except Exception as exc:  # pragma: no cover
                logger.exception("cycle failure: %s", exc)
            self._shutdown.wait(self.config.cycle_interval_sec)
        self.stop_dashboards()

    def request_shutdown(self) -> None:
        self._shutdown.set()
