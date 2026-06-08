# SPEACE Sandbox Lab — Stage 2.5

Profilo di laboratorio isolato per testare l'autonomia di SPEACE **senza**
toccare l'host. Tutto ciò che avviene qui dentro è confinato al container.

## Vincoli del perimetro

Questi vincoli sono **non negoziabili** e documentati anche in
`docs/speace_seed.md` e `speace_core/dna/genome/core/species_orientation.yaml`:

- ❌ Niente `privileged: true`
- ❌ Niente device passthrough (`/dev/sda`, GPU, USB, ecc.)
- ❌ Niente `network_mode: host`
- ❌ Niente volumi montati dall'host oltre la working dir del progetto
- ❌ Niente `seccomp:unconfined` in produzione (accettabile solo per dev)
- ❌ Niente `no-new-privileges: false`
- ✅ Capabilities ridotte: solo `CHOWN SETUID SETGID DAC_OVERRIDE`
- ✅ Rete isolata (`network_mode: none` di default)
- ✅ Risorse limitate: 2 CPU, 2 GB RAM, 256 PID
- ✅ `tmpfs` per `/tmp` e `/run`
- ✅ Hardening systemd documentato (vedi `speace-lab.service`)

## Avvio

```bash
# 1. Build dell'immagine (una volta)
docker build -f docker/Dockerfile.sandbox -t speace-sandbox:latest .

# 2. Avvio in modalità SAFE (default)
docker compose -f docker/docker-compose.sandbox.yml up

# 3. Avvio in modalità SANDBOX ESTESA (per i test di autonomia)
SPEACE_SANDBOX=1 docker compose -f docker/docker-compose.sandbox.yml up

# 4. Con identificatore di run per audit
SPEACE_SANDBOX=1 SPEACE_LAB_RUN_ID=exp-001 docker compose -f docker/docker-compose.sandbox.yml up
```

## Verifica del perimetro

Dopo l'avvio, **verifica sempre** che i vincoli siano rispettati:

```bash
# Il container non deve avere capability extra
docker inspect speace-sandbox-lab --format '{{.HostConfig.CapAdd}}'
# Atteso: [CHOWN SETUID SETGID DAC_OVERRIDE]

# Non deve essere privileged
docker inspect speace-sandbox-lab --format '{{.HostConfig.Privileged}}'
# Atteso: false

# La rete deve essere none
docker inspect speace-sandbox-lab --format '{{.HostConfig.NetworkMode}}'
# Atteso: none

# Nessun device passthrough
docker inspect speace-sandbox-lab --format '{{json .HostConfig.Devices}}'
# Atteso: null o []
```

## Audit

Ogni attivazione della modalità sandbox estesa viene loggata in:

- `data/sandbox/activations.jsonl` (dentro il container, persistente via volume)
- `/var/log/speace-lab/` (se si usa il profilo systemd)

## Cosa NON contiene questo setup

- ❌ Accesso a Internet (rete disabilitata di default)
- ❌ Accesso a `/dev` reali (solo device virtuali del container)
- ❌ Accesso a `/proc` reale (solo namespace di processo del container)
- ❌ Modifica dell'host (no volumi root)
- ❌ Persistenza sull'host (i volumi sono Docker-managed)

## Cosa contiene

- ✅ Python 3.12 + SPEACE installato in editable mode
- ✅ `sandbox/sandbox_profile.yaml` per il profilo esteso (vedi Punto 2)
- ✅ Sensori simulati (da `simulated_environment_engine.py` — Punto 4)
- ✅ Volume persistente per dati e report di laboratorio
- ✅ Healthcheck interno
- ✅ Utente non-root `speace` (uid 1001)

## Note sul DNA

Lo Stage 2.5 deve essere aggiunto a
`speace_core/dna/genome/core/species_orientation.yaml` con il testo:

```yaml
stage_2_5:
  name: "Sandboxed Lab Autonomy"
  description: >
    L'organismo SPEACE è installato in un ambiente isolato (container/VM)
    e opera con privilegi amministrativi SOLO all'interno di quell'ambiente.
    L'ambiente stesso è considerato un "corpo di test"; l'invariante
    "no expansion into external systems" si applica al sistema ospite,
    non al sandbox. L'uscita dal sandbox richiede uno stage successivo
    esplicito e autorizzato.
  invariants:
    - "Il codice conserva i guardrail interni; il profilo sandbox aggiunge
      permessi operativi solo via opt-in esplicito."
    - "Ogni attivazione del profilo viene loggata in modo persistente."
    - "Niente device passthrough, niente reti host, niente volumi root."
```

## Limitazioni note

- La rete è disabilitata di default. Se servono comunicazioni tra container
  (es. simulare due nodi SPEACE che parlano tra loro), attivare la sezione
  `networks` commentata in fondo a `docker-compose.sandbox.yml` e usare
  un bridge interno.
- Per test che richiedono più isolamento di rete (es. esporre porte),
  aprire una issue prima di modificare il compose.
