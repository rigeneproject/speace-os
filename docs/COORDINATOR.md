# Coordinatore OS — Contratto

Il coordinatore OS (`os_coordinator/`) è un agente a 6 stati che orchestra
l'avvio, la supervisione e lo spegnimento dei servizi cognitivi.

## API pubblica

### `OSCoordinator`

```python
from os_coordinator.coordinator import OSCoordinator, CoordinatorConfig

coord = OSCoCoordinator(
    config=CoordinatorConfig(dry_run=True, offline=True),
)
asyncio.run(coord.run())
```

### Comandi CLI

```bash
# Avvio come PID 1
speace-os-coordinator

# Test senza effetti
speace-os-coordinator --dry-run --phase COGNITION

# Singolo tick
speace-os-coordinator --once

# Stato corrente
speace-os-coordinator --status
```

## State machine

### Fasi (enum)

| Fase | Compito | Transizioni |
|---|---|---|
| `BOOT` | Monta proc/sys/dev, leggi os-release | → `IGNITION`, `SHUTDOWN` |
| `IGNITION` | Carica config, valida installazione | → `COGNITION`, `SHUTDOWN` |
| `COGNITION` | AI produce piano di avvio | → `IDLE`, `INTERVENTION`, `SHUTDOWN` |
| `IDLE` | Heartbeat + watchdog + consulto AI | → `INTERVENTION`, `SHUTDOWN` |
| `INTERVENTION` | Esegue azioni correttive | → `IDLE`, `SHUTDOWN` |
| `SHUTDOWN` | Stato terminale | (nessuna) |

### Garanzie

- `BOOT` è la fase iniziale e non è mai raggiungibile di nuovo
- `SHUTDOWN` è terminale (nessuna transizione in uscita)
- Ogni fase può portare a `SHUTDOWN` direttamente

## Contratto Agentic AI

### Input

Il coordinatore invia all'AI un contesto JSON:

```json
{
  "hostname": "speace-os-001",
  "phase": "IDLE",
  "tick": 42,
  "uptime_sec": 305.0,
  "registry": {
    "speace-brain": {"state": "running", "pid": 123, "uptime_sec": 300.0, ...},
    "speace-evolution": {"state": "running", "pid": 124, ...},
    "speace-agi-team": {"state": "stopped", ...},
    "speace-dashboard": {"state": "running", ...}
  },
  "state_machine": {"current": "IDLE", "transitions": [...]},
  "vital_metrics": {"coherence_phi": 0.65, "ilf": 0.71, ...},
  "stage": "idle_supervision" | "initial_startup" | "intervention"
}
```

### Output atteso

```json
{
  "phase_decision": "START_SERVICES" | "INTERVENE" | "IDLE" | "SHUTDOWN",
  "actions": [
    {"service": "speace-brain", "op": "start" | "stop" | "restart" | "status"}
  ],
  "reasoning": "spiegazione in italiano, max 200 caratteri",
  "urgency": "low" | "medium" | "high"
}
```

### Vincoli

- Solo i 4 servizi canonici sono accettati (whitelist)
- Solo le 4 operazioni canoniche (start, stop, restart, status)
- Rate limit: max 3 restart per servizio in 5 minuti
- L'AI NON può:
  - Manipolare il filesystem
  - Uccidere processi arbitrari
  - Cambiare la configurazione
  - Accedere a /dev
  - Scrivere fuori da `/var/{run,lib,log}/speace/`

## Service registry

I 4 servizi canonici sono dichiarati in `service_registry.py`:

```python
CANONICAL_SERVICES = (
    "speace-brain",       # speace_core
    "speace-evolution",   # evolution_daemon LiveOrganism
    "speace-agi-team",    # speace_agi_team web server
    "speace-dashboard",   # monitor FastAPI
)
```

Per aggiungere un nuovo servizio:
1. Aggiungilo a `CANONICAL_SERVICES`
2. Aggiungilo a `ALLOWED_OPS` in `policy.py`
3. Crea `/etc/speace/services/<name>/run` eseguibile
4. Aggiungi una sezione in `/etc/speace/coordinator.yaml`

## Health check

`check_health(registry, vital_metrics)` ritorna un `HealthReport` con:

- `healthy`: bool
- `failed_services`: lista di nomi
- `stale_services`: servizi RUNNING senza heartbeat recente (>60s)
- `vital_metrics`: dict passato in input
- `notes`: lista di spiegazioni testuali

`healthy` è `False` se:
- Almeno un servizio è `FAILED`
- `coherence_phi < 0.05`
- `ilf < 0.10`

## Modalità speciali

### `--offline`

Il coordinatore non consulta Ollama Cloud. Tutte le decisioni sono di
default `IDLE`. Utile per:
- Test CI senza dipendenza da rete
- Boot in ambienti air-gapped
- Smoke test del supervisore

### `--dry-run`

Il coordinatore non scrive marker files. Lo stato del registry viene
aggiornato in-memory ma nessun servizio viene realmente avviato.

### `--once`

Esegue un singolo tick ed esce. Per test rapidi.

### `--status`

Stampa lo stato corrente come JSON ed esce.
