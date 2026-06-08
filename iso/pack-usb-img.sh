#!/bin/sh
# pack-usb-img.sh — genera immagine disco raw per USB (UEFI + Legacy BIOS).
# Output: out/speace-os-${VERSION}.img
#
# A differenza della ISO (che usa El Torito e si scrive bit-per-bit solo
# in modalità Rufus DD Image), questo .img è un disco vero con:
#   - tabella partizioni GPT + BIOS boot partition (per GRUB BIOS)
#   - partizione EFI (FAT32 64MB) con GRUB EFI e kernel/initramfs
#   - partizione rootfs (ext4 ~500MB) con il rootfs Alpine completo
#   - GRUB installato nel MBR + core.img nel BIOS boot gap
#
# La USB scritta con Rufus DD mode / balenaEtcher / `dd` parte sia in
# UEFI che in Legacy BIOS senza dover configurare Secure Boot/CD-mode.

set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${HERE}/.." && pwd)"
OUT="${ROOT}/out"
VERSION="$(cat "${ROOT}/VERSION")"
IMG="${OUT}/speace-os-${VERSION}.img"
LOGFILE="${OUT}/usb-img-build.log"

if [ ! -d "${OUT}/rootfs/bin" ]; then
    "${HERE}/build.sh"
fi

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "${LOGFILE}"; }

# ------------------------------------------------------------ #
# Layout:
#   Sector 0        : protective MBR + GRUB BIOS (1MB = 2048 settori)
#   Sector 1..33    : GPT header + entries
#   Sector 2048..   : partizione EFI (64MB = 131072 settori)
#   Sector 133120.. : partizione rootfs (~500MB = 1024000 settori)
# ------------------------------------------------------------ #

BIOS_START=64
BIOS_SIZE_SECTORS=$((1 * 1024 * 1024 / 512))      # 1MB per GRUB BIOS
EFI_START=$((BIOS_START + BIOS_SIZE_SECTORS))
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
    parted -s "${IMG}" mkpart BIOS_BOOT fat32 ${BIOS_START}s $((BIOS_START + BIOS_SIZE_SECTORS - 1))s
    parted -s "${IMG}" set 1 bios_grub on
    parted -s "${IMG}" mkpart ESP fat32 ${EFI_START}s $((EFI_START + EFI_SIZE_SECTORS - 1))s
    parted -s "${IMG}" set 2 esp on
    parted -s "${IMG}" mkpart ROOTFS ext4 ${ROOTFS_START}s $((ROOTFS_START + ROOTFS_SIZE_SECTORS - 1))s

    # Loop-mount delle partizioni
    LOOPDEV=$(losetup --find --show --partscan "${IMG}" 2>/dev/null || echo "")
    if [ -n "${LOOPDEV}" ]; then
        trap "losetup -d ${LOOPDEV} 2>/dev/null || true" EXIT

        # Aspetta che i device partiscano (max 5s)
        for i in 1 2 3 4 5; do
            if [ -b "${LOOPDEV}p1" ] && [ -b "${LOOPDEV}p2" ] && [ -b "${LOOPDEV}p3" ]; then break; fi
            sleep 1
        done

        # ---- Partizione EFI: FAT32 con GRUB EFI + kernel + initramfs ----
        log "formato partizione EFI (FAT32)"
        mkfs.fat -F32 -n SPEACE_EFI "${LOOPDEV}p2" >/dev/null 2>&1
        USBMNT="$(mktemp -d)"
        mount "${LOOPDEV}p2" "${USBMNT}"

        # ---- GRUB BIOS core.img installato nel MBR + BIOS boot partition ----
        # GRUB scrive boot.img nel MBR, core.img nella BIOS boot partition (p1),
        # e i moduli in USBMNT/boot/grub
        log "installo GRUB i386-pc nel MBR + BIOS boot partition"
        if command -v grub-install >/dev/null 2>&1; then
            mkdir -p "${USBMNT}/boot/grub"
            grub-install --target=i386-pc \
                --boot-directory="${USBMNT}/boot" \
                --modules="ext2 fat part_msdos part_gpt biosdisk" \
                --install-modules="ext2 fat part_msdos part_gpt biosdisk linux acpi normal ls echo test sleep configfile" \
                "${LOOPDEV}" 2>&1 | tee -a "${LOGFILE}" || \
            log "(warn) grub-install BIOS fallita — solo boot UEFI"
        else
            log "(warn) grub-install non trovato — solo UEFI"
        fi

        # grub.cfg per USB (scritto prima di grub-mkstandalone per embedding)
        mkdir -p "${USBMNT}/boot/grub"
        cat > "${USBMNT}/boot/grub/grub.cfg" <<'GRUBEOF'
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

        # ---- GRUB EFI bootx64.efi (usa il grub.cfg appena scritto) ----
        mkdir -p "${USBMNT}/EFI/BOOT"
        if command -v grub-mkstandalone >/dev/null 2>&1; then
            log "creo BOOTX64.EFI con grub-mkstandalone"
            grub-mkstandalone \
                --format=x86_64-efi \
                --output="${USBMNT}/EFI/BOOT/BOOTX64.EFI" \
                --install-modules="ext2 fat part_gpt efi_networking" \
                /boot/grub/grub.cfg="${USBMNT}/boot/grub/grub.cfg" \
                2>&1 | tee -a "${LOGFILE}" || true
        elif [ -f "/usr/lib/grub/x86_64-efi/bootx64.efi" ]; then
            log "copio bootx64.efi prebuilt"
            cp "/usr/lib/grub/x86_64-efi/bootx64.efi" "${USBMNT}/EFI/BOOT/BOOTX64.EFI"
        else
            log "(warn) bootx64.efi non disponibile — UEFI non supportato"
        fi

        # Kernel + initramfs nella partizione EFI
        cp "${OUT}/kernel/bzImage" "${USBMNT}/boot/bzImage"
        cp "${OUT}/initramfs.cpio.gz" "${USBMNT}/boot/initramfs.cpio.gz"

        umount "${USBMNT}"
        rmdir "${USBMNT}"

        # ---- Rootfs partition: ext4 con il rootfs ----
        log "formato partizione rootfs (ext4 ${ROOTFS_SIZE_MB}MB)"
        mkfs.ext4 -L SPEACE_ROOT -F "${LOOPDEV}p3" >/dev/null 2>&1
        ROOTFS_MNT="$(mktemp -d)"
        mount "${LOOPDEV}p3" "${ROOTFS_MNT}"

        log "copio rootfs nella partizione"
        cp -a "${OUT}/rootfs/." "${ROOTFS_MNT}/"

        # Kernel + initramfs anche nel rootfs (fallback)
        mkdir -p "${ROOTFS_MNT}/boot"
        cp "${OUT}/kernel/bzImage" "${ROOTFS_MNT}/boot/bzImage"
        cp "${OUT}/initramfs.cpio.gz" "${ROOTFS_MNT}/boot/initramfs.cpio.gz"

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

# Fallback: img semplificato
log "(fallback) creo img semplificato (rootfs come file)"
RAW="${OUT}/speace-os-${VERSION}-fallback.img"
truncate -s 100M "${RAW}"
mkfs.fat -F32 -n SPEACE "${RAW}" >/dev/null 2>&1
mv "${RAW}" "${IMG}"
echo "[pack-usb-img] (warn) img fallback 100M: ${IMG}"
