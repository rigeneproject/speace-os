# Service Management

Il service manager è ispirato a s6/runit ma scritto in Python per
coerenza con il resto dell'ecosistema. Vive in
[`/lib/speace/supervisor.py`](../rootfs/lib/speace/supervisor.py) e
lavora in coppia con `os_coordinator`.

## Modello

```
┌──────────────────────────────────────────────────────────┐
│  os_coordinator (PID 1)                                  │
│   - Decide cosa fare                                     │
│   - Scrive marker in /var/run/speace/<service>.<op>      │
└────────────────────┬─────────────────────────────────────┘
                     │ marker file
                     ▼
┌──────────────────────────────────────────────────────────┐
│  speace-supervisor (PID ≠ 1, long-running)               │
│   - Polling 1s su /var/run/speace/                       │
│   - Esegue /etc/speace/services/<name>/run               │
│   - Watchdog: rileva processi morti, auto-restart        │
│   - Aggiorna /var/log/speace/<name>.log                  │
└──────────────────────────────────────────────────────────┘
```

## Servizi canonici

Ogni servizio è una directory in `/etc/speace/services/<name>/` con:

- `run`: script eseguibile (POSIX sh, NON Python)
- Opzionalmente: `finish`, `down`, `dependencies` (non usati in 0.1.0)

I 4 servizi canonici al lancio:

| Nome | Comando | Logica |
|---|---|---|
| `speace-brain` | `python3 -m speace_core.cli run` | Cervello cellulare continuo |
| `speace-evolution` | `python3 -m speace_core.cli live --dashboards` | Demone auto-miglioramento |
| `speace-agi-team` | `python3 -m speace_agi_team.main --port 8686` | Team agentico AI |
| `speace-dashboard` | `python3 -m speace_core.cli monitor` | Monitor FastAPI |

## Dispatch via marker

Il supervisore polling 1s su `/var/run/speace/`. Quando trova un file
marker `<service>.<op>`:

```python
marker = Path(f"/var/run/speace/{service}.{op}")
# se esiste: leggilo, cancellalo, esegui l'azione
```

Esempio: `os_coordinator` vuole riavviare il cervello:

```sh
touch /var/run/speace/speace-brain.restart
```

Entro 1s, il supervisore lo legge, lo cancella, e chiama `restart("speace-brain")`.

## Watchdog

Ogni secondo il supervisore controlla i processi figli. Se uno è
terminato inaspettatamente:

1. Controlla `auto_restart` (default `True`)
2. Controlla `max_restarts_per_hour` (default 6)
3. Se entro i limiti: riavvia
4. Se fuori limiti: marca come `FAILED`, logga errore

Il `coordinator` polling la salute:
- Se vede un servizio `FAILED`: potenziale `INTERVENTION`
- Se vede un servizio RUNNING con heartbeat stantio (>60s): potenziale riavvio

## Configurazione

`/etc/speace/coordinator.yaml` definisce la policy di supervisione:

```yaml
services:
  speace-brain:
    critical: true
    auto_restart: true
    max_restarts_per_hour: 6
  speace-evolution:
    auto_restart: true
    max_restarts_per_hour: 3
```

## Aggiungere un nuovo servizio

1. Crea `/etc/speace/services/<name>/run` (eseguibile)
2. Aggiungi `<name>` a `CANONICAL_SERVICES` in `os_coordinator/service_registry.py`
3. Aggiungi `<name>` a `ALLOWED_OPS` in `os_coordinator/policy.py`
4. Aggiungi sezione in `/etc/speace/coordinator.yaml`
5. Riavvia `os_coordinator` (o forza un refresh del supervisore)

## Comandi utili

```bash
# Status di tutti i servizi (via coordinatore)
speace-os-status

# Status di un singolo servizio (scrivere marker)
touch /var/run/speace/speace-brain.status
# (il log mostrerà lo status entro 1s)

# Riavvio manuale
touch /var/run/speace/speace-brain.restart

# Log di un servizio
tail -f /var/log/speace/speace-brain.log
```
