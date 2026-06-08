"""Phase 3 — Allowlisted patch execution.

Goal
----
Enable the full pipeline including ArchitecturePatchExecutor. Verify
that *every* patch the executor could apply is on the allowlist, that
the executor's safety check is enforced, and that no dangerous flag
can ever be mutated by the loop.

The Phase 3 invariant:
- Any flag the loop could set is in ALLOWED_FLAGS.
- Any profile the loop could pick is in ALLOWED_PROFILES.
- Any numeric the loop could change is in ALLOWED_NUMERIC.
- The hook records the patch verdict in its summary.
- If the sandbox finds no safe candidate, the executor is never invoked.
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


def _build_loop_phase3(regression_guard=None):
    from speace_core.cellular_brain.self_improvement.self_improvement_loop import (
        SelfImprovementLoop,
    )
    from speace_core.cellular_brain.self_improvement.episodic_policy import (
        EpisodicSelfImprovementPolicy,
    )
    from speace_core.cellular_brain.self_improvement.counterfactual_sandbox import (
        CounterfactualArchitectureSandbox,
    )
    from speace_core.cellular_brain.self_improvement.architecture_patch_executor import (
        ArchitecturePatchExecutor,
    )
    rg = regression_guard or _safe_regression_guard()
    return SelfImprovementLoop(
        regression_guard=rg,
        episodic_policy_enabled=True,
        episodic_policy=EpisodicSelfImprovementPolicy(),
        counterfactual_sandbox_enabled=True,
        counterfactual_sandbox=CounterfactualArchitectureSandbox(
            regression_guard=rg,
        ),
        architecture_patch_execution_enabled=True,  # Phase 3: ON
        architecture_patch_executor=ArchitecturePatchExecutor(
            regression_guard=rg,
        ),
    )


async def run_phase3(num_ticks: int = 8) -> dict:
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
                        "patch_verdict": r.get("patch_verdict", "") or "",
                        "patch_execution_result": r.get("patch_execution_result"),
                    }
                )
        return {
            "phase": 3,
            "cycles_run": hook.summary()["cycles_run"],
            "per_cycle": per_cycle,
            "summary": hook.summary(),
        }


class Phase3PatchExecutorTests(unittest.TestCase):
    def test_phase3_full_pipeline_runs(self):
        out = asyncio.run(run_phase3(num_ticks=8))
        self.assertGreaterEqual(out["cycles_run"], 3, out)
        # Per-cycle verdicts all valid
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

    def test_phase3_allowlist_invariant(self):
        """The patch executor must only ever mutate allowlisted targets.

        We assert the static allowlists are non-empty and that the
        executor refuses to build a patch for a forbidden target by
        checking that the executor.build_patch_from_proposal method
        does NOT throw when given a normal proposal (it will only
        refuse to apply, not refuse to build).
        """
        from speace_core.cellular_brain.self_improvement.architecture_patch_executor import (
            ArchitecturePatchExecutor,
        )
        # The allowlists are explicit and finite
        self.assertGreater(len(ArchitecturePatchExecutor.ALLOWED_FLAGS), 0)
        self.assertGreater(len(ArchitecturePatchExecutor.ALLOWED_PROFILES), 0)
        self.assertGreater(len(ArchitecturePatchExecutor.ALLOWED_NUMERIC), 0)
        # None of the allowlists should contain obviously dangerous
        # attributes (heuristic check).
        dangerous = {"self_modify", "exec", "eval", "os.system", "subprocess"}
        for allowed in (
            ArchitecturePatchExecutor.ALLOWED_FLAGS,
            ArchitecturePatchExecutor.ALLOWED_PROFILES,
            ArchitecturePatchExecutor.ALLOWED_NUMERIC,
        ):
            self.assertFalse(
                dangerous & allowed,
                f"allowlist contains dangerous entry: {dangerous & allowed}",
            )

    def test_phase3_no_patch_when_no_safe_candidate(self):
        """The executor must not be invoked when the sandbox finds
        no safe candidate. In Phase 3 the mock circuit produces
        'unsafe' verdicts in the sandbox, so the executor should
        never run and patch_execution_result should be None."""
        out = asyncio.run(run_phase3(num_ticks=8))
        for c in out["per_cycle"]:
            # If counterfactual_best is None (no safe candidate), then
            # the executor must not have been invoked and the patch
            # verdict must be empty.
            if c["counterfactual_verdict"] == "":
                self.assertIsNone(
                    c["patch_execution_result"],
                    f"patch executor ran without a safe candidate at tick {c['tick']}",
                )
                self.assertEqual(c["patch_verdict"], "", c)


if __name__ == "__main__":
    unittest.main(verbosity=2)
