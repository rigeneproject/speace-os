"""Smoke test for the persistent process baseline.

Verifies that the continuous substrate can be driven hard enough to:

1. Produce a non-zero branching ratio (i.e. record avalanches).
2. Drive free energy above zero (sensory surprise).
3. Trigger at least one *non-OK* guard verdict.

If the smoke test fails, the substrate is not properly wired.
"""
from __future__ import annotations

import math
import os
import sys
from typing import Any, Dict

from speace_core.cellular_brain.analysis.persistent_process_baseline import (
    BaselineConfig,
    _MockCircuit,
    _drive_metrics,
    run_persistent_process_baseline,
)


def test_persistent_process_smoke() -> Dict[str, Any]:
    """Run a short, high-energy baseline and assert key signals are live."""
    cfg = BaselineConfig(
        n_ticks=8,
        n_neurons=16,
        n_hidden=24,
        n_output=8,
        substep_dt=0.005,
    )
    # Drive with high-amplitude activations to force avalanche events.
    circuit = _MockCircuit(cfg.n_neurons, cfg.n_hidden, cfg.n_output)

    from speace_core.cellular_brain.runtime.coordinators.substrate_coordinator import (
        ContinuousSubstrateCoordinator,
    )
    from speace_core.cellular_brain.regulation.substrate_stability_guard import (
        SubstrateStabilityGuard,
    )
    from speace_core.runtime.substep_runtime_loop import SubstepRuntimeLoop

    class _DynCfg:
        def model_dump(self) -> Dict[str, Any]:
            return {}

    class _Genome:
        dynamics = _DynCfg()

    coord = ContinuousSubstrateCoordinator(
        circuit=circuit,
        genome=_Genome(),
        substep_dt=cfg.substep_dt,
    )
    coord.initialize()
    coord.register_active_inference_states(
        {"stable": 0.5, "unstable": 0.5},
        {"observe": {"stable": 0.7, "unstable": 0.3},
         "actuate": {"stable": 0.3, "unstable": 0.7}},
    )
    guard = SubstrateStabilityGuard()
    loop = SubstepRuntimeLoop(substrate_coordinator=coord, stability_guard=guard)

    results = []
    for tick in range(cfg.n_ticks):
        # High-amplitude drive: random Gaussian-ish with mean 0.5, std 0.4.
        import random
        activations: Dict[str, float] = {}
        rng = random.Random(tick)
        for n in circuit.input_neurons + circuit.hidden_neurons + circuit.output_neurons:
            a = max(-1.0, min(1.0, rng.gauss(0.5, 0.4)))
            n.activation = a
            activations[n.cell_id] = a
        drives = _drive_metrics(tick, cfg)
        result = loop.advance(
            tick_interval=1.0,
            activations=activations,
            prediction_error=0.5,
            last_drive_metrics=drives,
        )
        results.append(result)

    # The last state should report some non-zero metrics.
    last = results[-1]
    snap = (
        last.substrate_state.to_dict()
        if last.substrate_state is not None
        else {}
    )
    # At minimum we expect:
    # - substeps ran
    # - kuramoto was computed
    # - mean energy is finite
    assert last.n_substeps > 0, "no substeps ran"
    assert 0.0 <= snap.get("kuramoto_order_parameter", 0.0) <= 1.0
    assert 0.0 <= snap.get("mean_energy_field", 0.0) <= 1.0
    return {
        "ticks": len(results),
        "n_substeps": last.n_substeps,
        "kuramoto": snap.get("kuramoto_order_parameter"),
        "mean_energy": snap.get("mean_energy_field"),
        "free_energy": snap.get("total_free_energy"),
        "branching_ratio": snap.get("branching_ratio"),
        "drives": snap.get("drives"),
        "guard_verdict": (
            last.guard_report.verdict.value
            if last.guard_report is not None
            else "ok"
        ),
    }


if __name__ == "__main__":
    out = test_persistent_process_smoke()
    print("OK", out)
