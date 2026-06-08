"""Phase 1 — Observational self-improvement loop.

Goal
----
Run the SelfImprovementLoop end-to-end in *pure observational mode*:
the LimitationDetector reads substrate metrics and detects limitations;
the ArchitectureRewriter proposes patches; the loop assigns verdicts.
But the counterfactual sandbox and the architecture patch executor are
DISABLED, so no mutation is ever evaluated or applied.

Success criteria
----------------
1. The loop runs at least 1 detection cycle on the supplied metrics.
2. Every verdict is in the recognised set.
3. The summary distinguishes "no limitation" from "limitation detected,
   no safe patch" — the two safe verdicts the loop should produce
   without sandbox/patch.
4. The hook's outcome tracker and learning engine receive the cycle
   results without raising.
5. The evolutionary memory governor has consumed at least one record.
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# Reuse the same substrate / mock helpers as the end-to-end test
from tests.test_self_improvement_runtime_hook import (
    _MockCircuit,
    _MockOrchestrator,
    _build_substrate_stack,
    _drive_activations,
)


def _build_loop_observational(regression_guard=None):
    """Self-improvement loop with NO sandbox and NO patch executor."""
    from speace_core.cellular_brain.self_improvement.self_improvement_loop import (
        SelfImprovementLoop,
    )
    return SelfImprovementLoop(
        regression_guard=regression_guard,
        episodic_policy_enabled=False,
        counterfactual_sandbox_enabled=False,  # Phase 1: disabled
        architecture_patch_execution_enabled=False,  # Phase 1: disabled
    )


def _safe_regression_guard():
    class _G:
        def evaluate(self, delta):
            class _R:
                verdict = "POLICY_SAFE"
            return _R()
    return _G()


def _build_hook_observational(report_dir, si, outcome_tracker, governor):
    from speace_core.runtime.self_improvement_runtime_hook import (
        SelfImprovementRuntimeHook,
    )
    return SelfImprovementRuntimeHook(
        self_improvement_loop=si,
        outcome_tracker=outcome_tracker,
        evolutionary_memory_governor=governor,
        cycle_interval_ticks=2,
        report_dir=report_dir,
    )


async def run_phase1(num_ticks: int = 8) -> dict:
    """Run Phase 1 end-to-end and return the hook's final summary."""
    with tempfile.TemporaryDirectory() as tmp:
        # 1. Substrate
        coord, guard, subloop, circuit = _build_substrate_stack(
            n_neurons=8, n_hidden=12, n_output=4, substep_dt=0.01
        )
        # 2. Self-improvement loop (observational)
        si = _build_loop_observational(regression_guard=_safe_regression_guard())
        # 3. Outcome tracker + governor
        from speace_core.cellular_brain.self_improvement.outcome_tracker import (
            OutcomeTracker,
        )
        from speace_core.cellular_brain.evolutionary_memory.evolutionary_memory_governor import (
            EvolutionaryMemoryGovernor,
        )
        outcome_tracker = OutcomeTracker(base_path=os.path.join(tmp, "outcomes"))
        governor = EvolutionaryMemoryGovernor(
            report_dir=os.path.join(tmp, "memory")
        )
        # 4. Hook
        hook = _build_hook_observational(
            os.path.join(tmp, "hook_reports"),
            si=si,
            outcome_tracker=outcome_tracker,
            governor=governor,
        )
        # 5. Drive
        orch = _MockOrchestrator()
        last_state = None
        per_cycle = []
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
            r = await hook.tick(tick=tick, orchestrator=orch, substrate_state=last_state)
            if r is not None:
                per_cycle.append(
                    {
                        "tick": tick,
                        "verdict": r.get("final_verdict"),
                        "diagnoses": len(r.get("diagnoses", []) or []),
                        "proposals": len(r.get("proposals", []) or []),
                        "accepted": len(r.get("accepted_proposals", []) or []),
                        "rejected": len(r.get("rejected_proposals", []) or []),
                        "counterfactual_verdict": r.get("counterfactual_verdict", ""),
                        "patch_verdict": r.get("patch_verdict", "") or "",
                    }
                )
        # 6. Inspect reports and memory
        all_reports = []
        for root, _, files in os.walk(tmp):
            for f in files:
                if f.startswith("cycle_") and f.endswith(".json"):
                    with open(os.path.join(root, f), "r", encoding="utf-8") as fh:
                        all_reports.append(json.load(fh))
        memory_records = governor.store.list_records()
        return {
            "phase": 1,
            "ticks_executed": num_ticks,
            "cycles_run": hook.summary()["cycles_run"],
            "per_cycle": per_cycle,
            "reports_written": len(all_reports),
            "memory_records": len(memory_records),
            "summary": hook.summary(),
        }


class Phase1ObservationalTests(unittest.TestCase):
    def test_phase1_runs_at_least_one_cycle(self):
        out = asyncio.run(run_phase1(num_ticks=8))
        # At least 3 cycles with cycle_interval=2 across 8 ticks (0,2,4,6)
        self.assertGreaterEqual(out["cycles_run"], 3, out)
        # At least one report written
        self.assertGreaterEqual(out["reports_written"], 3, out)
        # Memory governor ingested at least one record
        self.assertGreaterEqual(out["memory_records"], 3, out)
        # Per-cycle verdicts are all recognised
        valid = {
            "NO_LIMITATION_DETECTED",
            "LIMITATION_DETECTED_NO_SAFE_PATCH",
            "PROPOSAL_ACCEPTED_FOR_NEXT_TASK",
            "REGRESSION_BLOCKED",
            "SAFE_PROPOSAL_GENERATED",
            "FAILED",
        }
        for c in out["per_cycle"]:
            self.assertIn(c["verdict"], valid, c)
            # Phase 1 invariant: no patch executor, so no patch_verdict
            self.assertEqual(c["patch_verdict"], "", c)
            # Phase 1 invariant: no sandbox, so no counterfactual verdict
            self.assertEqual(c["counterfactual_verdict"], "", c)

    def test_phase1_emits_diagnoses(self):
        out = asyncio.run(run_phase1(num_ticks=8))
        # The mock circuit has cellular_resilience_score=0, so the
        # detector should pick up 'cellular_damage' on at least one
        # cycle.
        any_diagnoses = any(c["diagnoses"] >= 1 for c in out["per_cycle"])
        self.assertTrue(any_diagnoses, f"expected at least one cycle with diagnoses, got {out['per_cycle']}")

    def test_phase1_no_patches_applied(self):
        """In Phase 1, architecture_patch_execution is disabled, so
        the hook's accepted_total should be 0 (no patch was ever
        applied)."""
        out = asyncio.run(run_phase1(num_ticks=8))
        s = out["summary"]
        self.assertEqual(s["accepted_total"], 0, s)


if __name__ == "__main__":
    unittest.main(verbosity=2)
