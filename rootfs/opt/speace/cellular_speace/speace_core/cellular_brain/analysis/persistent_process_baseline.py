"""T-PCPB — Persistent Cognitive Process Baseline.

End-to-end demo + audit that exercises the *complete* continuous
substrate over a multi-tick run, persisting a JSONL trace that shows
the system behaving as a *persistent cognitive process* rather than a
collection of discrete steps.

The runner:

1. Builds a minimal circuit (mock or real).
2. Attaches a :class:`ContinuousSubstrateCoordinator` and a
   :class:`SubstrateStabilityGuard`.
3. Drives ``N`` outer ticks with synthetic activations.
4. After every tick records:
   - sim_time, substeps, kuramoto order parameter
   - mean energy field, fatigue count
   - total free energy, branching ratio
   - drive signals, drive modulations
   - criticality recommendation
   - selected action
   - guard verdict + recommendations
5. Writes a JSONL trace to ``data/persistent_process/baseline.jsonl``
   and a summary JSON next to it.

The test is intentionally self-contained: it does not require the
full orchestrator, the network, or any external services.
"""
from __future__ import annotations

import json
import logging
import math
import os
import random
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

_logger = logging.getLogger(__name__)


@dataclass
class BaselineConfig:
    """Configuration for the baseline run."""

    n_neurons: int = 24
    n_hidden: int = 32
    n_output: int = 8
    n_ticks: int = 60
    substep_dt: float = 0.01
    output_dir: str = "data/persistent_process"
    seed: int = 7
    drift_pattern: str = "sinusoidal"  # "sinusoidal" or "random_walk"


class _MockNeuron:
    __slots__ = ("cell_id", "activation", "threshold", "energy", "plasticity_rate", "decay")

    def __init__(self, cell_id: str):
        self.cell_id = cell_id
        self.activation = 0.0
        self.threshold = 0.5
        self.energy = 1.0
        self.plasticity_rate = 0.05
        self.decay = 0.01


class _MockSynapse:
    __slots__ = ("source", "target", "weight", "state", "decay")

    def __init__(self, source: str, target: str, weight: float = 0.5):
        self.source = source
        self.target = target
        self.weight = weight
        self.state = "active"
        self.decay = 0.001


class _MockCircuit:
    def __init__(self, n_in: int, n_hidden: int, n_out: int, seed: int = 7):
        rng = random.Random(seed)
        self.input_neurons = [_MockNeuron(f"i{i}") for i in range(n_in)]
        self.hidden_neurons = [_MockNeuron(f"h{i}") for i in range(n_hidden)]
        self.output_neurons = [_MockNeuron(f"o{i}") for i in range(n_out)]
        self.synapses: List[_MockSynapse] = []
        for pre in self.input_neurons + self.hidden_neurons:
            for post in self.hidden_neurons + self.output_neurons:
                if rng.random() < 0.15:
                    self.synapses.append(
                        _MockSynapse(pre.cell_id, post.cell_id, rng.random())
                    )


def _drive_activations(circuit: _MockCircuit, tick: int, cfg: BaselineConfig) -> Dict[str, float]:
    """Generate a smooth, time-varying activation pattern.

    The point is to *exercise* the substrate: slow sinusoids in the
    input, mild chaos in the hidden layer, decaying pulses on the
    output. This produces non-trivial phase coupling, free-energy
    dynamics, and branching ratio variations.
    """
    acts: Dict[str, float] = {}
    for i, n in enumerate(circuit.input_neurons):
        phase = (tick / max(1, cfg.n_ticks)) * 2.0 * math.pi
        n.activation = 0.5 * (1.0 + math.sin(phase + i * 0.3))
        acts[n.cell_id] = n.activation
    for i, n in enumerate(circuit.hidden_neurons):
        n.activation = 0.3 * math.sin(tick * 0.4 + i * 0.7)
        acts[n.cell_id] = n.activation
    for i, n in enumerate(circuit.output_neurons):
        n.activation = 0.2 * math.cos(tick * 0.2 + i)
        acts[n.cell_id] = n.activation
    return acts


def _drive_metrics(tick: int, cfg: BaselineConfig) -> Dict[str, float]:
    """Drive signals derived from the tick number.

    Exploration grows over the run (we are learning), stability drops
    mildly (we are perturbing), survival is mostly low (no real
    danger), efficiency oscillates.
    """
    progress = tick / max(1, cfg.n_ticks - 1)
    return {
        "exploration": 0.3 + 0.4 * progress,
        "stability": 0.5 - 0.2 * math.sin(tick * 0.3),
        "survival": 0.1 + 0.05 * abs(math.sin(tick * 0.5)),
        "efficiency": 0.5 + 0.3 * math.cos(tick * 0.2),
    }


def run_persistent_process_baseline(
    config: Optional[BaselineConfig] = None,
) -> Dict[str, Any]:
    """Run the full baseline experiment and return a summary dict."""
    cfg = config or BaselineConfig()
    os.makedirs(cfg.output_dir, exist_ok=True)
    trace_path = os.path.join(cfg.output_dir, "baseline.jsonl")
    summary_path = os.path.join(cfg.output_dir, "summary.json")

    circuit = _MockCircuit(cfg.n_neurons, cfg.n_hidden, cfg.n_output, seed=cfg.seed)

    # Build a minimal genome-mock that satisfies model_dump().
    class _DynCfg:
        def model_dump(self) -> Dict[str, Any]:
            return {}

    class _Genome:
        dynamics = _DynCfg()

    from speace_core.cellular_brain.runtime.coordinators.substrate_coordinator import (
        ContinuousSubstrateCoordinator,
    )
    from speace_core.cellular_brain.regulation.substrate_stability_guard import (
        SubstrateStabilityGuard,
    )
    from speace_core.runtime.substep_runtime_loop import SubstepRuntimeLoop

    coord = ContinuousSubstrateCoordinator(
        circuit=circuit,
        genome=_Genome(),
        substep_dt=cfg.substep_dt,
    )
    coord.initialize()
    coord.register_active_inference_states(
        {"stable": 0.5, "unstable": 0.5},
        {
            "observe": {"stable": 0.7, "unstable": 0.3},
            "actuate": {"stable": 0.3, "unstable": 0.7},
            "request_sleep": {"stable": 0.1, "unstable": 0.9},
        },
    )

    guard = SubstrateStabilityGuard(
        kuramoto_hyper_threshold=0.92,
        kuramoto_hypo_threshold=0.05,
        branching_low=0.5,
        branching_high=1.5,
    )
    loop = SubstepRuntimeLoop(
        substrate_coordinator=coord,
        stability_guard=guard,
    )

    trace: List[Dict[str, Any]] = []
    start = time.time()
    halt_requested = False
    for tick in range(cfg.n_ticks):
        activations = _drive_activations(circuit, tick, cfg)
        drives = _drive_metrics(tick, cfg)
        result = loop.advance(
            tick_interval=1.0,
            activations=activations,
            prediction_error=0.05 * abs(math.sin(tick * 0.3)),
            last_drive_metrics=drives,
        )
        snap = (
            result.substrate_state.to_dict()
            if result.substrate_state is not None
            else {}
        )
        guard_d = (
            result.guard_report.to_dict()
            if result.guard_report is not None
            else {}
        )
        entry = {
            "tick": tick,
            "wall_time": time.time(),
            "sim_time": snap.get("sim_time", 0.0),
            "substeps_total": snap.get("substeps", 0),
            "substeps_this_tick": result.n_substeps,
            "duration_ms": result.duration_ms,
            "kuramoto_order_parameter": snap.get("kuramoto_order_parameter", 0.0),
            "mean_energy_field": snap.get("mean_energy_field", 0.0),
            "fatigue_count": snap.get("fatigue_count", 0),
            "total_free_energy": snap.get("total_free_energy", 0.0),
            "branching_ratio": snap.get("branching_ratio", 0.0),
            "drives": snap.get("drives", {}),
            "modulations": snap.get("modulations", {}),
            "criticality_recommendation": snap.get("criticality_recommendation", ""),
            "selected_action": snap.get("selected_action"),
            "guard_verdict": guard_d.get("verdict", "ok"),
            "guard_reason": guard_d.get("reason", ""),
            "halt_requested": result.halt_requested,
        }
        trace.append(entry)
        with open(trace_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
        if result.halt_requested:
            halt_requested = True
            _logger.warning("Baseline halted at tick %d", tick)
            break

    elapsed = time.time() - start
    summary = _summarise(trace, cfg, elapsed, halt_requested)
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    return summary


def _summarise(
    trace: List[Dict[str, Any]],
    cfg: BaselineConfig,
    elapsed: float,
    halt_requested: bool,
) -> Dict[str, Any]:
    if not trace:
        return {"ticks_executed": 0, "halt_requested": halt_requested}

    n = len(trace)
    kuramoto = [e["kuramoto_order_parameter"] for e in trace]
    energies = [e["mean_energy_field"] for e in trace]
    free_energies = [e["total_free_energy"] for e in trace]
    branching = [e["branching_ratio"] for e in trace]
    sim_times = [e["sim_time"] for e in trace]
    substeps = [e["substeps_this_tick"] for e in trace]

    return {
        "config": {
            "n_ticks_target": cfg.n_ticks,
            "n_neurons": cfg.n_neurons,
            "n_hidden": cfg.n_hidden,
            "n_output": cfg.n_output,
            "substep_dt": cfg.substep_dt,
            "seed": cfg.seed,
        },
        "ticks_executed": n,
        "halt_requested": halt_requested,
        "wall_time_seconds": round(elapsed, 3),
        "sim_time_span": round(sim_times[-1] - sim_times[0], 3),
        "mean_substeps_per_tick": sum(substeps) / n,
        "min_substeps_per_tick": min(substeps),
        "max_substeps_per_tick": max(substeps),
        "kuramoto": {
            "min": round(min(kuramoto), 4),
            "max": round(max(kuramoto), 4),
            "mean": round(sum(kuramoto) / n, 4),
        },
        "mean_energy_field": {
            "min": round(min(energies), 4),
            "max": round(max(energies), 4),
            "mean": round(sum(energies) / n, 4),
        },
        "free_energy": {
            "min": round(min(free_energies), 4),
            "max": round(max(free_energies), 4),
            "mean": round(sum(free_energies) / n, 4),
        },
        "branching_ratio": {
            "min": round(min(branching), 4),
            "max": round(max(branching), 4),
            "mean": round(sum(branching) / n, 4),
        },
        "guard_verdicts": {
            v: sum(1 for e in trace if e["guard_verdict"] == v)
            for v in {"ok", "adjust", "dampen", "emergency"}
        },
        "actions_seen": sorted({e["selected_action"] for e in trace if e["selected_action"]}),
    }
