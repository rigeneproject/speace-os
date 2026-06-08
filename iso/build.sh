#!/bin/sh
# build.sh — build completa della distro SPEACE OS.
# Produce in out/:
#   - kernel/bzImage
#   - rootfs/        (directory pronta per chroot o per impacchettamento)
#   - rootfs.tar.gz  (rootfs compresso per boot initramfs)
#   - initramfs.cpio.gz
#   - speace-os-0.1.0-cos.iso
#   - speace-os-0.1.0-cos.qcow2
#
# Dipendenze: gcc, make, qemu-utils, xorriso, grub, cpio, gzip, debootstrap/apk

set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${HERE}/.." && pwd)"
OUT="${ROOT}/out"
LOG="${OUT}/build.log"

mkdir -p "${OUT}"

# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "${LOG}"; }
fail() { log "FATAL: $*" >&2; exit 1; }

require() {
    command -v "$1" >/dev/null 2>&1 || fail "comando mancante: $1"
}

# ------------------------------------------------------------------ #
# 1. Kernel
# ------------------------------------------------------------------ #

log "=== 1/4 Build kernel ==="
if [ ! -f "${OUT}/kernel/bzImage" ]; then
    "${ROOT}/kernel/build-kernel.sh" 2>&1 | tee -a "${LOG}"
else
    log "kernel già presente, skip"
fi

# ------------------------------------------------------------------ #
# 2. Rootfs
# ------------------------------------------------------------------ #

log "=== 2/4 Build rootfs (Alpine 3.20 base) ==="
ROOTFS="${OUT}/rootfs"
if [ ! -d "${ROOTFS}/bin" ]; then
    rm -rf "${ROOTFS}"
    mkdir -p "${ROOTFS}"

    # Strategia: usiamo un tar di Alpine 3.20 minimale scaricato.
    ALPINE_VERSION=3.20
    ALPINE_ROOT="alpine-minirootfs-${ALPINE_VERSION}.3-x86_64"
    ALPINE_TAR="${OUT}/${ALPINE_ROOT}.tar.gz"

    if [ ! -f "${ALPINE_TAR}" ]; then
        log "scarico Alpine ${ALPINE_VERSION} rootfs"
        curl -fsSL -o "${ALPINE_TAR}" \
            "https://dl-cdn.alpinelinux.org/alpine/v${ALPINE_VERSION}/releases/x86_64/${ALPINE_ROOT}.tar.gz"
    fi

    log "estraggo Alpine rootfs"
    tar -xzf "${ALPINE_TAR}" -C "${ROOTFS}"

    # Overlay del nostro rootfs
    log "applico overlay rootfs/ di SPEACE OS"
    cp -a "${ROOT}/rootfs/." "${ROOTFS}/"

    # Copia di cellular_speace (snapshot)
    if [ ! -d "${ROOTFS}/opt/speace/cellular_speace/speace_core" ]; then
        log "copio cellular_speace/ in /opt/speace"
        SRC="$(cd "${ROOT}/../cellular_speace" && pwd)"
        mkdir -p "${ROOTFS}/opt/speace"
        # Filtra __pycache__ e cartelle di cache
        rsync -a --exclude='__pycache__' --exclude='.pytest_cache' --exclude='.ruff_cache' \
                 --exclude='.opencode' --exclude='.coverage' --exclude='cov.json' \
                 --exclude='*.pyc' --exclude='*.pdf' --exclude='_temp_*.txt' \
                 "${SRC}/" "${ROOTFS}/opt/speace/cellular_speace/"
    fi

    # Copia di os_coordinator (modulo nuovo)
    if [ ! -d "${ROOTFS}/usr/lib/python3.12/site-packages/os_coordinator" ] && \
       [ ! -d "${ROOTFS}/usr/lib/python3.13/site-packages/os_coordinator" ]; then
        log "installo os_coordinator/ in site-packages"
        SITE_PKGS="$(find "${ROOTFS}/usr/lib" -type d -name 'site-packages' | head -1)"
        if [ -n "${SITE_PKGS}" ]; then
            cp -a "${ROOT}/os_coordinator/." "${SITE_PKGS}/os_coordinator/"
        else
            # fallback: installa in /opt/speace/os_coordinator e aggiungi a PYTHONPATH
            cp -a "${ROOT}/os_coordinator" "${ROOTFS}/opt/speace/os_coordinator"
            mkdir -p "${ROOTFS}/etc/profile.d"
            echo "export PYTHONPATH=\"\${PYTHONPATH:-}:/opt/speace\"" \
                > "${ROOTFS}/etc/profile.d/speace-pythonpath.sh"
            chmod +x "${ROOTFS}/etc/profile.d/speace-pythonpath.sh"
        fi
    fi

    # Wrapper /sbin/os_coordinator (eseguibile dal rootfs dopo pivot_root).
    # È una copia speculare di initramfs/sbin/os_coordinator: se per qualche
    # motivo l'initramfs è stato strippato, l'init può comunque trovarlo qui.
    if [ -f "${ROOT}/initramfs/sbin/os_coordinator" ]; then
        mkdir -p "${ROOTFS}/sbin"
        cp -f "${ROOT}/initramfs/sbin/os_coordinator" "${ROOTFS}/sbin/os_coordinator"
        chmod +x "${ROOTFS}/sbin/os_coordinator"
        log "installo /sbin/os_coordinator (wrapper PID 1) nel rootfs"
    fi

    # Crea utente e directory di stato
    log "creo utente speace e directory di stato"
    if [ -x "${ROOTFS}/usr/sbin/adduser" ] || [ -x "${ROOTFS}/sbin/adduser" ]; then
        ADDU="$(find "${ROOTFS}" -name 'adduser' -executable -type f | head -1)"
        if [ -n "${ADDU}" ]; then
            chroot "${ROOTFS}" "$(basename "${ADDU}")" -D -s /bin/sh speace 2>/dev/null || true
        fi
    fi
    mkdir -p "${ROOTFS}/var/log/speace" \
             "${ROOTFS}/var/lib/speace" \
             "${ROOTFS}/var/run/speace" \
             "${ROOTFS}/run/speace"

    # Crea venv e installa dipendenze
    log "creo venv Python e installo dipendenze (se possibile)"
    PYBIN="$(find "${ROOTFS}/usr/bin" -name 'python3*' -executable -type f | head -1)"
    if [ -n "${PYBIN}" ]; then
        if chroot "${ROOTFS}" /usr/bin/python3 -m venv /opt/speace/.venv 2>/dev/null; then
            chroot "${ROOTFS}" /opt/speace/.venv/bin/pip install --quiet --no-cache-dir \
                pydantic pyyaml structlog httpx fastapi uvicorn websockets 2>&1 | tee -a "${LOG}" || \
                log "(warn) pip install fallita, continuo senza venv"
        else
            log "(warn) venv non creabile, userò python3 di sistema"
        fi
    fi
else
    log "rootfs già presente, skip"
fi

# ------------------------------------------------------------------ #
# 3. Initramfs
# ------------------------------------------------------------------ #

log "=== 3/4 Build initramfs ==="
INITRAMFS="${OUT}/initramfs.cpio.gz"
if [ ! -f "${INITRAMFS}" ]; then
    # Initramfs minimalissimo: contiene solo /init che è una copia di os_coordinator.
    # La maggior parte del sistema gira dal rootfs reale.
    WORK="$(mktemp -d)"
    mkdir -p "${WORK}"
    cp -a "${ROOT}/initramfs/." "${WORK}/"

    # Assicurati che /sbin/os_coordinator (wrapper PID 1) sia eseguibile.
    # cp -a preserva i bit +x dal filesystem sorgente, ma se i permessi
    # sul checkout sono persi (es. umask aggressivo), li ripristiniamo qui.
    if [ -f "${WORK}/sbin/os_coordinator" ]; then
        chmod +x "${WORK}/sbin/os_coordinator"
        log "initramfs: wrapper /sbin/os_coordinator (PID 1) reso eseguibile"
    else
        log "initramfs: WARN wrapper /sbin/os_coordinator non presente, init cadrebbe in shell"
    fi

    # Aggiungi os_coordinator al ramfs per garantire boot anche senza rootfs
    mkdir -p "${WORK}/opt/os_coordinator"
    cp -a "${ROOT}/os_coordinator/." "${WORK}/opt/os_coordinator/"

    cd "${WORK}"
    find . | cpio -o -H newc 2>/dev/null | gzip -9 > "${INITRAMFS}"
    cd - >/dev/null
    rm -rf "${WORK}"
    log "initramfs: ${INITRAMFS} ($(du -h "${INITRAMFS}" | cut -f1))"
fi

# ------------------------------------------------------------------ #
# 4. ISO
# ------------------------------------------------------------------ #

log "=== 4/4 Pack ISO ==="
"${HERE}/pack-iso.sh"

log "Build completata. Artefatti in ${OUT}/"
ls -la "${OUT}/" | tee -a "${LOG}"
