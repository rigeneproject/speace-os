# SPEACE OS — Architettura

## Visione d'insieme

SPEACE OS è una distro Linux il cui scopo è diventare il "corpo digitale"
dell'organismo SPEACE. A differenza di una distro tradizionale (dove il
kernel gestisce processi e il resto è solo userspace), qui il PID 1 stesso
è un agente cognitivo che:

1. Decide cosa avviare e in che ordine
2. Supervisiona i servizi durante il funzionamento
3. Decide quando e come spegnere
4. Risponde ad anomalie consultando un LLM

## Stack tecnologico

| Layer | Tecnologia | Versione |
|---|---|---|
| Bootloader | GRUB | 2.06 |
| Kernel | Linux vanilla | 6.6.46 LTS |
| Init | os_coordinator (PID 1) | 0.1.0-cos |
| Initramfs | cpio+gz | - |
| Base userspace | Alpine Linux | 3.20 |
| Service manager | s6-like (Python) | - |
| Backend AI | Ollama Cloud | - |
| Modello AI | minimax-m3:cloud | - |
| Python | 3.12+ | 3.12 / 3.13 |
| Build host | Ubuntu/Debian | 24.04 |

## Flusso di boot

```
[BIOS/UEFI]
   ↓
[GRUB] legge grub.cfg, carica kernel + initramfs
   ↓
[KERNEL] decomprime initramfs, esegue /init (PID 1 transitorio)
   ↓
[INITRAMFS /init]
   ├─ mount proc/sys/dev/run/tmp
   ├─ cerca rootfs: /dev/sr0 → /dev/vda → /dev/sda
   ├─ mount rootfs in /newroot
   ├─ pivot_root
   └─ exec /sbin/os_coordinator
   ↓
[OS_COORDINATOR (PID 1 finale)]
   ├─ BOOT        : log os-release
   ├─ IGNITION    : carica coordinator.yaml, registra servizi
   ├─ COGNITION   : AI produce piano di avvio
   ├─ IDLE        : heartbeat + watchdog + consulto AI ogni N tick
   └─ SHUTDOWN    : stop ordinato di evolution, agi_team, brain, supervisor
   ↓
[SHUTDOWN] pivot_root inverso, poweroff/reboot
```

## Ciclo di vita del PID 1

```
   ┌──────────────────────────────────────────────┐
   │                                              │
   │  BOOT ─→ IGNITION ─→ COGNITION ─→ IDLE       │
   │                              ↑       │       │
   │                              └── IDLE │       │
   │                                      │       │
   │                              INTERVENTION    │
   │                                      │       │
   │                                      ↓       │
   │                                  IDLE        │
   │                                              │
   │   ogni fase può andare a SHUTDOWN            │
   │                                              │
   │   SHUTDOWN è terminale                       │
   │                                              │
   └──────────────────────────────────────────────┘
```

## Componenti in dettaglio

### 1. `os_coordinator/`

Il cervello del sistema operativo. Modulo Python (≥3.12) con:

- `phases.py`: enum `Phase` e matrice `ALLOWED_TRANSITIONS`
- `state_machine.py`: macchina a stati con history
- `agentic_brain.py`: client Ollama Cloud con system prompt dedicato
- `policy.py`: filtro whitelist + rate limit
- `health.py`: watchdog
- `service_registry.py`: registro dei 4 servizi canonici
- `coordinator.py`: ciclo di vita, integrazione di tutto
- `__main__.py`: CLI `speace-os-coordinator`

### 2. `/lib/speace/supervisor.py`

Service manager ispirato a s6/runit:

- 1 processo long-running (NON PID 1)
- Auto-restart entro limiti (default 6/h per servizio)
- Marker-based dispatch: legge `/var/run/speace/<service>.<op>` scritto da `os_coordinator`
- Log per servizio in `/var/log/speace/<name>.log`
- Stato persistito in memoria (no DB)

### 3. Servizi canonici (in `/etc/speace/services/<name>/run`)

| Servizio | Comando | Porta | Note |
|---|---|---|---|
| `speace-brain` | `python3 -m speace_core.cli run` | 8787 | Cervello cellulare continuo |
| `speace-evolution` | `python3 -m speace_core.cli live --dashboards` | 5692/5697 | Demone auto-miglioramento |
| `speace-agi-team` | `python3 -m speace_agi_team.main` | 8686 | Team agentico |
| `speace-dashboard` | `python3 -m speace_core.cli monitor` | 8787 | Monitor FastAPI |

### 4. Initramfs

Minimalissimo: contiene solo `/init` e una copia di `os_coordinator` come
fallback. Tutto il resto risiede nel rootfs.

### 5. Cellular_speace snapshot

Tutto `cellular_speace/` (meno `__pycache__`, `.git`, pdf, ecc.) viene
copiato in `/opt/speace/cellular_speace/`. Il coordinatore NON lo modifica:
lo tratta come "codice di produzione" e propone solo modifiche attraverso
l'agentic AI.

## Variabili d'ambiente

Caricate da `/etc/speace/env.conf`:

```sh
OLLAMA_API_KEY=[REDACTED-OLLAMA-KEY]
OLLAMA_ENDPOINT=https://ollama.com
OLLAMA_MODEL=minimax-m3:cloud
SPEACE_HOME=/opt/speace
SPEACE_CELLULAR=/opt/speace/cellular_speace
SPEACE_PYTHON=/opt/speace/.venv/bin/python
SPEACE_STATE_DIR=/var/lib/speace
SPEACE_LOG_DIR=/var/log/speace
```

## Decisioni di design

1. **Perché Alpine?** 50 MB di rootfs, perfetto per embedded e CI. Niente systemd.
2. **Perché Python come init?** Coerenza con tutto il resto del progetto SPEACE. Veloce da modificare.
3. **Perché non systemd?** Vogliamo un init cognitivo, non un gestore di unità dichiarative. La complessità di systemd non ci serve.
4. **Perché minimax-m3:cloud?** Modello di punta via Ollama Cloud, già integrato in `speace_agi_team`.
5. **Perché 4 servizi canonici?** Ogni servizio rappresenta un "organo" dell'organismo (cervello, evoluzione, team, monitor).
