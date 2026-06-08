"""Fasi del ciclo di vita del sistema operativo cognitivo.

Una macchina a stati semplice ma rigorosa: ogni fase ha esattamente una
responsabilità, e le transizioni sono deterministiche tranne dove
l'agentic AI può scegliere (tipicamente IDLE → INTERVENTION).
"""

from __future__ import annotations

from enum import Enum


class Phase(str, Enum):
    """Ciclo di vita del sistema operativo SPEACE OS."""

    BOOT = "BOOT"
    # ^ Kernel in esecuzione, initramfs caricato, rootfs non ancora montato.
    #   Compiti: leggere /etc/os-release, configurare early-stage, montare proc/sys/dev.

    IGNITION = "IGNITION"
    # ^ Rootfs montato, supervisore servizi attivo, env caricato da /etc/speace/env.conf.
    #   Compiti: validare l'installazione di cellular_speace, caricare coordinator.yaml.

    COGNITION = "COGNITION"
    # ^ L'agente AI è sveglio e produce il piano di avvio dei servizi cognitivi.
    #   Compiti: chiedere all'AI come strutturare l'avvio, eseguire il piano.

    IDLE = "IDLE"
    # ^ Sistema in funzione, ciclo di supervisione attivo.
    #   Compiti: heartbeat, watchdog, consultare l'AI solo se le metriche degradano.

    INTERVENTION = "INTERVENTION"
    # ^ L'AI ha rilevato un'anomalia e ha chiesto un'azione correttiva.
    #   Compiti: eseguire le azioni richieste, tornare in IDLE.

    SHUTDOWN = "SHUTDOWN"
    # ^ Spegnimento ordinato: evolution, agi_team, brain, supervisore.
    #   Compiti: salvare snapshot, pivot_root inverso, poweroff/reboot.


# Transizioni permesse (fase di partenza → set di fasi di arrivo valide).
ALLOWED_TRANSITIONS: dict[Phase, set[Phase]] = {
    Phase.BOOT: {Phase.IGNITION, Phase.SHUTDOWN},
    Phase.IGNITION: {Phase.COGNITION, Phase.SHUTDOWN},
    Phase.COGNITION: {Phase.IDLE, Phase.INTERVENTION, Phase.SHUTDOWN},
    Phase.IDLE: {Phase.INTERVENTION, Phase.SHUTDOWN},
    Phase.INTERVENTION: {Phase.IDLE, Phase.SHUTDOWN},
    Phase.SHUTDOWN: set(),  # stato terminale
}


def can_transition(src: Phase, dst: Phase) -> bool:
    """Restituisce True se la transizione src → dst è permessa."""
    return dst in ALLOWED_TRANSITIONS.get(src, set())
