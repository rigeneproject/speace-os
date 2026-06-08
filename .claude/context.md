---
name: speace-os-cognitive-distro
description: SPEACE OS — distro Linux con PID 1 cognitivo (os_coordinator) guidato da minimax-m3:cloud, basata su cellular_speace
metadata:
  type: project
---

SPEACE OS 0.1.0-cos è una distro Linux costruita su Alpine 3.20 con:

- `os_coordinator/` come PID 1 cognitivo: state machine a 6 fasi (BOOT → IGNITION → COGNITION → IDLE → INTERVENTION ↔ IDLE → SHUTDOWN)
- agentic AI = `minimax-m3:cloud` via Ollama Cloud (API key già in `rootfs/etc/speace/env.conf`)
- `cellular_speace/` snapshot in `rootfs/opt/speace/cellular_speace/` (1.109 file, 11 MB)
- 4 servizi canonici: speace-brain, speace-evolution, speace-agi-team, speace-dashboard
- supervisore s6-like in Python (`rootfs/lib/speace/supervisor.py`)
- pipeline CI GitHub Actions: build-distro.yml (ISO + QCOW2 + rootfs), test-os-coordinator.yml, publish-release.yml
- 25/25 test passano sul coordinatore; 69% coverage; CLI `--status` funziona

**Why:** Trasforma cellular_speace (libreria Python) in un sistema operativo con kernel proprio, initramfs, e ciclo di vita gestito da un agentic AI.

**How to apply:** Quando si lavora su SPEACE OS:
- Qualsiasi modifica a `os_coordinator/` richiede test in `os_coordinator/tests/`
- Aggiungere un servizio canonico = modificare 3 file: `service_registry.py` (CANONICAL_SERVICES), `policy.py` (ALLOWED_OPS), `coordinator.yaml` (sezione services)
- Il modulo è `os_coordinator`, non confondere con `cellular_speace/speace_agi_team/` (esistente) — os_coordinator è di livello superiore (sistema operativo)
- L'API key Ollama è già in `env.conf`; per produzione spostarla in variabile ambiente
- La documentazione completa è in `docs/`: ARCHITECTURE, BOOT-SEQUENCE, COORDINATOR, SERVICE-MANAGEMENT, BUILD, SECURITY-MODEL
