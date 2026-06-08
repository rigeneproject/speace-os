from typing import Any, Optional

from speace_core.cellular_brain.runtime.subsystem_plugin import SubsystemPlugin


class EvolutionCoordinator(SubsystemPlugin):
    """Coordinates evolutionary engines (T55-T57)."""

    @property
    def name(self) -> str:
        return "evolution"

    def on_tick(self, context: Any) -> None:
        # Evolution runs are typically async and explicitly triggered,
        # so the tick hook is minimal for now.
        pass

    def get_edd_cvt_kernel(self, context: Any):
        orch = context.orchestrator_ref()
        if orch._edd_cvt_kernel is None and orch.edd_cvt_kernel_enabled:
            from speace_core.cellular_brain.evolutionary_kernel.edd_cvt_kernel import (
                EDDCVTEvolutionaryKernel,
            )

            orch._edd_cvt_kernel = EDDCVTEvolutionaryKernel(
                orchestrator=orch,
                enabled=orch.edd_cvt_kernel_enabled,
            )
        return orch._edd_cvt_kernel

    async def run_edd_cvt_cycle(self, context: Any) -> Optional[Any]:
        orch = context.orchestrator_ref()
        if not orch.edd_cvt_kernel_enabled:
            return None
        kernel = self.get_edd_cvt_kernel(context)
        if kernel is None:
            return None
        result = await kernel.run_cycle(tick=orch.current_tick)
        return result

    def get_multi_cycle_evolution_runner(self, context: Any):
        from speace_core.cellular_brain.evolutionary_kernel.multi_cycle_evolution_runner import (
            MultiCycleEvolutionRunner,
        )
        return MultiCycleEvolutionRunner(orchestrator=context.orchestrator_ref())

    async def run_multi_cycle_evolution(self, context: Any, cycle_count: int = 5) -> Optional[Any]:
        runner = self.get_multi_cycle_evolution_runner(context)
        runner.cycle_count = cycle_count
        result = await runner.run()
        return result

    def get_evolutionary_memory_governor(self, context: Any):
        orch = context.orchestrator_ref()
        if orch._evolutionary_memory_governor is None:
            from speace_core.cellular_brain.evolutionary_memory.evolutionary_memory_governor import (
                EvolutionaryMemoryGovernor,
            )
            orch._evolutionary_memory_governor = EvolutionaryMemoryGovernor()
        return orch._evolutionary_memory_governor

    async def run_evolutionary_memory_governance_cycle(self, context: Any) -> Optional[dict]:
        orch = context.orchestrator_ref()
        if not orch.evolutionary_memory_governance_enabled:
            return None
        governor = self.get_evolutionary_memory_governor(context)
        result = governor.run_governance_cycle()
        return result
