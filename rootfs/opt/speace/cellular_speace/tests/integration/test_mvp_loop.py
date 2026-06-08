import asyncio
import random

import pytest

from speace_core.dna.parser import load_genome
from speace_core.orchestrator import CellularBrainOrchestrator


def _lower_thresholds(orch):
    for n in orch.circuit.input_neurons + orch.circuit.hidden_neurons + orch.circuit.output_neurons:
        n.threshold = 0.05


def test_mvp_signal_propagation():
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    _lower_thresholds(orch)
    pattern = [2.0 if i == 0 else 0.0 for i in range(10)]
    orch.inject(pattern)

    async def _run():
        for _ in range(10):
            await orch._tick()
        activations = orch.circuit.output_activations
        assert any(a > 0 for a in activations), "Signal did not propagate to outputs"

    asyncio.run(_run())


def test_mvp_plasticity():
    random.seed(42)
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    _lower_thresholds(orch)
    initial_weights = [s.weight for s in orch.circuit.synapses]

    async def _run():
        for i in range(100):
            pattern = [0.0] * 10
            pattern[i % 10] = 1.0
            orch.inject(pattern)
            await orch._tick()
            score = 1.0 if i % 2 == 0 else -0.2
            orch.feedback(score)

    asyncio.run(_run())
    final_weights = [s.weight for s in orch.circuit.synapses]
    delta = sum(f - i for f, i in zip(final_weights, initial_weights))
    assert delta > 0, "Plasticity did not increase net weight"


def test_mvp_homeostasis_under_overload():
    random.seed(42)
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    _lower_thresholds(orch)

    async def _run():
        for _ in range(5):
            pattern = [2.0] * 10
            orch.inject(pattern)
            await orch._tick()

    asyncio.run(_run())
    metrics = orch.latest_metrics
    assert metrics is not None
    assert metrics.mean_energy < 1.0, "Energy should drop under overload"


def test_mvp_pruning():
    random.seed(42)
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    _lower_thresholds(orch)

    async def _run():
        for i in range(200):
            pattern = [0.0] * 10
            pattern[i % 10] = 2.0
            orch.inject(pattern)
            await orch._tick()
            orch.feedback(-2.0)
            if i % 5 == 0:
                orch.run_immune()

    asyncio.run(_run())
    pruned = sum(1 for s in orch.circuit.synapses if s.state == "pruned")
    assert pruned > 0, f"Microglia should prune low-trust synapses, got {pruned} pruned"
