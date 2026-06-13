#!/bin/sh
# pack-usb-img.sh - genera immagine disco raw per USB (UEFI + Legacy BIOS).
# Output: out/speace-os-${VERSION}.img

set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${HERE}/.." && pwd)"
OUT="${ROOT}/out"
VERSION="$(cat "${ROOT}/VERSION")"
IMG="${OUT}/speace-os-${VERSION}.img"
LOGFILE="${OUT}/usb-img-build.log"

if [ ! -f "${OUT}/rootfs/etc/speace/coordinator.yaml" ]; then
    log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "${LOGFILE}"; }
    log "rootfs non pronto, eseguo build.sh"
    "${HERE}/build.sh" >/dev/null 2>&1 || true
fi

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "${LOGFILE}"; }

do_mount() {
    if mount "$@" 2>/dev/null; then return 0; fi
    if sudo -n mount "$@" 2>/dev/null; then return 0; fi
    return 1
}
do_umount() {
    if umount "$@" 2>/dev/null; then return 0; fi
    if sudo -n umount "$@" 2>/dev/null; then return 0; fi
    return 1
}

WORK="/tmp/speace-usb-img"
rm -rf "${WORK}"
mkdir -p "${WORK}"

IMG_TMP="${WORK}/disk.img"
ESP_TMP="${WORK}/esp.img"
ROOTFS_TMP="${WORK}/rootfs.img"
ROOTFS_MNT="${WORK}/rootfs_mnt"
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
log "estraggo partizioni come file in ${WORK}"
dd if="${IMG_TMP}" of="${ESP_TMP}" bs=512 skip=$((EFI_START_MIB * SECPERMB)) count=${EFI_SECTORS} status=none
dd if="${IMG_TMP}" of="${ROOTFS_TMP}" bs=512 skip=$((ROOTFS_START_MIB * SECPERMB)) count=${ROOTFS_SECTORS} status=none

# ---- ESP FAT32 con mtools (no mount) ----
log "formato ESP FAT32 (${EFI_MB}MB)"
mkfs.fat -F32 -n SPEACE_EFI "${ESP_TMP}" >/dev/null

GRUB_TMP="${WORK}/grub_esp"
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

# Copia overlay in /tmp prima
ROOTFS_OVERLAY="${WORK}/overlay"
rm -rf "${ROOTFS_OVERLAY}"
mkdir -p "${ROOTFS_OVERLAY}"
log "copio rootfs overlay in ${ROOTFS_OVERLAY}"
(cd "${OUT}/rootfs" && tar -cf - .) | (cd "${ROOTFS_OVERLAY}" && tar -xf -)
log "overlay copiato: $(find "${ROOTFS_OVERLAY}" -type f | wc -l) file"

# Popola la partizione con sudo (mount -o loop ha bisogno di root)
ROOTFS_POPULATED=0
if do_mount -o loop "${ROOTFS_TMP}" "${ROOTFS_MNT}" 2>/dev/null; then
    log "rootfs montato, popolo con sudo"
    if sudo -n sh -c "rm -rf '${ROOTFS_MNT}/*' '${ROOTFS_MNT}/.*' 2>/dev/null; cp -a '${ROOTFS_OVERLAY}/.' '${ROOTFS_MNT}/'" 2>&1 | tee -a "${LOGFILE}"; then
        ROOTFS_POPULATED=1
        log "overlay copiato in rootfs_mnt"
    else
        log "(warn) sudo cp fallita"
    fi
    sync
    do_umount "${ROOTFS_MNT}"
fi

if [ "${ROOTFS_POPULATED}" = "0" ]; then
    log "(warn) rootfs non popolato (mount fallito). Eseguire in Linux nativo."
fi

# Riscrivi le partizioni nell'immagine
log "aggiorno partizioni nell'immagine"
dd if="${ESP_TMP}" of="${IMG_TMP}" bs=512 seek=$((EFI_START_MIB * SECPERMB)) count=${EFI_SECTORS} conv=notrunc status=none
dd if="${ROOTFS_TMP}" of="${IMG_TMP}" bs=512 seek=$((ROOTFS_START_MIB * SECPERMB)) count=${ROOTFS_SECTORS} conv=notrunc status=none

# ---- GRUB BIOS installato nel MBR ----
log "installo GRUB i386-pc nell'MBR"
GRUB_BIOS_OK=0
if command -v grub-install >/dev/null 2>&1; then
    GRUB_BOOT="${WORK}/grub-bios-boot"
    rm -rf "${GRUB_BOOT}"
    mkdir -p "${GRUB_BOOT}"
    if grub-install --target=i386-pc \
        --boot-directory="${GRUB_BOOT}" \
        --modules="ext2 fat part_msdos part_gpt biosdisk" \
        --install-modules="ext2 fat part_msdos part_gpt biosdisk linux acpi normal ls echo test sleep configfile" \
        "${IMG_TMP}" 2>&1 | tee -a "${LOGFILE}"; then
        GRUB_BIOS_OK=1
        log "GRUB BIOS installato in MBR (grub-install)"
    fi
fi

if [ "${GRUB_BIOS_OK}" = "0" ]; then
    log "(warn) grub-install fallita, provo install manuale con grub-mkimage + dd..."
    if command -v grub-mkimage >/dev/null 2>&1; then
        # Crea core.img per GPT + filesystem tipici
        GRUB_MODULES="ext2 fat part_msdos part_gpt biosdisk ls echo test sleep configfile linux normal acpi"
        CORE_IMG="${WORK}/core.img"
        if grub-mkimage -O i386-pc -o "${CORE_IMG}" ${GRUB_MODULES} 2>&1 | tee -a "${LOGFILE}"; then
            # La BIOS_BOOT partition (partizione 1) inizia a settore 2048 (1MiB)
            # GRUB boot code va nei primi 440 byte del MBR
            # core.img va subito dopo (sector 1-2047) ma su GPT i primi 34 settori
            # sono riservati, quindi core.img si scrive dal settore 34 in avanti
            # (contenuto nella partition 1, bios_grub)
            BIOS_PART_OFFSET=$((1 * MIBSIZE))  # 1 MiB
            BIOS_PART_SIZE=$((BIOS_MB * MIBSIZE))  # 1 MiB
            CORE_IMG_SIZE=$(stat -c%s "${CORE_IMG}" 2>/dev/null || wc -c < "${CORE_IMG}")
            if [ "${CORE_IMG_SIZE}" -le "${BIOS_PART_SIZE}" ]; then
                # Scrivi GRUB MBR boot code (stage1) - primo sector
                if [ -f /usr/lib/grub/i386-pc/boot.img ]; then
                    dd if=/usr/lib/grub/i386-pc/boot.img of="${IMG_TMP}" bs=440 count=1 conv=notrunc status=none 2>/dev/null && \
                    log "  GRUB stage1 (boot.img) scritto in MBR" || \
                    log "  (warn) boot.img non scritto"
                fi
                # Scrivi core.img nella BIOS_BOOT partition (offset 1MiB)
                dd if="${CORE_IMG}" of="${IMG_TMP}" bs=512 seek=$((BIOS_PART_OFFSET / 512)) conv=notrunc status=none 2>/dev/null && {
                    GRUB_BIOS_OK=1
                    log "GRUB BIOS installato manualmente (core.img + MBR)"
                } || log "  (warn) core.img non scritto"
                # Marca il disco come bootabile nel MBR
                printf '\x55\xAA' | dd of="${IMG_TMP}" bs=1 seek=510 conv=notrunc status=none 2>/dev/null || true
            else
                log "  (warn) core.img (${CORE_IMG_SIZE} bytes) troppo grande per BIOS_BOOT partition (${BIOS_PART_SIZE} bytes)"
            fi
        else
            log "  (warn) grub-mkimage fallita"
        fi
    else
        log "  (warn) grub-mkimage non disponibile, BIOS boot non funzionera'"
    fi
fi

if [ "${GRUB_BIOS_OK}" = "0" ]; then
    log "WARN: GRUB BIOS (Legacy) non installato. Funziona solo UEFI."
fi

# ---- Validazione finale ----
log "=== validazione immagine finale ==="
log "  file: $(ls -lh "${IMG_TMP}" | awk '{print $5}')"
# Verifica presenza partizioni con sfdisk
if command -v sfdisk >/dev/null 2>&1; then
    sfdisk -l "${IMG_TMP}" 2>/dev/null | while read -r line; do log "  $line"; done
elif command -v parted >/dev/null 2>&1; then
    parted -s "${IMG_TMP}" print 2>/dev/null | while read -r line; do log "  $line"; done
fi
# Verifica che ESP contenga i file EFI
if command -v mdir >/dev/null 2>&1; then
    log "  contenuto ESP:"
    mdir -i "${IMG_TMP}@@$((EFI_START_MIB * MIBSIZE))" -/ 2>/dev/null | while read -r line; do log "    $line"; done || true
fi

# Sposta immagine finale in out/
log "sposto immagine finale in ${IMG}"
[ -f "${IMG}" ] && mv "${IMG}" "${IMG}.bak.$(date +%s)" 2>/dev/null || rm -f "${IMG}"
cp "${IMG_TMP}" "${IMG}"
log "img scritto: ${IMG} ($(du -h "${IMG}" | cut -f1))"
log "Per USB: usare DD mode (raw) NON ISO mode."
log "  Rufus: selezionare 'DD Image' mode"
log "  balenaEtcher: funziona direttamente"
log "  Linux: sudo dd if=${IMG} of=/dev/sdX bs=4M status=progress conv=fdatasync"
log "  Verificare che il BIOS sia impostato su UEFI (con Secure Boot disattivato) o Legacy."