"""GameAIIntegrationCoordinator — orchestrates T163–T166 into a bio-inspired pipeline (T169).

Pipeline per tick:
1. FSM (OrganismStateMachine) — sets global organismic context.
2. Utility AI (UtilityDriveSystem + ArbitrationEngine) — weights module priorities.
3. Behavior Trees (BTRuntimeIntegration) — fast local reflexes; skipped if degraded.
4. GOAP (GOAPRuntimeIntegration) — triggered when BT fails or confidence low.
5. Governance / Metacognition — evaluates proposals; confidence check.
6. Execution / Proposal — approved actions queued; all logged.

Lower layers can suppress or escalate:
- BT can escalate to GOAP if leaf action returns FAILURE and goal remains urgent.
- GOAP can abort and fall back to BT if planning confidence < 0.3.
- Utility can globally suppress BTs by zeroing their module weight.
- FSM overloaded state can bypass non-safety BTs entirely.
"""

import time
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.cognition.bt_runtime_integration import BTRuntimeIntegration
from speace_core.cellular_brain.cognition.goap_runtime_integration import GOAPRuntimeIntegration
from speace_core.cellular_brain.cognition.organism_state_machine import OrganismStateMachine
from speace_core.cellular_brain.dynamics.dopaminergic_drive_circuit import DopaminergicModulator
from speace_core.cellular_brain.dynamics.predictive_tension_layer import PredictiveTensionLayer
from speace_core.cellular_brain.experience.temporal_narrative_engine import TemporalNarrativeEngine
from speace_core.cellular_brain.regulation.utility_arbitration_engine import UtilityArbitrationEngine
from speace_core.cellular_brain.regulation.utility_drive_system import UtilityDriveSystem


class ProposalBag:
    """Container for proposals from a pipeline layer."""

    def __init__(self, source_layer: str) -> None:
        self.source_layer = source_layer
        self.proposals: List[Dict[str, Any]] = []

    def add(self, proposal: Dict[str, Any]) -> None:
        proposal["source_layer"] = self.source_layer
        self.proposals.append(proposal)


class GameAIIntegrationCoordinator:
    """Coordinates the hierarchical game-AI pipeline."""

    def __init__(
        self,
        organism_state_machine: OrganismStateMachine,
        utility_drive_system: UtilityDriveSystem,
        utility_arbitration: UtilityArbitrationEngine,
        bt_integration: BTRuntimeIntegration,
        goap_integration: GOAPRuntimeIntegration,
        narrative_engine: Optional[TemporalNarrativeEngine] = None,
        max_pipeline_ms: float = 50.0,
        dopaminergic_modulator: Optional[DopaminergicModulator] = None,
        predictive_tension: Optional[PredictiveTensionLayer] = None,
    ) -> None:
        self.fsm = organism_state_machine
        self.drive_system = utility_drive_system
        self.arbitration = utility_arbitration
        self.bt = bt_integration
        self.goap = goap_integration
        self._narrative_engine = narrative_engine
        self._max_pipeline_ms = max_pipeline_ms
        self._dopaminergic = dopaminergic_modulator
        self._predictive_tension = predictive_tension

        self._tick_count: int = 0
        self._last_proposals: List[Dict[str, Any]] = []
        self._last_latencies_ms: Dict[str, float] = {}
        self._degraded_mode: bool = False

    # ------------------------------------------------------------------ #
    # Main pipeline tick
    # ------------------------------------------------------------------ #

    def tick(
        self,
        *,
        health_score: float = 0.0,
        cognitive_load: float = 0.0,
        prediction_error: float = 0.0,
        energy: float = 1.0,
        curiosity_score: float = 0.0,
        circadian_phase: str = "day",
        sensor_snapshot: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Execute the full pipeline and return unified proposals."""
        self._tick_count += 1
        pipeline_start = time.time()
        final_proposals: List[Dict[str, Any]] = []

        # 1. FSM Layer
        fsm_start = time.time()
        fsm_result = self.fsm.tick(
            homeostasis_metrics=None,
            energy=energy,
            cognitive_load=cognitive_load,
            prediction_error=prediction_error,
            circadian_phase=circadian_phase,
            health_score=health_score,
            curiosity_score=curiosity_score,
        )
        self._last_latencies_ms["fsm"] = (time.time() - fsm_start) * 1000.0
        organism_state = fsm_result["current_state"]

        # 2. Utility AI Layer
        util_start = time.time()
        self.drive_system.tick(
            curiosity_score=curiosity_score,
            novelty_score=0.0,
            prediction_error=prediction_error,
            coherence=0.0,
            noise_level=0.0,
            energy=energy,
            circadian_phase=circadian_phase,
        )
        module_weights = self.arbitration.tick(organism_state=organism_state)
        self._last_latencies_ms["utility"] = (time.time() - util_start) * 1000.0

        # Determine if we are in degraded mode (pipeline budget exceeded)
        elapsed_ms = (time.time() - pipeline_start) * 1000.0
        self._degraded_mode = elapsed_ms > self._max_pipeline_ms

        # 3. Behavior Tree Layer (skipped in degraded mode or if overloaded)
        bt_bag = ProposalBag("behavior_tree")
        if not self._degraded_mode and organism_state != "overloaded":
            bt_start = time.time()
            bt_context = self.bt.build_context(
                health_score=health_score,
                cognitive_load=cognitive_load,
                prediction_error=prediction_error,
                energy=energy,
                curiosity_score=curiosity_score,
                organism_state=organism_state,
                sensor_snapshot=sensor_snapshot,
            )
            bt_proposals = self.bt.tick(bt_context)
            for p in bt_proposals:
                bt_bag.add(p)
            self._last_latencies_ms["bt"] = (time.time() - bt_start) * 1000.0
        else:
            self._last_latencies_ms["bt"] = 0.0
            if self._degraded_mode and self._narrative_engine is not None:
                try:
                    self._narrative_engine.record(
                        event_type="pipeline_degraded_mode",
                        description="Pipeline exceeded budget; BT and GOAP skipped.",
                        importance=5,
                        metadata={"elapsed_ms": round(elapsed_ms, 2)},
                    )
                except Exception:
                    pass

        # 4. GOAP Layer — triggered if BT produced no actionable proposals
        goap_bag = ProposalBag("goap")
        if not self._degraded_mode and not bt_bag.proposals:
            goap_start = time.time()
            goap_context = {
                "world_state": {
                    "prediction_error": "high" if prediction_error > 0.5 else "low",
                    "sensor_data_fresh": False,
                    "memory_queried": False,
                    "clarification_needed": False,
                    "hypothesis_ready": True,
                    "metacognition_active": False,
                    "attention_focused": False,
                },
            }
            goap_proposals = self.goap.tick(goap_context)
            for p in goap_proposals:
                goap_bag.add(p)
            self._last_latencies_ms["goap"] = (time.time() - goap_start) * 1000.0
        else:
            self._last_latencies_ms["goap"] = 0.0

        # 5. Governance / Metacognition — merge bags, resolve conflicts
        # Higher layer wins if same proposal_type appears in both
        seen_types: set = set()
        for p in bt_bag.proposals:
            final_proposals.append(p)
            seen_types.add(p.get("proposal_type"))
        for p in goap_bag.proposals:
            if p.get("proposal_type") not in seen_types:
                final_proposals.append(p)

        # Tag all with tick info
        for p in final_proposals:
            p["tick"] = self._tick_count
            p["organism_state"] = organism_state
            # Attach dopaminergic / tension metadata if available
            if self._dopaminergic is not None:
                p["dopamine_level"] = round(self._dopaminergic.state.dopamine_level, 4)
            if self._predictive_tension is not None:
                p["predictive_tension"] = round(self._predictive_tension.get_drive_magnitude(), 4)

        self._last_proposals = final_proposals
        return final_proposals

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def snapshot(self) -> Dict[str, Any]:
        snap: Dict[str, Any] = {
            "tick_count": self._tick_count,
            "degraded_mode": self._degraded_mode,
            "last_latencies_ms": dict(self._last_latencies_ms),
            "last_proposal_count": len(self._last_proposals),
            "max_pipeline_ms": self._max_pipeline_ms,
            "layers": {
                "fsm": self.fsm.current_state(),
                "utility": self.arbitration.snapshot(),
                "bt": self.bt.snapshot(),
                "goap": self.goap.snapshot(),
            },
        }
        if self._dopaminergic is not None:
            snap["dopaminergic_state"] = self._dopaminergic.get_state().model_dump()
        if self._predictive_tension is not None:
            snap["predictive_tension_drive"] = round(self._predictive_tension.get_drive_magnitude(), 4)
        return snap
