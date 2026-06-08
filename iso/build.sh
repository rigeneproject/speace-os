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
    # ATTENZIONE: il progetto usa src layout (src/os_coordinator/).
    # Copiamo SOLO src/os_coordinator/ non l'intera directory del progetto.
    if [ ! -d "${ROOTFS}/usr/lib/python3.12/site-packages/os_coordinator" ] && \
       [ ! -d "${ROOTFS}/usr/lib/python3.13/site-packages/os_coordinator" ]; then
        log "installo os_coordinator module in site-packages"
        SITE_PKGS="$(find "${ROOTFS}/usr/lib" -type d -name 'site-packages' | head -1)"
        if [ -n "${SITE_PKGS}" ]; then
            # src layout: copia src/os_coordinator/ -> site-packages/os_coordinator/
            mkdir -p "${SITE_PKGS}/os_coordinator"
            cp -a "${ROOT}/os_coordinator/src/os_coordinator/." "${SITE_PKGS}/os_coordinator/"
        else
            # fallback: installa direttamente in /opt/speace (che è già in PYTHONPATH)
            log "site-packages non trovato, installo in /opt/speace"
            mkdir -p "${ROOTFS}/opt/speace/os_coordinator"
            cp -a "${ROOT}/os_coordinator/src/os_coordinator/." "${ROOTFS}/opt/speace/os_coordinator/"
            # PYTHONPATH=/opt/speace permette "import os_coordinator"
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

    # Installa Python3 in Alpine (non presente nella minirootfs)
    log "installo python3 nel rootfs Alpine"
    if [ -x "${ROOTFS}/sbin/apk" ] || [ -x "${ROOTFS}/usr/bin/apk" ]; then
        APK="$(find "${ROOTFS}" -name 'apk' -executable -type f | head -1)"
        if [ -n "${APK}" ]; then
            # Fix risoluzione DNS per apk in chroot
            mkdir -p "${ROOTFS}/etc"
            echo "nameserver 1.1.1.1" > "${ROOTFS}/etc/resolv.conf"
            # Aggiorna repo e installa python3 + pip
            chroot "${ROOTFS}" "$(basename "${APK}")" update 2>&1 | tee -a "${LOG}" || true
            chroot "${ROOTFS}" "$(basename "${APK}")" add --no-cache \
                python3 py3-pip py3-virtualenv busybox 2>&1 | tee -a "${LOG}" || \
                log "(warn) apk add python3 fallita, continuo comunque"
        fi
    else
        log "(warn) apk non trovato in Alpine rootfs, installazione python3 saltata"
    fi

    # Crea venv e installa dipendenze
    PYBIN="$(find "${ROOTFS}/usr/bin" -name 'python3*' -executable -type f | head -1)"
    if [ -n "${PYBIN}" ]; then
        log "creo venv Python e installo dipendenze"
        if chroot "${ROOTFS}" /usr/bin/python3 -m venv /opt/speace/.venv 2>/dev/null; then
            chroot "${ROOTFS}" /opt/speace/.venv/bin/pip install --quiet --no-cache-dir \
                pydantic pyyaml structlog httpx fastapi uvicorn websockets 2>&1 | tee -a "${LOG}" || \
                log "(warn) pip install fallita, continuo senza venv"
        else
            log "(warn) venv non creabile, useremo python3 di sistema"
            # Se venv fallisce, crea symlink diretto
            ln -sf "${PYBIN}" "${ROOTFS}/opt/speace/.venv/bin/python" 2>/dev/null || true
        fi
    else
        log "(warn) python3 non trovato dopo installazione, os_coordinator non partirà"
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
    WORK="$(mktemp -d)"
    mkdir -p "${WORK}"
    cp -a "${ROOT}/initramfs/." "${WORK}/"

    # Assicurati che /sbin/os_coordinator sia eseguibile
    if [ -f "${WORK}/sbin/os_coordinator" ]; then
        chmod +x "${WORK}/sbin/os_coordinator"
        log "initramfs: wrapper /sbin/os_coordinator reso eseguibile"
    else
        log "initramfs: WARN wrapper sbin/os_coordinator non presente"
    fi

    # Aggiungi os_coordinator module al ramfs (fallback, se Python presente)
    # NOTA: src layout — copia da src/os_coordinator/
    mkdir -p "${WORK}/opt/os_coordinator"
    cp -a "${ROOT}/os_coordinator/src/os_coordinator/." "${WORK}/opt/os_coordinator/"

    # --- AGGIUNTA: busybox per initramfs (fornisce sh, mount, pivot_root, etc.) ---
    BUSYBOX_BIN="${WORK}/bin/busybox"
    BUSYBOX_URL="https://busybox.net/downloads/binaries/1.36.1-i686/busybox"
    BUSYBOX_URL_X86_64="https://busybox.net/downloads/binaries/1.36.1-x86_64/busybox"
    mkdir -p "${WORK}/bin" "${WORK}/usr/bin" "${WORK}/sbin" "${WORK}/usr/sbin"

    # 1) Cerca busybox prima nel rootfs Alpine (se già estratto)
    BB_FOUND=""
    if [ -d "${ROOTFS}/bin" ]; then
        BB_FOUND="$(find "${ROOTFS}/bin" -name 'busybox' -type f | head -1)"
    fi
    if [ -z "${BB_FOUND}" ] && [ -d "${ROOTFS}/usr/bin" ]; then
        BB_FOUND="$(find "${ROOTFS}/usr/bin" -name 'busybox' -type f | head -1)"
    fi

    if [ -n "${BB_FOUND}" ]; then
        log "initramfs: busybox copiato da Alpine rootfs: ${BB_FOUND}"
        cp "${BB_FOUND}" "${BUSYBOX_BIN}"
    else
        log "initramfs: scarico busybox statico (x86_64)..."
        if command -v curl >/dev/null 2>&1; then
            curl -fsSL -o "${BUSYBOX_BIN}" "${BUSYBOX_URL_X86_64}" || \
            curl -fsSL -o "${BUSYBOX_BIN}" "${BUSYBOX_URL}" || true
        elif command -v wget >/dev/null 2>&1; then
            wget -q -O "${BUSYBOX_BIN}" "${BUSYBOX_URL_X86_64}" || true
        fi
    fi

    if [ -f "${BUSYBOX_BIN}" ] && [ -s "${BUSYBOX_BIN}" ]; then
        chmod +x "${BUSYBOX_BIN}"
        # Crea i symlink essenziali per il boot
        for applet in sh mount mkdir sleep umount pivot_root echo cat ls date ln ps; do
            ln -sf /bin/busybox "${WORK}/bin/${applet}" 2>/dev/null || true
        done
        # busybox mksh per init
        ln -sf /bin/busybox "${WORK}/bin/mksh" 2>/dev/null || true
        log "initramfs: busybox installato + $(ls "${WORK}/bin/" | wc -l) applet"
    else
        log "initramfs: WARN busybox non disponibile — init richiede sh, mount, etc."
        [ -f "${BUSYBOX_BIN}" ] && rm -f "${BUSYBOX_BIN}" || true
        # Fallback: copia direttamente da Alpine rootfs
        if [ -d "${ROOTFS}/bin" ]; then
            log "initramfs: tentativo fallback copia da Alpine rootfs"
            for cmd in sh mount mkdir sleep umount pivot_root echo cat ls; do
                SRC="$(find "${ROOTFS}" -name "${cmd}" -type f 2>/dev/null | head -1)"
                if [ -n "${SRC}" ]; then
                    cp "${SRC}" "${WORK}/bin/${cmd}" 2>/dev/null || true
                fi
            done
            chmod +x "${WORK}/bin/"* 2>/dev/null || true
        fi
    fi

    # Copia anche qualche utility extra da Alpine rootfs
    if [ -d "${ROOTFS}/lib" ]; then
        # Copia solo libc e loader dinamico se busybox non è statico
        for lib in ld-musl-x86_64.so.1 libc.musl-x86_64.so.1 libuClibc-*.so.*; do
            find "${ROOTFS}/lib" -name "${lib}" -exec cp {} "${WORK}/lib/" \; 2>/dev/null || true
        done
    fi

    cd "${WORK}"
    find . | cpio -o -H newc 2>/dev/null | gzip -9 > "${INITRAMFS}"
    cd - >/dev/null
    log "initramfs: ${INITRAMFS} ($(du -h "${INITRAMFS}" | cut -f1))"
    log "initramfs: contenuto: $(cpio -t < <(gunzip -c "${INITRAMFS}") 2>/dev/null | wc -l) file"
    rm -rf "${WORK}"
fi

# ------------------------------------------------------------------ #
# 4. ISO
# ------------------------------------------------------------------ #

log "=== 4/4 Pack ISO ==="
"${HERE}/pack-iso.sh"

log "Build completata. Artefatti in ${OUT}/"
ls -la "${OUT}/" | tee -a "${LOG}"
