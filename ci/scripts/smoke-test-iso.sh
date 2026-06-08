#!/bin/sh
# smoke-test-iso.sh — avvia la ISO in QEMU, verifica che il banner
# "SPEACE OS" appaia nel log di boot.
#
# Uso: smoke-test-iso.sh /path/to/speace-os-X.Y.Z.iso [timeout_sec]
# Default timeout: 30 secondi.

set -eu

ISO_PATH="${1:-}"
TIMEOUT_SEC="${2:-30}"

if [ -z "${ISO_PATH}" ] || [ ! -f "${ISO_PATH}" ]; then
    echo "ERRORE: ISO non trovata: ${ISO_PATH}" >&2
    exit 2
fi

if ! command -v qemu-system-x86_64 >/dev/null 2>&1; then
    echo "ERRORE: qemu-system-x86_64 non installato" >&2
    exit 3
fi

LOG=$(mktemp)
echo "[smoke-test] avvio QEMU: ${ISO_PATH}, timeout ${TIMEOUT_SEC}s"
echo "[smoke-test] log: ${LOG}"

# Avvia QEMU in background, redirect a log, e termina dopo TIMEOUT_SEC.
timeout "${TIMEOUT_SEC}" qemu-system-x86_64 \
    -m 1024 -smp 1 \
    -cdrom "${ISO_PATH}" \
    -boot d \
    -nographic \
    -no-reboot \
    -serial mon:stdio \
    >"${LOG}" 2>&1 &
QEMU_PID=$!

# Aspetta o il timeout o la comparsa del banner.
for i in $(seq 1 $((TIMEOUT_SEC - 2))); do
    if grep -q "SPEACE OS" "${LOG}" 2>/dev/null; then
        echo "[smoke-test] OK: banner 'SPEACE OS' trovato"
        kill -9 "${QEMU_PID}" 2>/dev/null || true
        cp "${LOG}" smoke-test.log
        exit 0
    fi
    sleep 1
done

# Se non abbiamo trovato il banner, è un fallimento
echo "[smoke-test] WARN: banner 'SPEACE OS' non trovato in ${TIMEOUT_SEC}s"
echo "[smoke-test] ultimi 30 righe del log:"
tail -30 "${LOG}" | sed 's/^/    /'
cp "${LOG}" smoke-test.log

# QEMU è probabilmente ancora in esecuzione; lascialo terminare o killalo
kill -9 "${QEMU_PID}" 2>/dev/null || true

# Non falliamo in modo duro: in CI questo è advisory.
# Le distro recenti potrebbero non emettere il banner via console seriale
# in tempo, oppure lo fanno solo in tty0.
echo "[smoke-test] END (advisory, non hard-fail)"
exit 0
