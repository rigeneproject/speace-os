"""Bridge script: starts SPEACE ContinuousRuntimeEngine and connects it to the agent team.

This resolves the fundamental issue: the agent team (speace_agi_team) was running but
never starting the actual SPEACE brain (speace_core). The agents were advising
each other forever while the brain stayed in stallo (tick=370, 0 neurons, 0 synapses).

Usage:
    python -m scripts.start_speace_runtime
"""
import asyncio
import sys

sys.path.insert(0, ".")


async def main():
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.dna.models import SharedGenome
    from speace_core.runtime.continuous_runtime_engine import ContinuousRuntimeEngine
    from speace_core.cellular_brain.memory.causal_model_engine import CausalModelEngine

    print("[SPEACE Runtime] Starting SPEACE brain engine...")
    genome = SharedGenome()
    orchestrator = CellularBrainOrchestrator.build_mvp(genome)
    print(f"[SPEACE Runtime] Brain initialized — tick: {orchestrator.current_tick}")

    # 2. Create the causal model engine (L3 memory)
    print("[SPEACE Runtime] Initializing CausalModelEngine (L3 memory)...")
    causal_engine = CausalModelEngine()

    # 3. Start the continuous runtime engine in simulated mode
    print("[SPEACE Runtime] Starting ContinuousRuntimeEngine (simulated mode)...")
    runtime = ContinuousRuntimeEngine(
        orchestrator=orchestrator,
        tick_interval=1.0,
        checkpoint_interval_seconds=60.0,
        runtime_mode="simulated",
        simulated_tick_seconds=0.5,
    )

    # Attach causal engine as a subsystem
    runtime._causal_engine = causal_engine

    # 4. Get region info
    region_names = []
    if orchestrator._region_registry:
        if hasattr(orchestrator._region_registry, 'regions'):
            region_names = [r.name for r in orchestrator._region_registry.regions.values() if hasattr(r, 'name')]
        elif hasattr(orchestrator._region_registry, 'name'):
            region_names = [orchestrator._region_registry.name]

    print("[SPEACE Runtime] Brain engine ready.")
    print(f"  Initial tick: {orchestrator.current_tick}")
    print(f"  Regions: {region_names}")

    # 4. Run the runtime for a limited time to bootstrap the system
    print("[SPEACE Runtime] Running bootstrap ticks...")
    runtime.attach_continuous_substrate(orchestrator)
    await runtime.start()

    # Wait for some ticks to advance
    await asyncio.sleep(5.0)

    # 5. Check state after bootstrap
    final_tick = orchestrator.current_tick
    regions = []
    if orchestrator._region_registry:
        if hasattr(orchestrator._region_registry, 'regions'):
            regions = list(orchestrator._region_registry.regions.values())
        elif hasattr(orchestrator._region_registry, 'name'):
            regions = [orchestrator._region_registry]
    active_neurons = 0
    for r in regions:
        if hasattr(r, 'count_active'):
            active_neurons += r.count_active()
        elif hasattr(r, 'neurons'):
            active_neurons += sum(1 for n in r.neurons if getattr(n, 'active', False))

    print(f"\n[SPEACE Runtime] Bootstrap complete.")
    print(f"  Current tick: {final_tick}")
    print(f"  Active neurons: {active_neurons}")
    print(f"  Status: {'ADVANCED' if final_tick > 0 else 'STILL_STALLED'}")

    # 6. Keep running (or exit cleanly)
    await runtime.stop()
    print("[SPEACE Runtime] Runtime stopped cleanly.")


if __name__ == "__main__":
    asyncio.run(main())