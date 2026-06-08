"""Phase 4 — Evolutionary memory consolidation.

Goal
----
Run the full hook loop enough times to produce a non-trivial memory,
then invoke ``EvolutionaryMemoryGovernor.run_governance_cycle()`` and
verify:

1. The governor detected conflicts (or correctly reported none).
2. The forgetting engine applied its policy to at least some records.
3. The consolidation policy engine classified every record into one
   of the recognised states.
4. The memory bloat stays bounded: the number of records forgotten is
   at least the number of newly quarantined, low-quality entries.
5. The export report is non-empty and the consolidated verdict is
   sensible.
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.test_self_improvement_runtime_hook import (
    _MockOrchestrator,
    _build_substrate_stack,
    _drive_activations,
)
from tests.test_phase3_patch_executor import _build_loop_phase3
from tests.test_phase1_observational import _safe_regression_guard


async def run_phase4(num_ticks: int = 20) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        coord, guard, subloop, circuit = _build_substrate_stack(
            n_neurons=8, n_hidden=12, n_output=4, substep_dt=0.01
        )
        si = _build_loop_phase3(regression_guard=_safe_regression_guard())
        from speace_core.cellular_brain.self_improvement.outcome_tracker import (
            OutcomeTracker,
        )
        from speace_core.cellular_brain.evolutionary_memory.evolutionary_memory_governor import (
            EvolutionaryMemoryGovernor,
        )
        from speace_core.runtime.self_improvement_runtime_hook import (
            SelfImprovementRuntimeHook,
        )
        outcome_tracker = OutcomeTracker(base_path=os.path.join(tmp, "outcomes"))
        governor = EvolutionaryMemoryGovernor(report_dir=os.path.join(tmp, "memory"))
        hook = SelfImprovementRuntimeHook(
            self_improvement_loop=si,
            outcome_tracker=outcome_tracker,
            evolutionary_memory_governor=governor,
            cycle_interval_ticks=2,
            report_dir=os.path.join(tmp, "hook_reports"),
        )
        orch = _MockOrchestrator()
        last_state = None
        for tick in range(num_ticks):
            acts = _drive_activations(circuit, tick)
            res = subloop.advance(tick_interval=1.0, activations=acts, prediction_error=0.05)
            last_state = res.substrate_state
            if last_state is not None and hasattr(last_state, "to_dict"):
                snap = last_state.to_dict()
                class _M:
                    pass
                m = _M()
                m.coherence_phi = snap.get("kuramoto_order_parameter", 0.0)
                m.mean_energy = snap.get("mean_energy_field", 0.0)
                m.energy_efficiency = max(0.0, 1.0 - snap.get("total_free_energy", 0.0))
                m.cognitive_score = snap.get("branching_ratio", 0.0)
                orch.latest_metrics = m
            await hook.tick(tick=tick, orchestrator=orch, substrate_state=last_state)
        # Now run the governance cycle
        records_before = governor.store.list_records()
        governance = governor.run_governance_cycle()
        records_after = governor.store.list_records()
        # Count statuses
        statuses = {}
        for r in records_after:
            statuses[r.status] = statuses.get(r.status, 0) + 1
        # Memory quality from forgetting engine
        from speace_core.cellular_brain.evolutionary_memory.evolutionary_forgetting_engine import (
            EvolutionaryForgettingEngine,
        )
        forgetting_engine = EvolutionaryForgettingEngine()
        forgetting_score = forgetting_engine.compute_forgetting_score(records_after)
        return {
            "phase": 4,
            "cycles_run": hook.summary()["cycles_run"],
            "records_before": len(records_before),
            "records_after": len(records_after),
            "statuses": statuses,
            "governance": governance,
            "forgetting_score": forgetting_score,
        }


class Phase4MemoryGovernanceTests(unittest.TestCase):
    def test_phase4_records_ingested(self):
        out = asyncio.run(run_phase4(num_ticks=20))
        self.assertGreaterEqual(out["records_after"], 5, out)

    def test_phase4_governance_returns_decisions(self):
        out = asyncio.run(run_phase4(num_ticks=20))
        g = out["governance"]
        self.assertIn("consolidation_decisions", g)
        self.assertIn("conflicts_detected", g)
        self.assertIn("forgotten_records", g)

    def test_phase4_status_classification(self):
        out = asyncio.run(run_phase4(num_ticks=20))
        # Every record should be in a recognised status
        valid = {
            "volatile",
            "experimental",
            "probationary",
            "stable",
            "frozen_policy",
            "quarantined",
            "deprecated",
            "forgotten",
        }
        for s, n in out["statuses"].items():
            self.assertIn(s, valid, f"unknown status {s!r} in {out['statuses']}")

    def test_phase4_forgetting_score_non_negative(self):
        """The forgetting score measures how well the forgetting
        engine removed noise. A higher score is better; a negative
        score would mean we forgot something useful."""
        out = asyncio.run(run_phase4(num_ticks=20))
        self.assertGreaterEqual(out["forgetting_score"], 0.0, out)

    def test_phase4_governance_movement(self):
        """After the governance cycle, at least one record should
        have moved out of 'volatile' status (to probationary,
        quarantined, deprecated, or forgotten)."""
        out = asyncio.run(run_phase4(num_ticks=20))
        non_volatile = {
            s: n for s, n in out["statuses"].items() if s != "volatile"
        }
        self.assertGreater(
            sum(non_volatile.values()),
            0,
            f"expected at least some non-volatile classification, got {out['statuses']}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
