"""MicroActuatorController — Phase 3: limited physical embodiment.

Provides sandboxed micro-actuation:
- speaker_beep    : audible beep via winsound (Windows-safe)
- tts_announce    : text-to-speech via SpeechOutputOrgan
- notification    : Windows desktop toast notification
- light_pulse     : toggle keyboard LED as light proxy
- cursor_nudge    : micro mouse movement (gated, max 10 px)

Every action is:
1. Proposed
2. screened by governance (risk classifier + policy engine)
3. blocked by default if dangerous
4. audited to JSONL
5. reversible where possible (light_pulse restores LED state)
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.memory.morphology_events import (
    MorphologyEvent,
    MorphologyEventType,
)

try:
    from speace_core.cellular_brain.action_governance.action_governance_models import (
        ActionGovernanceDecision,
        ExternalActionProposal,
        ExternalActionType,
    )
    from speace_core.cellular_brain.action_governance.action_policy_engine import (
        ActionPolicyEngine,
    )
    from speace_core.cellular_brain.action_governance.action_risk_classifier import (
        ActionRiskClassifier,
    )
    from speace_core.cellular_brain.action_governance.reversibility_analyzer import (
        ReversibilityAnalyzer,
    )

    _GOVERNANCE_AVAILABLE = True
except ImportError:  # pragma: no cover
    _GOVERNANCE_AVAILABLE = False


class MicroActuatorController:
    """Sandboxed micro-actuator for speaker, notifications, lights, cursor."""

    # Actions that always require human_review regardless of governance
    DANGEROUS_ACTIONS = {"cursor_nudge"}

    # Safety limits
    MAX_BEEP_FREQ = 2000
    MIN_BEEP_FREQ = 100
    MAX_CURSOR_NUDGE = 10
    MAX_NOTIFICATIONS_PER_MINUTE = 5

    def __init__(
        self,
        data_root: str = "data/embodiment/micro_actuator",
        speech_organ: Optional[Any] = None,
    ) -> None:
        self._data_root = Path(data_root)
        self._data_root.mkdir(parents=True, exist_ok=True)
        self._audit_path = self._data_root / "micro_actuator_audit.jsonl"
        self._speech_organ = speech_organ

        self._queue: List[Dict[str, Any]] = []
        self._history: List[Dict[str, Any]] = []
        self._proposals: Dict[str, Dict[str, Any]] = {}

        # Rate-limiting state
        self._notification_times: List[float] = []

        # Light state for reversibility
        self._numlock_before: Optional[bool] = None
        self._capslock_before: Optional[bool] = None

        if _GOVERNANCE_AVAILABLE:
            self._risk_classifier = ActionRiskClassifier()
            self._reversibility_analyzer = ReversibilityAnalyzer()
            self._policy_engine = ActionPolicyEngine()
        else:
            self._risk_classifier = None
            self._reversibility_analyzer = None
            self._policy_engine = None

    # ------------------------------------------------------------------ #
    # Governance helpers
    # ------------------------------------------------------------------ #

    def _build_external_proposal(
        self,
        proposal_id: str,
        action_type: str,
        params: Dict[str, Any],
    ) -> ExternalActionProposal:
        if action_type in ("speaker_beep", "tts_announce"):
            ext_type = ExternalActionType.OBSERVE_ONLY
            estimated_risk = 0.05
        elif action_type == "notification":
            ext_type = ExternalActionType.OBSERVE_ONLY
            estimated_risk = 0.1
        elif action_type == "light_pulse":
            ext_type = ExternalActionType.RECONFIGURE_SIMULATED
            estimated_risk = 0.15
        elif action_type == "cursor_nudge":
            ext_type = ExternalActionType.RESOURCE_SHIFT_SIMULATED
            estimated_risk = 0.4
        else:
            ext_type = ExternalActionType.UNKNOWN
            estimated_risk = 0.5

        return ExternalActionProposal(
            proposal_id=proposal_id,
            action_type=ext_type,
            title=f"Micro actuation: {action_type}",
            description=f"Limited physical actuation {action_type}",
            simulated_only=False,
            requested_real_execution=True,
            estimated_risk=estimated_risk,
            estimated_urgency=0.2,
            estimated_benefit=0.2,
            uncertainty_score=0.1,
            metadata={"micro_action_type": action_type, "params": params},
        )

    def _log(
        self,
        event_type: MorphologyEventType,
        action_id: str,
        metadata: Dict[str, Any],
    ) -> None:
        record = {
            "timestamp": time.time(),
            "event_type": str(event_type),
            "action_id": action_id,
            "metadata": metadata,
        }
        try:
            with self._audit_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            pass

    # ------------------------------------------------------------------ #
    # Proposal / approval / execute
    # ------------------------------------------------------------------ #

    def propose_action(self, action_type: str, params: Dict[str, Any]) -> str:
        proposal_id = f"micro_{uuid.uuid4().hex[:8]}"
        proposal: Dict[str, Any] = {
            "proposal_id": proposal_id,
            "action_type": action_type,
            "params": params,
            "status": "proposed",
            "governance_decision": None,
        }

        if _GOVERNANCE_AVAILABLE and self._policy_engine is not None:
            ext = self._build_external_proposal(proposal_id, action_type, params)
            risk = self._risk_classifier.classify_action_risk(ext)
            rev = self._reversibility_analyzer.assess_reversibility(ext)
            decision = self._policy_engine.evaluate_action_proposal(ext, risk, rev)
            proposal["governance_decision"] = decision.model_dump()

            if decision.blocked:
                proposal["status"] = "blocked"
                self._log(
                    MorphologyEventType.ACTION_BLOCKED,
                    proposal_id,
                    {"reason": decision.blocked_reason, "action_type": action_type},
                )
                self._history.append(
                    {
                        "proposal_id": proposal_id,
                        "action_type": action_type,
                        "params": params,
                        "timestamp": time.time(),
                        "outcome": "blocked",
                        "error": decision.blocked_reason,
                    }
                )
                self._proposals[proposal_id] = proposal
                return proposal_id

        self._queue.append(proposal)
        self._proposals[proposal_id] = proposal
        return proposal_id

    def approve_action(self, proposal_id: str) -> Dict[str, Any]:
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return {"success": False, "error": "proposal_not_found"}
        if proposal["status"] == "blocked":
            return {"success": False, "error": "proposal_blocked_by_governance"}
        if proposal["status"] != "proposed":
            return {"success": False, "error": "proposal_already_processed"}

        self._queue = [p for p in self._queue if p["proposal_id"] != proposal_id]
        return self.execute_action(
            proposal["action_type"],
            proposal["params"],
            proposal_id=proposal_id,
        )

    def execute_action(
        self,
        action_type: str,
        params: Dict[str, Any],
        proposal_id: Optional[str] = None,
        approval_level: str = "automatic",
    ) -> Dict[str, Any]:
        action_id = proposal_id or f"micro_act_{uuid.uuid4().hex[:8]}"

        # Dangerous-action gate
        if action_type in self.DANGEROUS_ACTIONS and approval_level != "human_review":
            self._log(
                MorphologyEventType.ACTION_BLOCKED,
                action_id,
                {"reason": "dangerous_action_requires_human_review", "action_type": action_type},
            )
            record = {
                "proposal_id": proposal_id,
                "action_type": action_type,
                "params": params,
                "timestamp": time.time(),
                "outcome": "blocked",
                "error": "dangerous_action_requires_human_review",
            }
            self._history.append(record)
            if proposal_id and proposal_id in self._proposals:
                self._proposals[proposal_id]["status"] = "blocked"
            return {"success": False, "error": "dangerous_action_requires_human_review", "action_id": action_id}

        try:
            result = self._perform_action(action_type, params)
            outcome = "success"
            error = None
            self._log(
                MorphologyEventType.ACTION_EXECUTED,
                action_id,
                {"action_type": action_type, "result": result},
            )
        except Exception as exc:
            result = None
            outcome = "failure"
            error = str(exc)
            self._log(
                MorphologyEventType.ACTION_BLOCKED,
                action_id,
                {"action_type": action_type, "error": error},
            )

        record = {
            "proposal_id": proposal_id,
            "action_type": action_type,
            "params": params,
            "timestamp": time.time(),
            "outcome": outcome,
            "error": error,
            "result": result,
        }
        self._history.append(record)
        if proposal_id and proposal_id in self._proposals:
            self._proposals[proposal_id]["status"] = "completed"
        return {"success": outcome == "success", "result": result, "error": error, "action_id": action_id}

    # ------------------------------------------------------------------ #
    # Action primitives
    # ------------------------------------------------------------------ #

    def _perform_action(self, action_type: str, params: Dict[str, Any]) -> Any:
        if action_type == "speaker_beep":
            return self._act_speaker_beep(params)
        if action_type == "tts_announce":
            return self._act_tts_announce(params)
        if action_type == "notification":
            return self._act_notification(params)
        if action_type == "light_pulse":
            return self._act_light_pulse(params)
        if action_type == "cursor_nudge":
            return self._act_cursor_nudge(params)
        raise ValueError(f"unknown_micro_action_type: {action_type}")

    def _act_speaker_beep(self, params: Dict[str, Any]) -> Dict[str, Any]:
        freq = int(params.get("frequency", 440))
        duration = int(params.get("duration_ms", 200))
        freq = max(self.MIN_BEEP_FREQ, min(self.MAX_BEEP_FREQ, freq))
        duration = max(50, min(1000, duration))

        try:
            import winsound
            winsound.Beep(freq, duration)
        except Exception as exc:
            # Fallback: log only if winsound unavailable
            return {"mode": "beep", "frequency": freq, "duration_ms": duration, "error": str(exc)}
        return {"mode": "beep", "frequency": freq, "duration_ms": duration}

    def _act_tts_announce(self, params: Dict[str, Any]) -> Dict[str, Any]:
        text = params.get("text", "")
        if not text:
            return {"mode": "tts", "error": "empty_text"}
        if self._speech_organ is not None:
            record = self._speech_organ.speak(text, source="micro_actuator")
            return {"mode": "tts", "record": record}
        # Fallback: print
        print(f"[SPEACE TTS] {text}")
        return {"mode": "tts", "text": text, "fallback": "printed"}

    def _act_notification(self, params: Dict[str, Any]) -> Dict[str, Any]:
        title = params.get("title", "SPEACE")
        message = params.get("message", "")
        if not message:
            return {"mode": "notification", "error": "empty_message"}

        # Rate limiting
        now = time.time()
        self._notification_times = [t for t in self._notification_times if now - t < 60]
        if len(self._notification_times) >= self.MAX_NOTIFICATIONS_PER_MINUTE:
            return {"mode": "notification", "error": "rate_limited", "title": title, "message": message}
        self._notification_times.append(now)

        try:
            # Try win10toast (non-blocking desktop toast) if available
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(title, message, duration=3, threaded=True)
        except Exception:
            # Fallback: print to console (non-blocking, safe everywhere)
            print(f"[SPEACE notification] {title}: {message}")
        return {"mode": "notification", "title": title, "message": message}

    def _act_light_pulse(self, params: Dict[str, Any]) -> Dict[str, Any]:
        led = params.get("led", "numlock")
        duration = float(params.get("duration_s", 0.5))
        if led not in ("numlock", "capslock"):
            raise ValueError("invalid_led_choice")

        try:
            import ctypes
            VK_NUMLOCK = 0x90
            VK_CAPITAL = 0x14
            key = VK_NUMLOCK if led == "numlock" else VK_CAPITAL
            user32 = ctypes.windll.user32

            # Read current state
            before = bool(user32.GetKeyState(key) & 0x0001)
            if led == "numlock":
                self._numlock_before = before
            else:
                self._capslock_before = before

            # Toggle
            user32.keybd_event(key, 0x45, 0x0001, 0)
            user32.keybd_event(key, 0x45, 0x0001 | 0x0002, 0)

            # Schedule restore
            def _restore() -> None:
                import time
                time.sleep(duration)
                after = bool(user32.GetKeyState(key) & 0x0001)
                if after != before:
                    user32.keybd_event(key, 0x45, 0x0001, 0)
                    user32.keybd_event(key, 0x45, 0x0001 | 0x0002, 0)

            import threading
            threading.Thread(target=_restore, daemon=True).start()
        except Exception as exc:
            return {"mode": "light_pulse", "led": led, "duration_s": duration, "error": str(exc)}
        return {"mode": "light_pulse", "led": led, "duration_s": duration, "restored_after": duration}

    def _act_cursor_nudge(self, params: Dict[str, Any]) -> Dict[str, Any]:
        dx = int(params.get("dx", 0))
        dy = int(params.get("dy", 0))
        if abs(dx) > self.MAX_CURSOR_NUDGE or abs(dy) > self.MAX_CURSOR_NUDGE:
            raise ValueError("cursor_nudge_exceeds_safety_limit")
        try:
            import ctypes
            user32 = ctypes.windll.user32
            # Get current position
            pt = ctypes.wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            new_x = pt.x + dx
            new_y = pt.y + dy
            user32.SetCursorPos(new_x, new_y)
        except Exception as exc:
            return {"mode": "cursor_nudge", "dx": dx, "dy": dy, "error": str(exc)}
        return {"mode": "cursor_nudge", "dx": dx, "dy": dy}

    # ------------------------------------------------------------------ #
    # History
    # ------------------------------------------------------------------ #

    def get_action_history(self) -> List[Dict[str, Any]]:
        return list(self._history)

    def get_proposal_status(self, proposal_id: str) -> str:
        """Return the status of a proposal by ID."""
        return self._proposals.get(proposal_id, {}).get("status", "unknown")

    def summary(self) -> Dict[str, Any]:
        total = len(self._history)
        successes = sum(1 for h in self._history if h.get("outcome") == "success")
        blocked = sum(1 for h in self._history if h.get("outcome") == "blocked")
        failures = total - successes - blocked
        by_type: Dict[str, int] = {}
        for h in self._history:
            t = h.get("action_type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1
        return {
            "total_actions": total,
            "successes": successes,
            "blocked": blocked,
            "failures": failures,
            "by_type": by_type,
            "rate_limit_window": len(self._notification_times),
        }
