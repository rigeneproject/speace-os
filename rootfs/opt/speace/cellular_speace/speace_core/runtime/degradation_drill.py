"""DegradationDrill — controlled stress tests for graceful degradation (T114).

Simulates high load, resource starvation, and partial failures. Verifies
that SPEACE remains safe and only degrades reversibly.
"""

import asyncio
import json
import random
import time
from typing import Any, Callable, Dict, List, Optional


class DegradationDrill:
    """Executes degradation drills and records outcomes."""

    SCENARIOS = ("memory_pressure", "tick_latency_spike", "exception_burst", "subsystem_failure")

    def __init__(
        self,
        orchestrator: Any,
        health_monitor: Any,
        degradation_handler: Any,
        narrative_engine: Any = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.health_monitor = health_monitor
        self.degradation_handler = degradation_handler
        self.narrative_engine = narrative_engine
        self._drill_log: List[Dict[str, Any]] = []
        self._original_tick_interval: Optional[float] = None
        self._injected_faults: List[str] = []

    # ------------------------------------------------------------------ #
    # Drill execution
    # ------------------------------------------------------------------ #

    async def run_drill(
        self,
        scenario: str = "memory_pressure",
        duration_seconds: float = 30.0,
    ) -> Dict[str, Any]:
        if scenario not in self.SCENARIOS:
            raise ValueError(f"Unknown scenario {scenario}. Choose from {self.SCENARIOS}")

        self._drill_log.clear()
        self._injected_faults.clear()
        self._original_tick_interval = getattr(self.orchestrator, "tick_interval", 1.0)

        start = time.time()
        self._log_event("drill_start", scenario=scenario)

        # Inject fault
        fault_remover = self._inject_fault(scenario)

        try:
            while (time.time() - start) < duration_seconds:
                await asyncio.sleep(1.0)
                self._sample()
        finally:
            fault_remover()
            self._restore_state()

        report = self._build_report(scenario, start)
        self._log_event("drill_end", scenario=scenario, report=report)
        return report

    # ------------------------------------------------------------------ #
    # Fault injection
    # ------------------------------------------------------------------ #

    def _inject_fault(self, scenario: str) -> Callable[[], None]:
        """Returns a callable that removes the injected fault."""
        if scenario == "memory_pressure":
            # Simulate memory pressure by allocating a large buffer on orchestrator
            buf: List[bytes] = []
            for _ in range(10):
                buf.append(b"x" * (2 * 1024 * 1024))  # 20 MB total
            self.orchestrator._drill_memory_buffer = buf
            self._injected_faults.append("memory_pressure_20mb")

            def remover():
                if hasattr(self.orchestrator, "_drill_memory_buffer"):
                    delattr(self.orchestrator, "_drill_memory_buffer")

            return remover

        if scenario == "tick_latency_spike":
            orig_tick = self.orchestrator._tick
            delay = 2.0  # seconds

            async def delayed_tick():
                await asyncio.sleep(delay)
                await orig_tick()

            self.orchestrator._tick = delayed_tick
            self._injected_faults.append(f"tick_latency_{delay}s")

            def remover():
                self.orchestrator._tick = orig_tick

            return remover

        if scenario == "exception_burst":
            orig_tick = self.orchestrator._tick
            call_count = [0]

            async def failing_tick():
                call_count[0] += 1
                if call_count[0] % 3 == 0:
                    raise RuntimeError("injected_exception")
                await orig_tick()

            self.orchestrator._tick = failing_tick
            self._injected_faults.append("exception_every_3_ticks")

            def remover():
                self.orchestrator._tick = orig_tick

            return remover

        if scenario == "subsystem_failure":
            # Disable a critical subsystem temporarily
            self._saved_subsystems: Dict[str, Any] = {}
            for attr in ("global_workspace_enabled", "predictive_coding_enabled"):
                self._saved_subsystems[attr] = getattr(self.orchestrator, attr, True)
                setattr(self.orchestrator, attr, False)
            self._injected_faults.append("subsystem_disable_gw_pc")

            def remover():
                for attr, val in self._saved_subsystems.items():
                    setattr(self.orchestrator, attr, val)

            return remover

        return lambda: None

    def _restore_state(self) -> None:
        if self._original_tick_interval is not None:
            self.orchestrator.tick_interval = self._original_tick_interval

    # ------------------------------------------------------------------ #
    # Sampling
    # ------------------------------------------------------------------ #

    def _sample(self) -> None:
        try:
            import psutil
            rss = psutil.Process().memory_info().rss / (1024 * 1024)
        except Exception:
            rss = 0.0
        self._drill_log.append({
            "timestamp": time.time(),
            "health_score": self.health_monitor.health_score(),
            "rss_mb": rss,
            "tick_latency_ms": self.health_monitor._tick_latency_ms,
            "consecutive_exceptions": self.health_monitor._consecutive_exceptions,
        })

    # ------------------------------------------------------------------ #
    # Report construction
    # ------------------------------------------------------------------ #

    def _build_report(self, scenario: str, start: float) -> Dict[str, Any]:
        if not self._drill_log:
            return {"scenario": scenario, "status": "no_samples"}

        health_values = [s["health_score"] for s in self._drill_log]
        min_health = min(health_values)
        avg_health = sum(health_values) / len(health_values)
        max_exceptions = max(s["consecutive_exceptions"] for s in self._drill_log)

        # Evaluate degradation actions triggered
        actions = self.degradation_handler.summary().get("actions_applied", [])
        drill_actions = [a for a in actions if a.get("timestamp", 0) >= start]

        # Pass criteria
        passed = (
            min_health >= 0.0  # never reached critical halt
            and all(a["action"] != "enter_conservation" for a in drill_actions)
        )

        return {
            "scenario": scenario,
            "duration_seconds": time.time() - start,
            "min_health": min_health,
            "avg_health": avg_health,
            "max_consecutive_exceptions": max_exceptions,
            "degradation_actions": drill_actions,
            "injected_faults": self._injected_faults,
            "passed": passed,
            "samples": len(self._drill_log),
        }

    # ------------------------------------------------------------------ #
    # Logging
    # ------------------------------------------------------------------ #

    def _log_event(self, event: str, **kwargs: Any) -> None:
        if self.narrative_engine is not None:
            try:
                self.narrative_engine.record(
                    event_type=f"degradation_drill_{event}",
                    description=f"T114 drill {event}: {kwargs.get('scenario', 'unknown')}",
                    importance=6,
                    metadata=kwargs,
                )
            except Exception:
                pass
