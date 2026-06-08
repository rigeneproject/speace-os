# SPEACE OS — Cognitive Operating System

> Un sistema operativo Linux il cui PID 1 è un agente cognitivo che orchestra
> l'avvio, la supervisione e lo spegnimento dei servizi cognitivi di
> **SPEACE** (Super Entità Autonoma Cibernetica Cellulare Evolutiva).

[![Tests](https://img.shields.io/badge/tests-25%20passing-brightgreen)](os_coordinator/tests/)
[![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue)](os_coordinator/pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

## Cos'è

SPEACE OS è una distro Linux basata su **Alpine 3.20** che:

- Porta tutto il codice `cellular_speace/` in `/opt/speace/cellular_speace/`
- Aggiunge un nuovo modulo `os_coordinator/` che funziona da **PID 1 cognitivo**
- Usa `minimax-m3:cloud` (via Ollama Cloud) come decisore di alto livello
- Espone un supervisore di servizi s6-like in Python (`/lib/speace/supervisor.py`)
- Produce ISO avviabile, QCOW2 per KVM, e rootfs standalone tramite GitHub Actions

## Quick start (in QEMU)

```bash
# 1) Scarica l'ultima release da GitHub
wget https://github.com/rigeneproject/speace-os/releases/latest/download/speace-os-0.1.0-cos.iso

# 2) Avvia in QEMU
qemu-system-x86_64 -m 3G -smp 2 -cdrom speace-os-0.1.0-cos.iso

# 3) Dopo il login, prova:
speace-os-status          # stato del coordinatore cognitivo
speace chat               # parla con l'organismo
speace monitor            # dashboard web (http://127.0.0.1:8787)
```

## Quick start (in CI: build da sorgente)

```bash
git clone https://github.com/rigeneproject/speace-os.git
cd speace-os/SPEACE_OS_Cognitive_Operating_System
sudo ./iso/build.sh
# → out/speace-os-0.1.0-cos.iso
```

## Architettura

```
┌─────────────────────────────────────────────────────────┐
│              BIOS/UEFI → GRUB → KERNEL                  │
│         + initramfs (init → os_coordinator come PID 1)  │
└──────────────────────┬──────────────────────────────────┘
                       │ pivot_root
                       ▼
┌─────────────────────────────────────────────────────────┐
│  ROOTFS (Alpine 3.20)                                   │
│  ┌───────────────────────────────────────────────────┐  │
│  │ /sbin/os_coordinator (PID 1)                     │  │
│  │  ├─ phase: BOOT → IGNITION → COGNITION → IDLE   │  │
│  │  ├─ invoca agentic AI (minimax-m3:cloud)         │  │
│  │  ├─ gestisce servizi (s6-like supervisor)        │  │
│  │  └─ spegnimento cognitivo ordinato               │  │
│  └───────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────┐  │
│  │ /opt/speace/cellular_speace/                     │  │
│  │  ├─ speace_core/      (cervello cellulare)        │  │
│  │  ├─ evolution_daemon/ (auto-miglioramento)        │  │
│  │  └─ speace_agi_team/  (team agentico)             │  │
│  └───────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────┐  │
│  │ /etc/speace/services/                            │  │
│  │  ├─ speace-brain/        (speace_core)            │  │
│  │  ├─ speace-evolution/    (evolution_daemon)       │  │
│  │  ├─ speace-agi-team/     (speace_agi_team)        │  │
│  │  └─ speace-dashboard/    (FastAPI monitor)        │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Componenti

| Componente | Dove | Ruolo |
|---|---|---|
| `os_coordinator` | `os_coordinator/` | PID 1 cognitivo: ciclo di vita OS + decisioni AI |
| `supervisor.py` | `rootfs/lib/speace/supervisor.py` | Service manager s6-like, watchdog, restart |
| Servizi | `rootfs/etc/speace/services/<name>/run` | 4 servizi canonici (brain, evolution, agi-team, dashboard) |
| Initramfs | `initramfs/init` | Bootstrap minimo: monta rootfs, lancia `os_coordinator` |
| Build pipeline | `iso/build.sh` + 4 script | Kernel + rootfs + initramfs + ISO + QCOW2 |
| CI | `.github/workflows/*.yml` | 3 workflow: build-distro, test, publish-release |

## Documentazione

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — design dettagliato
- [docs/BOOT-SEQUENCE.md](docs/BOOT-SEQUENCE.md) — dal BIOS al cervello
- [docs/COORDINATOR.md](docs/COORDINATOR.md) — contratto del coordinatore
- [docs/SERVICE-MANAGEMENT.md](docs/SERVICE-MANAGEMENT.md) — come funziona il supervisore
- [docs/BUILD.md](docs/BUILD.md) — come buildare in locale
- [docs/SECURITY-MODEL.md](docs/SECURITY-MODEL.md) — guardrail e DNA Stage

## Test

```bash
# Test del coordinatore (25 unit test, eseguiti in CI su Python 3.12 e 3.13)
cd os_coordinator
pip install -e ".[dev]"
pytest tests/ -v
```

## Contribuire

Le contribuzioni sono benvenute! Aree chiave:
- Estendere la policy (`os_coordinator/policy.py`) con nuove azioni
- Aggiungere un nuovo servizio canonico in `service_registry.py` + un nuovo `run`
- Migliorare il guardrail del `supervisor.py`
- Ottimizzare la ISO (più compressione, meno servizi opzionali)

Vedi [CHANGELOG.md](CHANGELOG.md) per la roadmap.

## Licenza

MIT — vedi [LICENSE](LICENSE).

## Acknowledgements

SPEACE OS è costruito su:
- [cellular_speace](../cellular_speace) — il cervello cellulare di SPEACE
- [Ollama Cloud](https://ollama.com) — backend LLM (`minimax-m3:cloud`)
- Alpine Linux — rootfs di base
- Linux 6.6 LTS — kernel
