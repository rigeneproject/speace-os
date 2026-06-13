#!/bin/sh
# build.sh - build completa della distro SPEACE OS.
# Produce in out/:
#   - kernel/bzImage
#   - rootfs/        (directory pronta per chroot o per impacchettamento)
#   - rootfs.tar.gz  (rootfs compresso per boot initramfs)
#   - initramfs.cpio.gz
#   - speace-os-0.1.0-cos.iso
#   - speace-os-0.1.0-cos.qcow2
#
# Dipendenze: gcc, make, xorriso, grub, cpio, gzip, rsync, curl, mtools, dosfstools
# Opzionali: apk (per installare python nel rootfs)

set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${HERE}/.." && pwd)"
OUT="${ROOT}/out"
LOG="${OUT}/build.log"
NPROC="$(nproc 2>/dev/null || echo 4)"

mkdir -p "${OUT}"

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "${LOG}"; }
fail() { log "FATAL: $*" >&2; exit 1; }
require() { command -v "$1" >/dev/null 2>&1 || fail "comando mancante: $1"; }

# ------------------------------------------------------------------ #
# 1. Kernel
# ------------------------------------------------------------------ #
log "=== 1/4 Build kernel ==="
if [ ! -f "${OUT}/kernel/bzImage" ]; then
    log "build kernel (nproc=${NPROC})"
    "${ROOT}/kernel/build-kernel.sh" 2>&1 | tee -a "${LOG}"
else
    log "kernel già presente, skip"
fi

# ------------------------------------------------------------------ #
# 2. Rootfs (costruito in /tmp per velocità, poi copiato in out/)
# ------------------------------------------------------------------ #
log "=== 2/4 Build rootfs (Alpine 3.20 base + overlay SPEACE) ==="
ROOTFS="${OUT}/rootfs"
WORKROOTFS="/tmp/speace-rootfs"   # FS veloce nativo, evita /mnt/c lentissimo
FORCE="${FORCE_ROOTFS:-0}"

NEED_REBUILD=0
if [ "${FORCE}" = "1" ]; then NEED_REBUILD=1; log "FORCE_ROOTFS=1, ricostruisco"; fi
if [ ! -d "${ROOTFS}/bin" ]; then NEED_REBUILD=1; log "manca ${ROOTFS}/bin, ricostruisco"; fi
if [ ! -f "${ROOTFS}/etc/speace/coordinator.yaml" ]; then NEED_REBUILD=1; log "manca marker overlay, ricostruisco"; fi

if [ "${NEED_REBUILD}" = "1" ]; then
    rm -rf "${WORKROOTFS}" "${ROOTFS}"
    mkdir -p "${WORKROOTFS}"

    ALPINE_VERSION=3.20
    ALPINE_ROOT="alpine-minirootfs-${ALPINE_VERSION}.3-x86_64"
    ALPINE_TAR="${OUT}/${ALPINE_ROOT}.tar.gz"

    if [ ! -f "${ALPINE_TAR}" ]; then
        log "scarico Alpine ${ALPINE_VERSION} rootfs in ${OUT}"
        if command -v curl >/dev/null 2>&1; then
            curl -fsSL -o "${ALPINE_TAR}" \
                "https://dl-cdn.alpinelinux.org/alpine/v${ALPINE_VERSION}/releases/x86_64/${ALPINE_ROOT}.tar.gz"
        else
            wget -q -O "${ALPINE_TAR}" \
                "https://dl-cdn.alpinelinux.org/alpine/v${ALPINE_VERSION}/releases/x86_64/${ALPINE_ROOT}.tar.gz"
        fi
    fi

    log "estraggo Alpine rootfs in ${WORKROOTFS}"
    tar -xzf "${ALPINE_TAR}" -C "${WORKROOTFS}"

    log "applico overlay rootfs/ di SPEACE OS"
    cp -a "${ROOT}/rootfs/." "${WORKROOTFS}/"

    # Copia di cellular_speace (snapshot)
    if [ ! -d "${WORKROOTFS}/opt/speace/cellular_speace/speace_core" ]; then
        log "copio cellular_speace/ in /opt/speace"
        SRC="$(cd "${ROOT}/../cellular_speace" && pwd)"
        mkdir -p "${WORKROOTFS}/opt/speace"
        rsync -a --exclude='__pycache__' --exclude='.pytest_cache' --exclude='.ruff_cache' \
                 --exclude='.opencode' --exclude='.coverage' --exclude='cov.json' \
                 --exclude='*.pyc' --exclude='*.pdf' --exclude='_temp_*.txt' \
                 "${SRC}/" "${WORKROOTFS}/opt/speace/cellular_speace/"
    fi

    # Copia di os_coordinator (modulo nuovo)
    if [ ! -d "${WORKROOTFS}/usr/lib/python3.12/site-packages/os_coordinator" ] && \
       [ ! -d "${WORKROOTFS}/usr/lib/python3.13/site-packages/os_coordinator" ]; then
        log "installo os_coordinator module in site-packages"
        SITE_PKGS="$(find "${WORKROOTFS}/usr/lib" -type d -name 'site-packages' | head -1)"
        if [ -n "${SITE_PKGS}" ]; then
            mkdir -p "${SITE_PKGS}/os_coordinator"
            cp -a "${ROOT}/os_coordinator/src/os_coordinator/." "${SITE_PKGS}/os_coordinator/"
        else
            log "site-packages non trovato, installo in /opt/speace"
            mkdir -p "${WORKROOTFS}/opt/speace/os_coordinator"
            cp -a "${ROOT}/os_coordinator/src/os_coordinator/." "${WORKROOTFS}/opt/speace/os_coordinator/"
            mkdir -p "${WORKROOTFS}/etc/profile.d"
            echo 'export PYTHONPATH="${PYTHONPATH:-}:/opt/speace"' \
                > "${WORKROOTFS}/etc/profile.d/speace-pythonpath.sh"
            chmod +x "${WORKROOTFS}/etc/profile.d/speace-pythonpath.sh"
        fi
    fi

    # Wrapper /sbin/os_coordinator
    if [ -f "${ROOT}/initramfs/sbin/os_coordinator" ]; then
        mkdir -p "${WORKROOTFS}/sbin"
        cp -f "${ROOT}/initramfs/sbin/os_coordinator" "${WORKROOTFS}/sbin/os_coordinator"
        chmod +x "${WORKROOTFS}/sbin/os_coordinator"
        log "installo /sbin/os_coordinator (wrapper PID 1) nel rootfs"
    fi

    log "creo utente speace e directory di stato"
    mkdir -p "${WORKROOTFS}/var/log/speace" \
             "${WORKROOTFS}/var/lib/speace" \
    # /var/run è spesso un symlink a /run: usa install -d o ignora errore
    mkdir -p "${WORKROOTFS}/run/speace" 2>/dev/null || install -d "${WORKROOTFS}/run/speace" 2>/dev/null || true
    mkdir -p "${WORKROOTFS}/var/run/speace" 2>/dev/null || true
    chmod 1777 "${WORKROOTFS}/var/run" "${WORKROOTFS}/run" 2>/dev/null || true

    # Installa Python3 in Alpine
    log "installo python3 nel rootfs Alpine (se apk disponibile)"
    if [ -x "${WORKROOTFS}/sbin/apk" ] || [ -x "${WORKROOTFS}/usr/bin/apk" ]; then
        APK="$(find "${WORKROOTFS}" -name 'apk' -executable -type f | head -1)"
        if [ -n "${APK}" ]; then
            mkdir -p "${WORKROOTFS}/etc"
            echo "nameserver 1.1.1.1" > "${WORKROOTFS}/etc/resolv.conf"
            # chroot richiede root - proviamo, ma non blocchiamo se fallisce
            if command -v chroot >/dev/null 2>&1 && [ "$(id -u)" = "0" ]; then
                chroot "${WORKROOTFS}" "$(basename "${APK}")" update 2>&1 | tee -a "${LOG}" || true
                chroot "${WORKROOTFS}" "$(basename "${APK}")" add --no-cache \
                    python3 py3-pip py3-virtualenv busybox 2>&1 | tee -a "${LOG}" || \
                    log "(warn) apk add python3 fallita in chroot, continuo senza"
            else
                log "(warn) chroot non disponibile (no root o mancante), python3 non installato"
            fi
        fi
    else
        log "(warn) apk non trovato in Alpine rootfs, installazione python3 saltata"
    fi

    # Crea venv se python3 disponibile
    PYBIN="$(find "${WORKROOTFS}/usr/bin" -name 'python3*' -executable -type f 2>/dev/null | head -1)"
    if [ -n "${PYBIN}" ] && command -v chroot >/dev/null 2>&1 && [ "$(id -u)" = "0" ]; then
        log "creo venv Python e installo dipendenze"
        chroot "${WORKROOTFS}" /usr/bin/python3 -m venv /opt/speace/.venv 2>/dev/null || true
        chroot "${WORKROOTFS}" /opt/speace/.venv/bin/pip install --quiet --no-cache-dir \
            pydantic pyyaml structlog httpx fastapi uvicorn websockets 2>&1 | tee -a "${LOG}" || \
            log "(warn) pip install fallita, continuo senza venv"
    fi

    # Copia il rootfs finale in out (preserva permessi; tar -C per essere cross-FS)
    log "copio rootfs finale in ${ROOTFS}"
    mkdir -p "${ROOTFS}"
    # Usa tar piped copy per evitare problemi di permessi su /mnt/c
    (cd "${WORKROOTFS}" && tar -cf - .) | (cd "${ROOTFS}" && tar -xf -)
    log "rootfs finale: $(find "${ROOTFS}" -type f | wc -l) file"
else
    log "rootfs già presente, skip"
fi

# ------------------------------------------------------------------ #
# 3. Initramfs
# ------------------------------------------------------------------ #
log "=== 3/4 Build initramfs ==="
INITRAMFS="${OUT}/initramfs.cpio.gz"
if [ ! -f "${INITRAMFS}" ]; then
    WORK="/tmp/speace-initramfs"
    rm -rf "${WORK}"
    mkdir -p "${WORK}"
    cp -a "${ROOT}/initramfs/." "${WORK}/"

    if [ -f "${WORK}/sbin/os_coordinator" ]; then
        chmod +x "${WORK}/sbin/os_coordinator"
        log "initramfs: wrapper /sbin/os_coordinator reso eseguibile"
    else
        log "initramfs: WARN wrapper sbin/os_coordinator non presente"
    fi

    # Modulo os_coordinator
    mkdir -p "${WORK}/opt/os_coordinator"
    cp -a "${ROOT}/os_coordinator/src/os_coordinator/." "${WORK}/opt/os_coordinator/"

    # busybox per initramfs
    BUSYBOX_BIN="${WORK}/bin/busybox"
    BB_FOUND=""
    if [ -d "${ROOTFS}/bin" ]; then
        BB_FOUND="$(find "${ROOTFS}/bin" -name 'busybox' -type f | head -1)"
    fi
    if [ -z "${BB_FOUND}" ] && [ -d "${ROOTFS}/usr/bin" ]; then
        BB_FOUND="$(find "${ROOTFS}/usr/bin" -name 'busybox' -type f | head -1)"
    fi
    if [ -n "${BB_FOUND}" ]; then
        log "initramfs: busybox copiato da Alpine rootfs"
        mkdir -p "${WORK}/bin" "${WORK}/usr/bin" "${WORK}/sbin" "${WORK}/usr/sbin"
        cp "${BB_FOUND}" "${BUSYBOX_BIN}"
    fi
    if [ -f "${BUSYBOX_BIN}" ] && [ -s "${BUSYBOX_BIN}" ]; then
        chmod +x "${BUSYBOX_BIN}"
        for applet in sh mount mkdir sleep umount pivot_root echo cat ls date ln ps; do
            ln -sf /bin/busybox "${WORK}/bin/${applet}" 2>/dev/null || true
        done
        ln -sf /bin/busybox "${WORK}/bin/mksh" 2>/dev/null || true
        log "initramfs: busybox installato + applet"
    else
        log "initramfs: WARN busybox non disponibile"
    fi

    # libc musl per compatibilità binari
    if [ -d "${ROOTFS}/lib" ]; then
        mkdir -p "${WORK}/lib"
        for lib in ld-musl-x86_64.so.1 libc.musl-x86_64.so.1; do
            find "${ROOTFS}/lib" -name "${lib}" -exec cp {} "${WORK}/lib/" \; 2>/dev/null || true
        done
    fi

    cd "${WORK}"
    find . | cpio -o -H newc 2>/dev/null | gzip -9 > "${INITRAMFS}"
    cd - >/dev/null
    log "initramfs: ${INITRAMFS} ($(du -h "${INITRAMFS}" | cut -f1))"
    log "initramfs: contenuto: $(gunzip -c "${INITRAMFS}" | cpio -t 2>/dev/null | wc -l) file"
    rm -rf "${WORK}"
else
    log "initramfs già presente, skip"
fi

# ------------------------------------------------------------------ #
# 4. ISO + IMG
# ------------------------------------------------------------------ #
log "=== 4/4 Pack ISO + IMG ==="
"${HERE}/pack-iso.sh" 2>&1 | tee -a "${LOG}" || log "(warn) pack-iso.sh ha restituito errore"
"${HERE}/pack-usb-img.sh" 2>&1 | tee -a "${LOG}" || log "(warn) pack-usb-img.sh ha restituito errore"

log "Build completata. Artefatti in ${OUT}/"
ls -la "${OUT}/" | tee -a "${LOG}"
