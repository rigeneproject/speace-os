"""Watchdog della salute dei servizi e delle metriche vitali dell'organismo."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from os_coordinator.service_registry import ServiceRegistry, ServiceState


@dataclass
class HealthReport:
    """Rappresenta lo stato di salute corrente del sistema."""

    healthy: bool
    failed_services: list[str]
    stale_services: list[str]          # servizi RUNNING ma senza heartbeat recente
    vital_metrics: dict
    notes: list[str] = None           # type: ignore[assignment]

    def to_dict(self) -> dict:
        return {
            "healthy": self.healthy,
            "failed_services": self.failed_services,
            "stale_services": self.stale_services,
            "vital_metrics": self.vital_metrics,
            "notes": self.notes or [],
        }


def check_health(
    registry: ServiceRegistry,
    vital_metrics: Optional[dict] = None,
    heartbeat_stale_sec: float = 60.0,
) -> HealthReport:
    """Controlla lo stato dei servizi e le metriche vitali.

    Restituisce un report strutturato che il coordinatore usa per
    decidere se chiedere un intervento all'agentic AI.
    """
    notes: list[str] = []
    failed: list[str] = []
    stale: list[str] = []

    now = time.time()
    for rec in registry.all():
        if rec.state == ServiceState.FAILED:
            failed.append(rec.name)
            notes.append(f"servizio FAILED: {rec.name} ({rec.last_error or 'no error'})")
        elif rec.state == ServiceState.RUNNING:
            if rec.last_heartbeat > 0 and (now - rec.last_heartbeat) > heartbeat_stale_sec:
                stale.append(rec.name)
                notes.append(f"heartbeat stantio: {rec.name} ({(now - rec.last_heartbeat):.0f}s)")

    # Metriche vitali: solo advisory, non bloccanti.
    degraded = False
    if vital_metrics:
        phi = vital_metrics.get("coherence_phi")
        if phi is not None and phi < 0.05:
            degraded = True
            notes.append(f"coherence_phi critico: {phi:.4f}")
        ilf = vital_metrics.get("ilf")
        if ilf is not None and ilf < 0.1:
            degraded = True
            notes.append(f"ILF molto basso: {ilf:.4f}")

    return HealthReport(
        healthy=not failed and not degraded,
        failed_services=failed,
        stale_services=stale,
        vital_metrics=vital_metrics or {},
        notes=notes,
    )
