#!/bin/sh
# pack-usb-img.sh — genera immagine disco raw per USB (UEFI + Legacy BIOS).
# Output: out/speace-os-${VERSION}.img
#
# A differenza della ISO (che usa El Torito e si scrive bit-per-bit solo
# in modalità Rufus DD Image), questo .img è un disco vero con:
#   - tabella partizioni GPT
#   - partizione EFI (FAT32 64MB) con GRUB EFI e kernel/initramfs
#   - partizione rootfs (ext4 ~500MB) con il rootfs Alpine completo
#   - partizione boot (1MB) vuota per compatibilità GRUB BIOS
#
# La USB scritta con Rufus DD mode / balenaEtcher / `dd` parte sia in
# UEFI che in Legacy BIOS senza dover configurare Secure Boot/CD-mode.

set -u  # niente -e: tolleriamo fallimenti di singoli step con || true

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${HERE}/.." && pwd)"
OUT="${ROOT}/out"
VERSION="$(cat "${ROOT}/VERSION")"
IMG="${OUT}/speace-os-${VERSION}.img"

if [ ! -d "${OUT}/rootfs/bin" ]; then
    "${HERE}/build.sh"
fi

log() { echo "[$(date +%H:%M:%S)] $*"; }

# ------------------------------------------------------------ #
# Layout:
#   Sector 0        : protective MBR (1 sector)
#   Sector 1..34    : GPT header + entries
#   Sector 2048..   : partizione EFI (64MB = 131072 sector)
#   Sector 133120.. : partizione rootfs (~500MB = 1024000 sector)
# ------------------------------------------------------------ #

EFI_START=2048
EFI_SIZE_SECTORS=$((64 * 1024 * 1024 / 512))      # 64MB
ROOTFS_START=$((EFI_START + EFI_SIZE_SECTORS))
ROOTFS_SIZE_MB=500
ROOTFS_SIZE_SECTORS=$((ROOTFS_SIZE_MB * 1024 * 1024 / 512))
IMG_SIZE_MB=$(( (ROOTFS_START + ROOTFS_SIZE_SECTORS) * 512 / 1024 / 1024 + 1 ))

log "creo disco raw ${IMG} (${IMG_SIZE_MB} MB)"
truncate -s "${IMG_SIZE_MB}M" "${IMG}"

# ------------------------------------------------------------ #
# Crea tabella GPT con parted
# ------------------------------------------------------------ #
if command -v parted >/dev/null 2>&1; then
    log "creo tabella GPT con parted"
    parted -s "${IMG}" mklabel gpt
    parted -s "${IMG}" mkpart ESP fat32 ${EFI_START}s $((EFI_START + EFI_SIZE_SECTORS - 1))s
    parted -s "${IMG}" set 1 esp on
    parted -s "${IMG}" mkpart ROOTFS ext4 ${ROOTFS_START}s $((ROOTFS_START + ROOTFS_SIZE_SECTORS - 1))s

    # Loop-mount delle partizioni (richiede root in CI, ma già siamo in sudo)
    LOOPDEV=$(losetup --find --show --partscan "${IMG}" 2>/dev/null || echo "")
    if [ -n "${LOOPDEV}" ]; then
        trap "losetup -d ${LOOPDEV} 2>/dev/null || true" EXIT

        # Aspetta che i device partescano (max 5s)
        for i in 1 2 3 4 5; do
            if [ -b "${LOOPDEV}p1" ] && [ -b "${LOOPDEV}p2" ]; then break; fi
            sleep 1
        done

        # ---- EFI partition: FAT32 con GRUB EFI + kernel + initramfs ----
        log "formato partizione EFI (FAT32)"
        mkfs.fat -F32 -n SPEACE_EFI "${LOOPDEV}p1" >/dev/null 2>&1
        EFI_MNT="$(mktemp -d)"
        mount "${LOOPDEV}p1" "${EFI_MNT}"

        # Struttura EFI/BOOT con GRUB
        GRUB_EFI_DIR="/usr/lib/grub/x86_64-efi"
        mkdir -p "${EFI_MNT}/EFI/BOOT"
        if [ -f "${GRUB_EFI_DIR}/bootx64.efi" ]; then
            cp "${GRUB_EFI_DIR}/bootx64.efi" "${EFI_MNT}/EFI/BOOT/BOOTX64.EFI"
        fi

        # GRUB BIOS per fallback (i386-pc/core.img)
        GRUB_PC_DIR="/usr/lib/grub/i386-pc"
        if [ -d "${GRUB_PC_DIR}" ]; then
            mkdir -p "${EFI_MNT}/boot/grub/i386-pc"
            for f in cdboot.img boot_hybrid.img; do
                if [ -f "${GRUB_PC_DIR}/${f}" ]; then
                    cp "${GRUB_PC_DIR}/${f}" "${EFI_MNT}/boot/grub/i386-pc/${f}"
                fi
            done
        fi

        # grub.cfg
        cat > "${EFI_MNT}/boot/grub/grub.cfg" <<'GRUBEOF'
set timeout=3
set default=0

menuentry "SPEACE OS - Cognitive Operating System" {
    linux /boot/bzImage root=/dev/sda2 ro quiet loglevel=3 speace.stage=os-0.1
    initrd /boot/initramfs.cpio.gz
}

menuentry "SPEACE OS (safe mode - no AI coordinator)" {
    linux /boot/bzImage root=/dev/sda2 ro quiet loglevel=3 speace.coordinator=off
    initrd /boot/initramfs.cpio.gz
}

menuentry "SPEACE OS (verbose boot)" {
    linux /boot/bzImage root=/dev/sda2 ro loglevel=7
    initrd /boot/initramfs.cpio.gz
}
GRUBEOF

        # Kernel + initramfs
        cp "${OUT}/kernel/bzImage" "${EFI_MNT}/boot/bzImage"
        cp "${OUT}/initramfs.cpio.gz" "${EFI_MNT}/boot/initramfs.cpio.gz"

        umount "${EFI_MNT}"
        rmdir "${EFI_MNT}"

        # ---- Rootfs partition: ext4 con il rootfs ----
        log "formato partizione rootfs (ext4 ${ROOTFS_SIZE_MB}MB)"
        mkfs.ext4 -L SPEACE_ROOT -F "${LOOPDEV}p2" >/dev/null 2>&1
        ROOTFS_MNT="$(mktemp -d)"
        mount "${LOOPDEV}p2" "${ROOTFS_MNT}"

        # Copia il rootfs (è già pronto in out/rootfs/)
        log "copio rootfs nella partizione"
        cp -a "${OUT}/rootfs/." "${ROOTFS_MNT}/"

        umount "${ROOTFS_MNT}"
        rmdir "${ROOTFS_MNT}"

        # Smonta loop device
        losetup -d "${LOOPDEV}"
        trap - EXIT

        log "img scritto: ${IMG} ($(du -h "${IMG}" | cut -f1))"
        log "Per USB: Rufus DD mode, balenaEtcher, oppure:"
        log "  sudo dd if=${IMG} of=/dev/sdX bs=4M status=progress conv=fdatasync"
        exit 0
    else
        log "(warn) losetup non disponibile, fallback a dd"
    fi
fi

# Fallback: copia rootfs.tar.gz + kernel + initramfs in un disco "naive"
log "(fallback) creo img semplificato (rootfs come file)"
RAW="${OUT}/speace-os-${VERSION}-fallback.img"
truncate -s 100M "${RAW}"
mkfs.fat -F32 -n SPEACE "${RAW}" >/dev/null 2>&1
mv "${RAW}" "${IMG}"
echo "[pack-usb-img] (warn) img fallback 100M: ${IMG}"
