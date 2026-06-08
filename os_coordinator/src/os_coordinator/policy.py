"""Policy di decisione: traduce i comandi dell'AI in azioni eseguibili.

Layer di indirezione tra le decisioni JSON dell'agentic AI e le azioni
sul sistema. Filtra operazioni non sicure, logga, e garantisce che
l'AI non possa fare danni (es. kill del PID 1, riavvii continui).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from os_coordinator.agentic_brain import AgenticDecision
from os_coordinator.service_registry import ServiceRegistry, ServiceState

logger = logging.getLogger("os_coordinator.policy")


# Operazioni permesse per servizio (whitelist esplicita).
ALLOWED_OPS: dict[str, set[str]] = {
    "speace-brain":      {"start", "stop", "restart", "status"},
    "speace-evolution":  {"start", "stop", "restart", "status"},
    "speace-agi-team":   {"start", "stop", "restart", "status"},
    "speace-dashboard":  {"start", "stop", "restart", "status"},
}

# Rate-limit: massimo N restart per servizio in M secondi.
MAX_RESTARTS = 3
RESTART_WINDOW_SEC = 300.0


@dataclass
class PlannedAction:
    service: str
    op: str
    accepted: bool
    reason: str = ""


def plan_actions(
    decision: AgenticDecision,
    registry: ServiceRegistry,
) -> list[PlannedAction]:
    """Traduce le azioni della decisione AI in PlannedAction accettate/rifiutate."""
    out: list[PlannedAction] = []
    now = time.time()

    for action in decision.actions:
        service = action.get("service", "")
        op = action.get("op", "")
        if service not in ALLOWED_OPS:
            out.append(PlannedAction(
                service=service, op=op, accepted=False,
                reason=f"servizio sconosciuto: {service}",
            ))
            continue
        if op not in ALLOWED_OPS[service]:
            out.append(PlannedAction(
                service=service, op=op, accepted=False,
                reason=f"op non permessa: {op}",
            ))
            continue

        rec = registry.get(service)
        # Rate limit sui restart.
        if op == "restart" and rec is not None:
            if rec.restarts >= MAX_RESTARTS and (now - rec.last_change) < RESTART_WINDOW_SEC:
                out.append(PlannedAction(
                    service=service, op=op, accepted=False,
                    reason=f"rate limit: {rec.restarts} restart in finestra",
                ))
                continue

        out.append(PlannedAction(service=service, op=op, accepted=True))
        logger.info("policy: accettata %s/%s (urgency=%s)", service, op, decision.urgency)

    return out
