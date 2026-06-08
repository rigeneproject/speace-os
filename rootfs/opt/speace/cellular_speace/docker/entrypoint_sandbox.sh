#!/usr/bin/env bash
# Stage 2.5 — Sandbox Autonomy (laboratory)
# ENTRYPOINT del container. NON viene eseguito sull'host.
# Tutto ciò che avviene qui dentro è confinato al container.
#
# Comportamento:
#   1. Verifica la coerenza del perimetro (non siamo root, siamo in container)
#   2. Verifica la variabile SPEACE_SANDBOX (default 0 = safe)
#   3. Se SPEACE_SANDBOX=1, logga esplicitamente l'attivazione del profilo
#   4. Lancia il CMD passato (default: `speace monitor`)

set -euo pipefail

# --- Banner di identificazione ---
echo "============================================================"
echo " SPEACE Stage 2.5 — Sandbox Autonomy (laboratory)"
echo " Container PID: $$"
echo " User: $(id -un) (uid=$(id -u))"
echo " Working dir: $(pwd)"
echo "============================================================"

# --- Verifica perimetro: non dobbiamo essere root ---
# (l'utente speace è stato creato con uid 1001 nel Dockerfile)
if [ "$(id -u)" = "0" ]; then
    echo "[FATAL] entrypoint sta girando come root." >&2
    echo "        Il Dockerfile deve passare a USER speace." >&2
    exit 1
fi

# --- Verifica perimetro: dobbiamo essere in un container Linux ---
# /proc/1/cgroup esiste solo nei container; inoltre cerchiamo i marker
# tipici di Docker/containerd.
IN_CONTAINER=0
if [ -f /.dockerenv ] || grep -qE "docker|containerd|kubepods" /proc/1/cgroup 2>/dev/null; then
    IN_CONTAINER=1
fi

if [ "$IN_CONTAINER" = "0" ]; then
    echo "[WARN] Non sembra di essere in un container." >&2
    echo "       Questo entrypoint dovrebbe essere eseguito solo dentro Docker." >&2
    # Non blocchiamo: potrebbe essere un test locale
fi

# --- Verifica variabile sandbox ---
SPEACE_SANDBOX="${SPEACE_SANDBOX:-0}"
SPEACE_LAB_RUN_ID="${SPEACE_LAB_RUN_ID:-unknown}"

mkdir -p /cellular_speace/data/sandbox

if [ "$SPEACE_SANDBOX" = "1" ]; then
    echo ""
    echo "[SPEACE_SANDBOX=1] Modalità sandbox estesa ATTIVA."
    echo "  • L'attuatore EmbodiedActionActuator accetta un set esteso di azioni."
    echo "  • Tutte le azioni sono loggate in data/sandbox/activations.jsonl"
    echo "  • Stage DNA corrente: 2.5-sandbox-lab"
    echo "  • Lab run id: ${SPEACE_LAB_RUN_ID}"
    echo ""

    # Log di attivazione persistente
    ACTIVATION_LOG="/cellular_speace/data/sandbox/activations.jsonl"
    ACTIVATION_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "{\"timestamp\":\"${ACTIVATION_TS}\",\"event\":\"sandbox_activated\",\"run_id\":\"${SPEACE_LAB_RUN_ID}\",\"stage\":\"2.5-sandbox-lab\",\"user\":\"$(id -un)\",\"in_container\":${IN_CONTAINER}}" \
        >> "$ACTIVATION_LOG"
else
    echo ""
    echo "[SPEACE_SANDBOX=0] Modalità SAFE."
    echo "  • Guardrail standard del codice attivi."
    echo "  • Nessuna azione estesa dell'attuatore."
    echo "  • Per attivare la modalità lab: SPEACE_SANDBOX=1 <comando>"
    echo ""
fi

# --- Esegui CMD ---
echo "[entrypoint] Esecuzione: $*"
echo "============================================================"

exec "$@"
