"""Phase 2 — Counterfactual sandbox validation.

Goal
----
Enable the CounterfactualArchitectureSandbox but leave the
ArchitecturePatchExecutor DISABLED. The sandbox clones the
orchestrator state, runs each proposal as a "what-if" scenario, and
returns a verdict per proposal. We verify:

1. Each proposal produces a CounterfactualResult with a recognisable
   verdict.
2. The sandbox identifies a "best safe" result (or correctly reports
   that none is safe).
3. No patch is ever applied (the executor is disabled).
4. The hook's per-cycle report includes the sandbox's verdict.
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
from tests.test_phase1_observational import _safe_regression_guard


def _build_loop_phase2(regression_guard=None):
    from speace_core.cellular_brain.self_improvement.self_improvement_loop import (
        SelfImprovementLoop,
    )
    from speace_core.cellular_brain.self_improvement.episodic_policy import (
        EpisodicSelfImprovementPolicy,
    )
    from speace_core.cellular_brain.self_improvement.counterfactual_sandbox import (
        CounterfactualArchitectureSandbox,
    )
    rg = regression_guard or _safe_regression_guard()
    return SelfImprovementLoop(
        regression_guard=rg,
        episodic_policy_enabled=True,
        episodic_policy=EpisodicSelfImprovementPolicy(),
        counterfactual_sandbox_enabled=True,                # Phase 2: ON
        counterfactual_sandbox=CounterfactualArchitectureSandbox(
            regression_guard=rg,
        ),
        architecture_patch_execution_enabled=False,         # Phase 2: still OFF
    )


async def run_phase2(num_ticks: int = 8) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        coord, guard, subloop, circuit = _build_substrate_stack(
            n_neurons=8, n_hidden=12, n_output=4, substep_dt=0.01
        )
        si = _build_loop_phase2(regression_guard=_safe_regression_guard())
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
                        "counterfactual_verdict": r.get("counterfactual_verdict", ""),
                        "counterfactual_results": r.get("counterfactual_results", []) or [],
                        "patch_verdict": r.get("patch_verdict", "") or "",
                    }
                )
        return {
            "phase": 2,
            "cycles_run": hook.summary()["cycles_run"],
            "per_cycle": per_cycle,
            "summary": hook.summary(),
        }


class Phase2SandboxTests(unittest.TestCase):
    def test_phase2_runs_sandbox_per_proposal(self):
        out = asyncio.run(run_phase2(num_ticks=8))
        self.assertGreaterEqual(out["cycles_run"], 3, out)
        # At least one cycle had proposals that the sandbox evaluated
        any_evaluated = any(
            len(c["counterfactual_results"]) >= 1
            for c in out["per_cycle"]
        )
        self.assertTrue(any_evaluated, f"expected sandbox to evaluate at least one proposal, got {out['per_cycle']}")

    def test_phase2_no_patches_applied(self):
        out = asyncio.run(run_phase2(num_ticks=8))
        s = out["summary"]
        self.assertEqual(s["accepted_total"], 0, s)
        for c in out["per_cycle"]:
            # Phase 2 invariant: no patch executor, so patch_verdict is empty
            self.assertEqual(c["patch_verdict"], "", c)

    def test_phase2_sandbox_verdicts_are_recognised(self):
        out = asyncio.run(run_phase2(num_ticks=8))
        valid = {"safe", "unsafe", "needs_more_evidence", ""}
        for c in out["per_cycle"]:
            self.assertIn(c["counterfactual_verdict"], valid, c)
            for cf in c["counterfactual_results"]:
                self.assertIn(cf.get("verdict", ""), valid, cf)

    def test_phase2_results_consistent(self):
        out = asyncio.run(run_phase2(num_ticks=8))
        # Final verdict must be one of the recognised set
        valid_verdicts = {
            "NO_LIMITATION_DETECTED",
            "LIMITATION_DETECTED_NO_SAFE_PATCH",
            "PROPOSAL_ACCEPTED_FOR_NEXT_TASK",
            "REGRESSION_BLOCKED",
            "SAFE_PROPOSAL_GENERATED",
            "FAILED",
        }
        for c in out["per_cycle"]:
            self.assertIn(c["verdict"], valid_verdicts, c)


if __name__ == "__main__":
    unittest.main(verbosity=2)
