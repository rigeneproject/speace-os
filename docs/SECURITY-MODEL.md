# Security Model

Come SPEACE OS gestisce la sicurezza, i guardrail e i permessi.

## Principi fondamentali

1. **Defense in depth**: più livelli di protezione
2. **Default deny**: l'AI può solo fare ciò che è esplicitamente permesso
3. **No auto-escalation**: nessun `sudo` automatico, nessun `privileged`
4. **DNA Stage come policy**: il file `species_orientation.yaml` di
   cellular_speace è la fonte di verità per i limiti operativi
5. **Log di tutto**: ogni decisione AI, ogni azione del supervisore

## Modello di processi

| Processo | UID | Capabilities | Note |
|---|---|---|---|
| `os_coordinator` (PID 1) | root (init) | full (necessario per pivot_root) | Esegue il ciclo di vita |
| `speace-supervisor` | root | limitate | Esegue i servizi come utenti non-root |
| `speace-brain` | speace (uid 1001) | limitate | Cervello cellulare |
| `speace-evolution` | speace (uid 1001) | limitate | Demone auto-miglioramento |
| `speace-agi-team` | speace (uid 1001) | limitate | Team agentico AI |
| `speace-dashboard` | speace (uid 1001) | limitate | Monitor FastAPI |

## Capabilities

`speace-supervisor` viene invocato con:
```sh
# Solo se root. In CI si usa root completo.
# In produzione si consiglia:
setcap cap_dac_override,cap_chown,cap_setuid,cap_setgid,cap_kill+ep /usr/bin/speace-supervisor
```

`os_coordinator` come PID 1 ha i permessi completi di init, ma è scritto
per non usarli: monta, logga, dispatch.

## Guardrail del coordinatore

L'agentic AI NON può:

1. **Manipolare il filesystem** fuori da `/var/{run,lib,log}/speace/`
2. **Accedere a /dev** (no mount, no device passthrough)
3. **Eseguire comandi arbitrari**: solo i 4 `run` script
4. **Cambiare la configurazione**: `coordinator.yaml` è read-only
5. **Modificare `cellular_speace/`**: snapshot immutabile in `/opt/speace/`
6. **Accedere a rete** in modalità lab (segue il modello Stage 2.5)

## Whitelist azioni

In `os_coordinator/policy.py`:

```python
ALLOWED_OPS: dict[str, set[str]] = {
    "speace-brain":      {"start", "stop", "restart", "status"},
    "speace-evolution":  {"start", "stop", "restart", "status"},
    "speace-agi-team":   {"start", "stop", "restart", "status"},
    "speace-dashboard":  {"start", "stop", "restart", "status"},
}
```

Qualsiasi altra azione viene rifiutata con log.

## Rate limit

- Max 3 restart per servizio in 5 minuti
- Oltre il limite: l'azione viene rifiutata, l'errore loggato
- Lo stato del servizio rimane invariato

## Watchdog anti-crashloop

Il supervisore rileva crashloop:
- Se un servizio muore N volte in M minuti, viene marcato `FAILED`
- Il coordinatore può chiedere all'AI se riavviare ancora o lasciarlo spento
- Di default: dopo 6 morti in 1 ora, non riavvia automaticamente

## DNS / Network

- Di default: il sistema ha accesso alla rete (necessario per Ollama Cloud)
- Modalità safe: `--offline` per ambienti air-gapped
- Nessun firewall di default: si assume che l'utente configuri la rete

## Log audit

Tutto è loggato in `/var/log/speace/`:

```
/var/log/speace/
├── coordinator.log
├── supervisor.log
├── speace-brain.log
├── speace-evolution.log
├── speace-agi-team.log
└── speace-dashboard.log
```

Inoltre `os_coordinator` mantiene `decisions_log` in memoria, accessibile
via `speace-os-status`.

## Hardering del kernel

`kernel/linux-config` include:

- No driver GPU (DRM disabilitato)
- No wireless
- No bluetooth
- No sound
- KASLR abilitato (default kernel)
- `randomize_kstack_offset=y` (se abilitato in config)
- No `CONFIG_USERMODEHELPER` non necessari

## Aggiornamenti

In 0.1.0-cos: nessun meccanismo automatico. Aggiornare significa
rebuildare la ISO. Roadmap in CHANGELOG.
