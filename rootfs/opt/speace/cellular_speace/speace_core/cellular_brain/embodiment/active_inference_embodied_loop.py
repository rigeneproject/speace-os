"""T-AIEL — Active Inference Embodied Loop.

Tightens the loop between :class:`ActiveInferenceEngine` and
:class:`EmbodiedActionActuator` so that:

1. Real prediction errors from the physical environment update the
   active inference beliefs.
2. The action selected by active inference is mapped to a concrete
   actuator proposal (not just an internal ``signal_type``).
3. Every step is recorded in :class:`EmbodiedActionAuditTrail` so the
   learned causal model is verifiable.
4. The action outcome is fed back into the predictive coding engine
   as a teaching signal for the next iteration.

This module does *not* bypass the action governance policy. All
proposals still flow through ``EmbodiedActionActuator.propose_action``,
which is sandboxed and audited by construction.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_logger = logging.getLogger(__name__)


@dataclass
class EmbodiedStepResult:
    """Outcome of one closed-loop step."""

    tick: int
    pre_state: Dict[str, float] = field(default_factory=dict)
    prediction: Optional[Dict[str, float]] = None
    action: Optional[str] = None
    post_state: Dict[str, float] = field(default_factory=dict)
    proposal_id: Optional[str] = None
    proposal_status: Optional[str] = None
    prediction_error: float = 0.0
    surprise: float = 0.0
    belief_after: Dict[str, float] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tick": self.tick,
            "pre_state": dict(self.pre_state),
            "prediction": dict(self.prediction) if self.prediction is not None else None,
            "action": self.action,
            "post_state": dict(self.post_state),
            "proposal_id": self.proposal_id,
            "proposal_status": self.proposal_status,
            "prediction_error": float(self.prediction_error),
            "surprise": float(self.surprise),
            "belief_after": dict(self.belief_after),
            "notes": list(self.notes),
        }


class ActiveInferenceEmbodiedLoop:
    """Closed loop between active inference, environment and actuator."""

    # Default mapping from a high-level action name (the result of
    # :class:`ActiveInferenceEngine.step()`) to a concrete actuator
    # ``action_type``. Keep this list small and well-audited.
    DEFAULT_ACTION_MAP: Dict[str, Dict[str, Any]] = {
        "observe": {
            "action_type": "log_event",
            "params": {"category": "active_inference_observe"},
        },
        "actuate": {
            "action_type": "send_signal_to_self",
            "params": {"signal_type": "request_change"},
        },
        "request_sleep": {
            "action_type": "send_signal_to_self",
            "params": {"signal_type": "request_sleep"},
        },
        "request_resume": {
            "action_type": "send_signal_to_self",
            "params": {"signal_type": "request_resume"},
        },
        "checkpoint": {
            "action_type": "create_checkpoint",
            "params": {"scope": "active_inference"},
        },
        "garbage_collect": {
            "action_type": "log_event",
            "params": {"category": "garbage_collect"},
        },
    }

    def __init__(
        self,
        active_inference: Any,
        embodied_actuator: Any,
        audit_trail: Any,
        predictive_coding: Any = None,
        action_map: Optional[Dict[str, Dict[str, Any]]] = None,
        world_model: Any = None,
    ):
        self.active_inference = active_inference
        self.embodied_actuator = embodied_actuator
        self.audit_trail = audit_trail
        self.predictive_coding = predictive_coding
        self.action_map: Dict[str, Dict[str, Any]] = dict(
            action_map or self.DEFAULT_ACTION_MAP
        )
        self.world_model = world_model
        self._tick: int = 0
        self._last_result: Optional[EmbodiedStepResult] = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def register_action(self, name: str, action_type: str, params: Dict[str, Any]) -> None:
        """Register a new high-level action → actuator mapping."""
        self.action_map[name] = {"action_type": action_type, "params": dict(params)}

    def step(
        self,
        pre_state: Dict[str, float],
        post_state: Dict[str, float],
        surprise: float = 0.0,
        note: str = "",
    ) -> EmbodiedStepResult:
        """Run one closed-loop step.

        ``pre_state`` is the (flattened) sensor reading *before* the
        action. ``post_state`` is the reading *after* the actuator
        proposal was emitted. ``surprise`` is the Bayesian surprise
        (e.g. KL between predicted and observed) used to update the
        active inference beliefs.
        """
        self._tick += 1
        result = EmbodiedStepResult(tick=self._tick, pre_state=dict(pre_state), post_state=dict(post_state))

        # 1) Predict next state (best effort) from the world model.
        prediction: Optional[Dict[str, float]] = None
        if self.world_model is not None and hasattr(self.world_model, "predict_next_state"):
            try:
                predicted = self.world_model.predict_next_state()
                if isinstance(predicted, dict):
                    prediction = {k: float(v) for k, v in predicted.items()}
            except Exception as exc:  # pragma: no cover
                result.notes.append(f"predict_failed:{exc}")
        result.prediction = prediction

        # 2) Compute prediction error vs reality.
        if prediction is not None:
            err = sum(
                abs(float(post_state.get(k, 0.0)) - float(prediction.get(k, 0.0)))
                for k in set(post_state) | set(prediction)
            )
            result.prediction_error = float(err)
        result.surprise = float(surprise)

        # 3) Bayesian update of active inference beliefs.
        if (
            self.active_inference is not None
            and self.active_inference.beliefs
            and surprise > 0.0
        ):
            # Use the surprise as a soft likelihood: the state with
            # the highest prior absorbs it.
            try:
                top_state = max(
                    self.active_inference.beliefs,
                    key=self.active_inference.beliefs.get,
                )
                self.active_inference.observe(top_state, 1.0 + float(surprise))
                result.belief_after = dict(self.active_inference.beliefs)
            except Exception as exc:  # pragma: no cover
                result.notes.append(f"ai_observe_failed:{exc}")
        elif self.active_inference is not None and self.active_inference.beliefs:
            result.belief_after = dict(self.active_inference.beliefs)

        # 4) Select action and translate to actuator proposal.
        selected: Optional[str] = None
        if self.active_inference is not None:
            try:
                selected = self.active_inference.step()
            except Exception as exc:  # pragma: no cover
                result.notes.append(f"ai_step_failed:{exc}")
                selected = None
        result.action = selected

        proposal_id: Optional[str] = None
        proposal_status: Optional[str] = None
        if selected is not None and selected in self.action_map and self.embodied_actuator is not None:
            spec = self.action_map[selected]
            try:
                proposal_id = self.embodied_actuator.propose_action(
                    spec["action_type"], spec.get("params", {})
                )
                # Look up status from the actuator's internal state.
                proposals = getattr(self.embodied_actuator, "_proposals", {})
                proposal = proposals.get(proposal_id, {})
                proposal_status = proposal.get("status")
                result.notes.append(
                    f"proposal_status:{proposal_status}"
                )
            except Exception as exc:  # pragma: no cover
                result.notes.append(f"propose_failed:{exc}")
        result.proposal_id = proposal_id
        result.proposal_status = proposal_status

        # 5) Feed prediction error into the predictive coding engine
        #    as a sensory-layer teaching signal.
        if (
            self.predictive_coding is not None
            and result.prediction_error > 0.0
            and "sensory" in getattr(self.predictive_coding, "layers", {})
        ):
            try:
                import numpy as np

                dim = self.predictive_coding.layers["sensory"]["dim"]
                arr = np.full(dim, min(1.0, result.prediction_error), dtype=float)
                self.predictive_coding.update("sensory", arr)
            except Exception as exc:  # pragma: no cover
                result.notes.append(f"pc_update_failed:{exc}")

        # 6) Audit.
        if self.audit_trail is not None:
            try:
                self.audit_trail.record(
                    tick=self._tick,
                    pre_state=pre_state,
                    post_state=post_state,
                    action=selected,
                    prediction=prediction,
                    surprise=result.surprise,
                    belief_after=result.belief_after,
                    note=note or ";".join(result.notes),
                )
            except Exception as exc:  # pragma: no cover
                _logger.debug("Audit trail record failed: %s", exc)

        self._last_result = result
        return result

    @property
    def last_result(self) -> Optional[EmbodiedStepResult]:
        return self._last_result
