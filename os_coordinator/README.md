# os_coordinator — PID 1 cognitivo

Il cuore del sistema operativo SPEACE OS. Gira come PID 1 dopo che il
kernel ha completato il boot e ha montato l'initramfs.

## Responsabilità

1. Eseguire il **ciclo di vita** del sistema: BOOT → IGNITION → COGNITION → IDLE → (INTERVENTION ↔ IDLE) → SHUTDOWN
2. Consultare l'**agentic AI** (`minimax-m3:cloud` via Ollama Cloud) per decidere l'avvio, la supervisione e lo spegnimento dei servizi cognitivi
3. Mantenere il **registro dei servizi** canonici (`speace-brain`, `speace-evolution`, `speace-agi-team`, `speace-dashboard`)
4. Fare **watchdog** dei servizi e delle metriche vitali
5. Garantire uno **spegnimento ordinato** (evolution → agi_team → brain → supervisore)

## Differenze da `speace_agi_team`

| Aspetto | `speace_agi_team` | `os_coordinator` |
|---|---|---|
| Dominio | supervisione del cervello e proposte di miglioramento | orchestrazione di tutto il sistema operativo |
| Livello | applicativo | sistema (PID 1) |
| Decisione | propone/non propone, mai esegue | esegue azioni filtrate da `policy.py` |
| Quando gira | opzionale, post-boot | sempre, dal primo momento |

## CLI

```bash
# Avvio come PID 1
speace-os-coordinator

# Test senza effetti reali
speace-os-coordinator --dry-run --phase COGNITION

# Singolo tick (per test)
speace-os-coordinator --once

# Stato corrente
speace-os-coordinator --status
```

## Test

```bash
pytest os_coordinator/tests/ -v
```
