#!/bin/bash
# docker-build.sh - Build completa di SPEACE OS in container Linux nativo.
# Risolve: permessi Unix, chroot per apk/python, GRUB UEFI+BIOS, loop devices.
#
# Uso:
#   docker build -t speace-os-build .
#   docker run --rm -v "$(pwd)/out:/build/out" speace-os-build
#
# Oppure (se out/ non esiste ancora):
#   docker run --rm -v "$(pwd):/build" speace-os-build

set -eu

ROOT="/build"
OUT="${ROOT}/out"
LOG="${OUT}/build-docker.log"

mkdir -p "${OUT}"

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "${LOG}"; }
fail() { log "FATAL: $*" >&2; exit 1; }

log "========================================="
log " SPEACE OS - Docker Build"
log "========================================="

# ------------------------------------------------------------------ #
# 0. Verifica prerequisiti container
# ------------------------------------------------------------------ #
log "verifico prerequisiti container..."
for cmd in gcc make xorriso grub-mkrescue mtools mkfs.fat mkfs.ext4 parted cpio gzip curl python3; do
    command -v "$cmd" >/dev/null 2>&1 || fail "comando mancante nel container: $cmd"
done
log "prerequisiti OK"

# ------------------------------------------------------------------ #
# 1. Kernel
# ------------------------------------------------------------------ #
log "=== 1/5 Build kernel ==="
if [ ! -f "${OUT}/kernel/bzImage" ]; then
    "${ROOT}/kernel/build-kernel.sh" 2>&1 | tee -a "${LOG}"
else
    log "kernel già presente, skip"
fi

[ -f "${OUT}/kernel/bzImage" ] || fail "bzImage non trovato dopo la build"

# ------------------------------------------------------------------ #
# 2. Rootfs (Alpine 3.20 base + overlay SPEACE + Python3)
# ------------------------------------------------------------------ #
log "=== 2/5 Build rootfs (Alpine 3.20 + Python3 + overlay SPEACE) ==="
ROOTFS="${OUT}/rootfs"
WORKROOTFS="/tmp/speace-rootfs"
FORCE="${FORCE_ROOTFS:-1}"

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
        log "scarico Alpine ${ALPINE_VERSION} rootfs"
        curl -fsSL -o "${ALPINE_TAR}" \
            "https://dl-cdn.alpinelinux.org/alpine/v${ALPINE_VERSION}/releases/x86_64/${ALPINE_ROOT}.tar.gz"
    fi

    log "estraggo Alpine rootfs in ${WORKROOTFS}"
    tar -xzf "${ALPINE_TAR}" -C "${WORKROOTFS}"

    log "applico overlay rootfs/ di SPEACE OS"
    cp -a "${ROOT}/rootfs/." "${WORKROOTFS}/"

    # Copia di cellular_speace (se presente)
    if [ -d "${ROOT}/../cellular_speace/speace_core" ]; then
        log "copio cellular_speace/ in /opt/speace"
        mkdir -p "${WORKROOTFS}/opt/speace"
        rsync -a --exclude='__pycache__' --exclude='.pytest_cache' --exclude='.ruff_cache' \
                 --exclude='.opencode' --exclude='.coverage' --exclude='cov.json' \
                 --exclude='*.pyc' --exclude='*.pdf' --exclude='_temp_*.txt' \
                 "${ROOT}/../cellular_speace/" "${WORKROOTFS}/opt/speace/cellular_speace/" 2>/dev/null || true
    fi

    # --- Installa Python3 e dipendenze via apk in chroot ---
    log "installo python3 e dipendenze nel rootfs Alpine (chroot)"
    if [ -x "${WORKROOTFS}/sbin/apk" ] || [ -x "${WORKROOTFS}/usr/sbin/apk" ]; then
        # Configura DNS per apk in chroot
        mkdir -p "${WORKROOTFS}/etc"
        echo "nameserver 1.1.1.1" > "${WORKROOTFS}/etc/resolv.conf"
        echo "nameserver 8.8.8.8" >> "${WORKROOTFS}/etc/resolv.conf"

        # Copia musl libc necessaria per chroot
        CPREFIX="$(find "${WORKROOTFS}/lib" -name 'ld-musl-x86_64.so.1' | head -1)"
        if [ -n "${CPREFIX}" ]; then
            log "trovato musl in rootfs, provo chroot per apk"
            # Mount /proc e /dev per chroot
            mount -t proc none "${WORKROOTFS}/proc" 2>/dev/null || true
            mount --rbind /dev "${WORKROOTFS}/dev" 2>/dev/null || true
            mount --rbind /sys "${WORKROOTFS}/sys" 2>/dev/null || true

            chroot "${WORKROOTFS}" /sbin/apk update 2>&1 | tee -a "${LOG}" || log "(warn) apk update fallita"
            chroot "${WORKROOTFS}" /sbin/apk add --no-cache \
                python3 py3-pip busybox 2>&1 | tee -a "${LOG}" || log "(warn) apk add python3 fallita"

            # Verifica python3 installato
            if [ -x "${WORKROOTFS}/usr/bin/python3" ]; then
                log "python3 installato con successo nel rootfs"

                # Installa dipendenze Python nel rootfs
                log "installo dipendenze Python (pydantic, pyyaml, structlog, httpx)"
                chroot "${WORKROOTFS}" /usr/bin/python3 -m ensurepip 2>/dev/null || true
                chroot "${WORKROOTFS}" /usr/bin/pip3 install --no-cache-dir --break-system-packages \
                    pydantic pyyaml structlog httpx 2>&1 | tee -a "${LOG}" || \
                    log "(warn) pip install fallita, continuo senza"
            else
                log "(warn) python3 non installato dopo apk, fallback"
            fi

            umount -l "${WORKROOTFS}/dev" 2>/dev/null || true
            umount -l "${WORKROOTFS}/proc" 2>/dev/null || true
            umount -l "${WORKROOTFS}/sys" 2>/dev/null || true
        else
            log "(warn) ld-musl non trovato in rootfs, skip chroot"
        fi
    else
        log "(warn) apk non trovato in Alpine rootfs"
    fi

    # --- Fallback: copia python3 dall'host se non nel rootfs ---
    if [ ! -x "${WORKROOTFS}/usr/bin/python3" ]; then
        log "FALLBACK: copio python3 e librerie dall'host Debian nel rootfs"
        mkdir -p "${WORKROOTFS}/usr/bin"
        mkdir -p "${WORKROOTFS}/usr/lib"

        # Copia python3 binary
        CPYTHON="$(which python3 2>/dev/null || echo '')"
        if [ -n "${CPYTHON}" ] && [ -x "${CPYTHON}" ]; then
            cp -f "${CPYTHON}" "${WORKROOTFS}/usr/bin/python3"
            # Trova e copia le librerie shared necessarie
            ldd "${CPYTHON}" 2>/dev/null | grep -o '/[^ ]*' | while read -r lib; do
                if [ -f "${lib}" ]; then
                    # Determina la destinazione (lib o lib64)
                    destdir="${WORKROOTFS}$(dirname "${lib}")"
                    mkdir -p "${destdir}"
                    cp -f "${lib}" "${destdir}/"
                fi
            done 2>/dev/null || true

            # Copia moduli standard Python
            PYVER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
            SITEDIR="/usr/lib/python${PYVER}"
            if [ -d "${SITEDIR}" ]; then
                mkdir -p "${WORKROOTFS}${SITEDIR}"
                cp -a "${SITEDIR}/." "${WORKROOTFS}${SITEDIR}/"
            fi
            log "python3 copiato dall'host (versione ${PYVER})"
        else
            log "(warn) python3 non disponibile nemmeno sull'host"
        fi
    fi

    # Copia modulo os_coordinator
    log "installo os_coordinator module"
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

    # Wrapper /sbin/os_coordinator
    if [ -f "${ROOT}/initramfs/sbin/os_coordinator" ]; then
        mkdir -p "${WORKROOTFS}/sbin"
        cp -f "${ROOT}/initramfs/sbin/os_coordinator" "${WORKROOTFS}/sbin/os_coordinator"
        chmod +x "${WORKROOTFS}/sbin/os_coordinator"
        log "installo /sbin/os_coordinator (wrapper PID 1) nel rootfs"
    fi

    # Utente e directory di stato
    log "creo utente speace e directory di stato"
    mkdir -p "${WORKROOTFS}/var/log/speace" \
             "${WORKROOTFS}/var/lib/speace" \
             "${WORKROOTFS}/run/speace" \
             "${WORKROOTFS}/var/run/speace"
    chmod 1777 "${WORKROOTFS}/var/run" "${WORKROOTFS}/run" 2>/dev/null || true

    # Copia rootfs finale in out/
    log "copio rootfs finale in ${ROOTFS}"
    mkdir -p "${ROOTFS}"
    (cd "${WORKROOTFS}" && tar -cf - .) | (cd "${ROOTFS}" && tar -xf -)
    log "rootfs finale: $(find "${ROOTFS}" -type f | wc -l) file"
    log "python3 nel rootfs: $([ -x "${ROOTFS}/usr/bin/python3" ] && echo 'SI' || echo 'NO')"
    log "os_coordinator nel rootfs: $([ -x "${ROOTFS}/sbin/os_coordinator" ] && echo 'SI' || echo 'NO')"
else
    log "rootfs già presente, skip"
fi

# ------------------------------------------------------------------ #
# 3. Initramfs
# ------------------------------------------------------------------ #
log "=== 3/5 Build initramfs ==="
INITRAMFS="${OUT}/initramfs.cpio.gz"
WORK="/tmp/speace-initramfs"
rm -rf "${WORK}"
mkdir -p "${WORK}"
cp -a "${ROOT}/initramfs/." "${WORK}/"

if [ -f "${WORK}/sbin/os_coordinator" ]; then
    chmod +x "${WORK}/sbin/os_coordinator"
    log "initramfs: wrapper /sbin/os_coordinator reso eseguibile"
fi

mkdir -p "${WORK}/opt/os_coordinator"
cp -a "${ROOT}/os_coordinator/src/os_coordinator/." "${WORK}/opt/os_coordinator/"

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
fi

# libc musl
if [ -d "${ROOTFS}/lib" ]; then
    mkdir -p "${WORK}/lib"
    for lib in ld-musl-x86_64.so.1 libc.musl-x86_64.so.1; do
        find "${ROOTFS}/lib" -name "${lib}" -exec cp {} "${WORK}/lib/" \; 2>/dev/null || true
    done
fi

cd "${WORK}"
find . | cpio -o -H newc 2>/dev/null | gzip -9 > "${INITRAMFS}"
cd "${ROOT}"
log "initramfs: ${INITRAMFS} ($(du -h "${INITRAMFS}" | cut -f1))"
log "initramfs: contenuto: $(gunzip -c "${INITRAMFS}" | cpio -t 2>/dev/null | wc -l) file"

# ------------------------------------------------------------------ #
# 4. ISO (grub-mkrescue - BIOS+UEFI)
# ------------------------------------------------------------------ #
log "=== 4/5 Pack ISO (grub-mkrescue BIOS+UEFI) ==="
ISO="${OUT}/speace-os-$(cat "${ROOT}/VERSION").iso"
ISO_WORK="${OUT}/iso-build"
GRUB_RESCUE_ISO="${OUT}/grub-rescue.iso"

rm -rf "${ISO_WORK}" "${GRUB_RESCUE_ISO}"
mkdir -p "${ISO_WORK}/boot/grub" "${ISO_WORK}/EFI/BOOT" "${ISO_WORK}/speace"

# grub.cfg
cat > "${ISO_WORK}/boot/grub/grub.cfg" <<'EOF'
set timeout=3
set default=0

menuentry "SPEACE OS - Cognitive Operating System" {
    linux /boot/bzImage ro quiet loglevel=3 speace.stage=os-0.1
    initrd /boot/initramfs.cpio.gz
}

menuentry "SPEACE OS (safe mode - no AI coordinator)" {
    linux /boot/bzImage ro quiet loglevel=3 speace.coordinator=off
    initrd /boot/initramfs.cpio.gz
}

menuentry "SPEACE OS (verbose boot)" {
    linux /boot/bzImage ro loglevel=7
    initrd /boot/initramfs.cpio.gz
}
EOF

# Copia payload
log "copio bzImage, initramfs, rootfs"
cp -f "${OUT}/kernel/bzImage" "${ISO_WORK}/boot/bzImage"
cp -f "${OUT}/initramfs.cpio.gz" "${ISO_WORK}/boot/initramfs.cpio.gz"

if [ -d "${OUT}/rootfs" ] && [ -f "${OUT}/rootfs/etc/speace/coordinator.yaml" ]; then
    log "creo speace/rootfs.tar.gz (rootfs overlay presente)"
    tar -czf "${ISO_WORK}/speace/rootfs.tar.gz" -C "${OUT}" rootfs
else
    log "(warn) rootfs non pronto: coordinator.yaml mancante"
    : > "${ISO_WORK}/speace/.gitkeep"
fi

# grub-mkrescue (BIOS+UEFI)
log "eseguo grub-mkrescue"
if ! grub-mkrescue -o "${GRUB_RESCUE_ISO}" "${ISO_WORK}" 2>&1 | tee -a "${LOG}"; then
    fail "grub-mkrescue fallita"
fi

if [ ! -s "${GRUB_RESCUE_ISO}" ]; then
    fail "ISO vuota (grub-mkrescue non ha prodotto output)"
fi

rm -f "${ISO}"
mv "${GRUB_RESCUE_ISO}" "${ISO}"
rm -rf "${ISO_WORK}"

ISO_SIZE="$(du -h "${ISO}" | cut -f1)"
log "ISO scritto: ${ISO} (${ISO_SIZE})"
log "=== report El Torito ==="
xorriso -indev "${ISO}" -report_el_torito plain 2>&1 | tee -a "${LOG}" | head -20 || true

# ------------------------------------------------------------------ #
# 5. IMG (USB disk image - BIOS+UEFI)
# ------------------------------------------------------------------ #
log "=== 5/5 Pack IMG (USB disk image) ==="
IMG="${OUT}/speace-os-$(cat "${ROOT}/VERSION").img"
IMG_WORK="/tmp/speace-usb-img"
rm -rf "${IMG_WORK}"
mkdir -p "${IMG_WORK}"

IMG_TMP="${IMG_WORK}/disk.img"
ESP_TMP="${IMG_WORK}/esp.img"
ROOTFS_TMP="${IMG_WORK}/rootfs.img"
ROOTFS_MNT="${IMG_WORK}/rootfs_mnt"
mkdir -p "${ROOTFS_MNT}"

MIBSIZE=$((1024 * 1024))
SECSIZE=512
SECPERMB=$((MIBSIZE / SECSIZE))
BIOS_MB=1
EFI_MB=64
ROOTFS_MB=500
IMG_MB=$((2 + BIOS_MB + EFI_MB + ROOTFS_MB))

log "creo disco raw ${IMG_TMP} (${IMG_MB} MB)"
truncate -s "${IMG_MB}M" "${IMG_TMP}"

log "creo tabella GPT con parted (allineamento 1 MiB)"
parted -s -a optimal "${IMG_TMP}" mklabel gpt
parted -s -a optimal "${IMG_TMP}" mkpart BIOS_BOOT 1MiB $((1 + BIOS_MB))MiB
parted -s "${IMG_TMP}" set 1 bios_grub on
parted -s -a optimal "${IMG_TMP}" mkpart ESP fat32 $((1 + BIOS_MB))MiB $((1 + BIOS_MB + EFI_MB))MiB
parted -s "${IMG_TMP}" set 2 esp on
parted -s -a optimal "${IMG_TMP}" mkpart ROOTFS ext4 $((1 + BIOS_MB + EFI_MB))MiB $((1 + BIOS_MB + EFI_MB + ROOTFS_MB))MiB

EFI_START_MIB=$((1 + BIOS_MB))
ROOTFS_START_MIB=$((1 + BIOS_MB + EFI_MB))
EFI_SECTORS=$((EFI_MB * SECPERMB))
ROOTFS_SECTORS=$((ROOTFS_MB * SECPERMB))

log "estraggo partizioni come file in ${IMG_WORK}"
dd if="${IMG_TMP}" of="${ESP_TMP}" bs=512 skip=$((EFI_START_MIB * SECPERMB)) count=${EFI_SECTORS} status=none
dd if="${IMG_TMP}" of="${ROOTFS_TMP}" bs=512 skip=$((ROOTFS_START_MIB * SECPERMB)) count=${ROOTFS_SECTORS} status=none

# ---- ESP FAT32 ----
log "formato ESP FAT32 (${EFI_MB}MB)"
mkfs.fat -F32 -n SPEACE_EFI "${ESP_TMP}" >/dev/null

GRUB_TMP="${IMG_WORK}/grub_esp"
rm -rf "${GRUB_TMP}"
mkdir -p "${GRUB_TMP}/boot/grub" "${GRUB_TMP}/EFI/BOOT" "${GRUB_TMP}/speace"

cat > "${GRUB_TMP}/boot/grub/grub.cfg" <<'GRUBEOF'
set timeout=3
set default=0

menuentry "SPEACE OS - Cognitive Operating System" {
    search --label --set=root SPEACE_EFI
    linux /boot/bzImage root=LABEL=SPEACE_ROOT ro quiet loglevel=3 speace.stage=os-0.1
    initrd /boot/initramfs.cpio.gz
}

menuentry "SPEACE OS (safe mode - no AI coordinator)" {
    search --label --set=root SPEACE_EFI
    linux /boot/bzImage root=LABEL=SPEACE_ROOT ro quiet loglevel=3 speace.coordinator=off
    initrd /boot/initramfs.cpio.gz
}

menuentry "SPEACE OS (verbose boot)" {
    search --label --set=root SPEACE_EFI
    linux /boot/bzImage root=LABEL=SPEACE_ROOT ro loglevel=7
    initrd /boot/initramfs.cpio.gz
}
GRUBEOF

cp "${OUT}/kernel/bzImage" "${GRUB_TMP}/boot/bzImage"
cp "${OUT}/initramfs.cpio.gz" "${GRUB_TMP}/boot/initramfs.cpio.gz"

# UEFI boot loader
if [ -f /usr/lib/grub/x86_64-efi-signed/grubx64.efi.signed ]; then
    cp /usr/lib/grub/x86_64-efi-signed/grubx64.efi.signed "${GRUB_TMP}/EFI/BOOT/BOOTX64.EFI"
elif [ -f /usr/lib/grub/x86_64-efi/bootx64.efi ]; then
    cp /usr/lib/grub/x86_64-efi/bootx64.efi "${GRUB_TMP}/EFI/BOOT/BOOTX64.EFI"
fi

[ -f "${OUT}/rootfs.tar.gz" ] && cp "${OUT}/rootfs.tar.gz" "${GRUB_TMP}/speace/rootfs.tar.gz"

log "popolo ESP con mtools"
mcopy -i "${ESP_TMP}" -s -Q -p "${GRUB_TMP}"/* ::/
rm -rf "${GRUB_TMP}"

# ---- ROOTFS ext4 ----
log "formato ROOTFS ext4 (${ROOTFS_MB}MB)"
mkfs.ext4 -L SPEACE_ROOT -F "${ROOTFS_TMP}" >/dev/null

ROOTFS_OVERLAY="${IMG_WORK}/overlay"
rm -rf "${ROOTFS_OVERLAY}"
mkdir -p "${ROOTFS_OVERLAY}"
log "copio rootfs overlay in ${ROOTFS_OVERLAY}"
(cd "${OUT}/rootfs" && tar -cf - .) | (cd "${ROOTFS_OVERLAY}" && tar -xf -)
log "overlay copiato: $(find "${ROOTFS_OVERLAY}" -type f | wc -l) file"

ROOTFS_POPULATED=0
log "monto rootfs per copia overlay (mount -o loop)"
if mount -o loop "${ROOTFS_TMP}" "${ROOTFS_MNT}" 2>/dev/null; then
    log "rootfs montato, copio overlay"
    rm -rf "${ROOTFS_MNT:?}/"*
    cp -a "${ROOTFS_OVERLAY}/." "${ROOTFS_MNT}/"
    ROOTFS_POPULATED=1
    log "overlay copiato in rootfs_mnt"
    sync
    umount "${ROOTFS_MNT}"
else
    log "(warn) mount -o loop fallito, provo con debugfs/e2cp"
    # Fallback: debugfs per copiare file singoli (limitato)
    if command -v debugfs >/dev/null 2>&1; then
        log "uso debugfs per copiare file critici nel rootfs"
        # Copia solo i file essenziali per il boot
        for f in sbin/os_coordinator etc/speace/coordinator.yaml etc/speace/env.conf; do
            src="${ROOTFS_OVERLAY}/${f}"
            if [ -f "${src}" ]; then
                destdir="$(dirname "${f}")"
                debugfs -w -R "mkdir ${destdir}" "${ROOTFS_TMP}" 2>/dev/null || true
                debugfs -w -R "write ${src} ${f}" "${ROOTFS_TMP}" 2>/dev/null || true
            fi
        done
    fi
fi

if [ "${ROOTFS_POPULATED}" = "0" ]; then
    log "WARN: rootfs non completamente popolato. Proseguo comunque."
fi

# Riscrivi partizioni
log "aggiorno partizioni nell'immagine"
dd if="${ESP_TMP}" of="${IMG_TMP}" bs=512 seek=$((EFI_START_MIB * SECPERMB)) count=${EFI_SECTORS} conv=notrunc status=none
dd if="${ROOTFS_TMP}" of="${IMG_TMP}" bs=512 seek=$((ROOTFS_START_MIB * SECPERMB)) count=${ROOTFS_SECTORS} conv=notrunc status=none

# ---- GRUB BIOS nel MBR ----
log "installo GRUB i386-pc nell'MBR"
GRUB_BIOS_OK=0
if command -v grub-install >/dev/null 2>&1; then
    # Crea un device map per l'immagine
    GRUB_BOOT="${IMG_WORK}/grub-bios-boot"
    rm -rf "${GRUB_BOOT}"
    mkdir -p "${GRUB_BOOT}"

    # Setup loop device
    LOOP_DEV=""
    if command -v losetup >/dev/null 2>&1; then
        LOOP_DEV="$(losetup --find --show --partscan "${IMG_TMP}" 2>/dev/null || true)"
        if [ -n "${LOOP_DEV}" ]; then
            log "loop device: ${LOOP_DEV}"
            # Attendi che le partizioni appaiano
            sleep 2
            partprobe "${LOOP_DEV}" 2>/dev/null || true
            udevadm settle 2>/dev/null || true
        fi
    fi

    if [ -n "${LOOP_DEV}" ]; then
        # Trova la partizione ESP (la seconda)
        ESP_PART="${LOOP_DEV}p2"
        ROOTFS_PART="${LOOP_DEV}p3"

        # Formatta e monta ESP nel loop device
        mkfs.fat -F32 -n SPEACE_EFI "${ESP_PART}" 2>/dev/null || true
        mkdir -p "${IMG_WORK}/esp_mnt"
        if mount "${ESP_PART}" "${IMG_WORK}/esp_mnt" 2>/dev/null; then
            # Copia i file GRUB nella ESP montata
            GRUB_TMP2="${IMG_WORK}/grub_esp2"
            mkdir -p "${GRUB_TMP2}/boot/grub" "${GRUB_TMP2}/EFI/BOOT"
            cat > "${GRUB_TMP2}/boot/grub/grub.cfg" <<'GRUBCFG'
set timeout=3
set default=0

menuentry "SPEACE OS - Cognitive Operating System" {
    search --label --set=root SPEACE_EFI
    linux /boot/bzImage root=LABEL=SPEACE_ROOT ro quiet loglevel=3 speace.stage=os-0.1
    initrd /boot/initramfs.cpio.gz
}

menuentry "SPEACE OS (safe mode - no AI coordinator)" {
    search --label --set=root SPEACE_EFI
    linux /boot/bzImage root=LABEL=SPEACE_ROOT ro quiet loglevel=3 speace.coordinator=off
    initrd /boot/initramfs.cpio.gz
}

menuentry "SPEACE OS (verbose boot)" {
    search --label --set=root SPEACE_EFI
    linux /boot/bzImage root=LABEL=SPEACE_ROOT ro loglevel=7
    initrd /boot/initramfs.cpio.gz
}
GRUBCFG
            cp "${OUT}/kernel/bzImage" "${GRUB_TMP2}/boot/bzImage"
            cp "${OUT}/initramfs.cpio.gz" "${GRUB_TMP2}/boot/initramfs.cpio.gz"
            cp -a "${GRUB_TMP2}/." "${IMG_WORK}/esp_mnt/"
            umount "${IMG_WORK}/esp_mnt"
        fi

        # Formatta e monta rootfs nel loop device
        mkfs.ext4 -L SPEACE_ROOT "${ROOTFS_PART}" 2>/dev/null || true
        mkdir -p "${IMG_WORK}/rootfs_mnt2"
        if mount "${ROOTFS_PART}" "${IMG_WORK}/rootfs_mnt2" 2>/dev/null; then
            cp -a "${ROOTFS_OVERLAY}/." "${IMG_WORK}/rootfs_mnt2/"
            ROOTFS_POPULATED=1
            log "rootfs popolato via loop device"
            sync
            umount "${IMG_WORK}/rootfs_mnt2"
        fi

        # Installa GRUB nel MBR del loop device
        if grub-install --target=i386-pc \
            --boot-directory="${GRUB_BOOT}" \
            --modules="ext2 fat part_msdos part_gpt biosdisk" \
            --install-modules="ext2 fat part_msdos part_gpt biosdisk linux acpi normal ls echo test sleep configfile" \
            "${LOOP_DEV}" 2>&1 | tee -a "${LOG}"; then
            GRUB_BIOS_OK=1
            log "GRUB BIOS installato in MBR (grub-install su loop device)"
        else
            log "(warn) grub-install su loop device fallita"
        fi

        # Cleanup loop device
        losetup -d "${LOOP_DEV}" 2>/dev/null || true
    else
        log "(warn) losetup non disponibile, provo grub-install diretto"
        if grub-install --target=i386-pc \
            --boot-directory="${GRUB_BOOT}" \
            --modules="ext2 fat part_msdos part_gpt biosdisk" \
            --install-modules="ext2 fat part_msdos part_gpt biosdisk linux acpi normal ls echo test sleep configfile" \
            "${IMG_TMP}" 2>&1 | tee -a "${LOG}"; then
            GRUB_BIOS_OK=1
            log "GRUB BIOS installato in MBR (grub-install diretto)"
        fi
    fi
fi

if [ "${GRUB_BIOS_OK}" = "0" ]; then
    log "provo install manuale GRUB con grub-mkimage + dd..."
    if command -v grub-mkimage >/dev/null 2>&1; then
        GRUB_MODULES="ext2 fat part_msdos part_gpt biosdisk ls echo test sleep configfile linux normal acpi"
        CORE_IMG="${IMG_WORK}/core.img"
        if grub-mkimage -O i386-pc -o "${CORE_IMG}" ${GRUB_MODULES} 2>&1 | tee -a "${LOG}"; then
            CORE_IMG_SIZE=$(stat -c%s "${CORE_IMG}" 2>/dev/null || wc -c < "${CORE_IMG}")
            BIOS_PART_SIZE=$((BIOS_MB * MIBSIZE))
            if [ "${CORE_IMG_SIZE}" -le "${BIOS_PART_SIZE}" ]; then
                if [ -f /usr/lib/grub/i386-pc/boot.img ]; then
                    dd if=/usr/lib/grub/i386-pc/boot.img of="${IMG_TMP}" bs=440 count=1 conv=notrunc status=none 2>/dev/null && \
                    log "  GRUB stage1 (boot.img) scritto in MBR" || \
                    log "  (warn) boot.img non scritto"
                fi
                dd if="${CORE_IMG}" of="${IMG_TMP}" bs=512 seek=$((BIOS_PART_SIZE / 512 / 2)) conv=notrunc status=none 2>/dev/null && {
                    GRUB_BIOS_OK=1
                    log "GRUB BIOS installato manualmente (core.img + MBR)"
                } || log "  (warn) core.img non scritto"
                printf '\x55\xAA' | dd of="${IMG_TMP}" bs=1 seek=510 conv=notrunc status=none 2>/dev/null || true
            else
                log "  (warn) core.img troppo grande per BIOS_BOOT partition"
            fi
        else
            log "  (warn) grub-mkimage fallita"
        fi
    else
        log "  (warn) grub-mkimage non disponibile"
    fi
fi

if [ "${GRUB_BIOS_OK}" = "0" ]; then
    log "WARN: GRUB BIOS (Legacy) non installato. Funziona solo UEFI."
fi

# ---- Validazione finale ----
log "=== validazione immagine finale ==="
log "  file: $(ls -lh "${IMG_TMP}" | awk '{print $5}')"
if command -v sfdisk >/dev/null 2>&1; then
    sfdisk -l "${IMG_TMP}" 2>/dev/null | while read -r line; do log "  $line"; done
elif command -v parted >/dev/null 2>&1; then
    parted -s "${IMG_TMP}" print 2>/dev/null | while read -r line; do log "  $line"; done
fi

# Sposta immagine finale in out/
log "sposto immagine finale in ${IMG}"
[ -f "${IMG}" ] && mv "${IMG}" "${IMG}.bak.$(date +%s)" 2>/dev/null || rm -f "${IMG}"
cp "${IMG_TMP}" "${IMG}"
log "img scritto: ${IMG} ($(du -h "${IMG}" | cut -f1))"

# ---- Cleanup ----
rm -rf "${IMG_WORK}" "${WORKROOTFS}" "${WORK}"

log "========================================="
log " BUILD COMPLETATA"
log "========================================="
log "  ISO:  ${ISO} ($(du -h "${ISO}" | cut -f1))"
log "  IMG:  ${IMG} ($(du -h "${IMG}" | cut -f1))"
log ""
log "  QEMU:   qemu-system-x86_64 -cdrom ${ISO} -m 2G -smp 2"
log "  USB:    Rufus DD mode, balenaEtcher, oppure:"
log "          sudo dd if=${IMG} of=/dev/sdX bs=4M status=progress conv=fdatasync"
log ""
log "  NOTA: per UEFI con QEMU aggiungere:"
log "    -drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE.fd"

exit 0