from typing import Any, Optional

from speace_core.cellular_brain.runtime.subsystem_plugin import SubsystemPlugin


class MetabolismCoordinator(SubsystemPlugin):
    """Coordinates metabolic resource governance (T58)."""

    @property
    def name(self) -> str:
        return "metabolism"

    def on_tick(self, context: Any) -> None:
        # Metabolic cycles are typically explicitly triggered,
        # so the tick hook is minimal for now.
        pass

    def get_metabolic_governor(self, context: Any):
        orch = context.orchestrator_ref()
        if orch._metabolic_governor is None:
            from speace_core.cellular_brain.metabolism.metabolic_governor import MetabolicGovernor
            orch._metabolic_governor = MetabolicGovernor()
        return orch._metabolic_governor

    async def run_metabolic_cycle(self, context: Any) -> Optional[dict]:
        orch = context.orchestrator_ref()
        if not orch.metabolic_governance_enabled:
            return None
        governor = self.get_metabolic_governor(context)
        result = governor.run_metabolic_cycle()
        return result

    def get_metabolic_state(self, context: Any) -> Optional[dict]:
        orch = context.orchestrator_ref()
        if not orch.metabolic_governance_enabled:
            return None
        governor = self.get_metabolic_governor(context)
        state = governor.get_metabolic_state()
        return state.model_dump()

    async def run_metabolic_audit(self, context: Any) -> Optional[list]:
        orch = context.orchestrator_ref()
        if not orch.metabolic_governance_enabled:
            return None
        from speace_core.cellular_brain.metabolism.metabolic_audit import MetabolicAudit
        governor = self.get_metabolic_governor(context)
        audit = MetabolicAudit(governor)
        results = audit.run_audit_suite()
        return [r.model_dump() for r in results]

    async def run_metabolic_real_run_audit(self, context: Any) -> Optional[dict]:
        orch = context.orchestrator_ref()
        if not orch.metabolic_governance_enabled:
            return None
        from speace_core.cellular_brain.metabolism.metabolic_real_run_audit_runner import (
            MetabolicRealRunAuditRunner,
        )
        governor = self.get_metabolic_governor(context)
        runner = MetabolicRealRunAuditRunner(governor=governor)
        suite = runner.run_audit_suite()
        return suite.model_dump()
