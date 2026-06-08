#!/bin/sh
# pack-iso.sh — genera ISO avviabile (BIOS + UEFI) con GRUB.
# Output: out/speace-os-0.1.0-cos.iso

set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${HERE}/.." && pwd)"
OUT="${ROOT}/out"
VERSION="$(cat "${ROOT}/VERSION")"
ISO="${OUT}/speace-os-${VERSION}.iso"
ISODIR="${OUT}/iso"
LOGFILE="${OUT}/iso-build.log"

mkdir -p "${ISODIR}/boot/grub"

log() { echo "[pack-iso] $*" | tee -a "${LOGFILE}"; }

# GRUB config
cat > "${ISODIR}/boot/grub/grub.cfg" <<'EOF'
set timeout=3
set default=0

menuentry "SPEACE OS — Cognitive Operating System" {
    linux /boot/bzImage root=/dev/sr0 ro quiet loglevel=3 speace.stage=os-0.1
    initrd /boot/initramfs.cpio.gz
}

menuentry "SPEACE OS (safe mode — no AI coordinator)" {
    linux /boot/bzImage root=/dev/sr0 ro quiet loglevel=3 speace.coordinator=off
    initrd /boot/initramfs.cpio.gz
}

menuentry "SPEACE OS (verbose boot)" {
    linux /boot/bzImage root=/dev/sr0 ro loglevel=7
    initrd /boot/initramfs.cpio.gz
}
EOF

# Copia kernel e initramfs
cp "${OUT}/kernel/bzImage" "${ISODIR}/boot/bzImage"
cp "${OUT}/initramfs.cpio.gz" "${ISODIR}/boot/initramfs.cpio.gz"

# Copia rootfs come filesystem accessibile (per debug e installazione)
mkdir -p "${ISODIR}/speace"
tar -czf "${ISODIR}/speace/rootfs.tar.gz" -C "${OUT}" rootfs 2>/dev/null || true

# ---------------------------------------------------------------- #
# Installa GRUB per BIOS (i386-pc) nel boot directory
# ---------------------------------------------------------------- #
log "installo GRUB i386-pc nel boot directory"
if command -v grub-install >/dev/null 2>&1; then
    grub-install --target=i386-pc \
        --boot-directory="${ISODIR}" \
        --modules="iso9660 ext2 fat part_msdos part_gpt biosdisk" \
        --install-modules="iso9660 ext2 fat part_msdos part_gpt biosdisk linux acpi normal ls echo test sleep configfile" \
        --no-floppy \
        --recheck \
        "${ISODIR}" 2>&1 | tee -a "${LOGFILE}" || \
    log "(warn) grub-install BIOS fallita, userò xorriso diretto"
else
    log "(warn) grub-install non trovato"
fi

# ---------------------------------------------------------------- #
# Installa GRUB per UEFI (x86_64-efi)
# ---------------------------------------------------------------- #
log "preparo EFI boot"
mkdir -p "${ISODIR}/EFI/BOOT"

if command -v grub-mkstandalone >/dev/null 2>&1; then
    grub-mkstandalone \
        --format=x86_64-efi \
        --output="${ISODIR}/EFI/BOOT/BOOTX64.EFI" \
        --install-modules="iso9660 ext2 fat part_gpt efi_networking" \
        --modules="iso9660 ext2 fat part_gpt efi_networking" \
        /boot/grub/grub.cfg="${ISODIR}/boot/grub/grub.cfg" \
        2>&1 | tee -a "${LOGFILE}" || \
    log "(warn) grub-mkstandalone fallita, copio bootx64.efi prebuilt"
elif [ -f "/usr/lib/grub/x86_64-efi/bootx64.efi" ]; then
    cp "/usr/lib/grub/x86_64-efi/bootx64.efi" "${ISODIR}/EFI/BOOT/BOOTX64.EFI"
    log "copiato bootx64.efi prebuilt"
else
    log "(warn) bootx64.efi non disponibile — UEFI boot non supportato"
fi

# ---------------------------------------------------------------- #
# Crea immagine EFI FAT per El Torito (UEFI boot da CD)
# Necessaria per boot UEFI da CD-ROM/ISO
# ---------------------------------------------------------------- #
EFI_IMG="${OUT}/efi.img"
if [ -f "${ISODIR}/EFI/BOOT/BOOTX64.EFI" ]; then
    log "creo efi.img per UEFI El Torito"
    truncate -s 8M "${EFI_IMG}"
    mkfs.fat -F12 -n SPEACE_EFI "${EFI_IMG}" >/dev/null 2>&1 || true
    MDIR="$(mktemp -d)"
    mount "${EFI_IMG}" "${MDIR}" 2>/dev/null && {
        mkdir -p "${MDIR}/EFI/BOOT"
        cp "${ISODIR}/EFI/BOOT/BOOTX64.EFI" "${MDIR}/EFI/BOOT/BOOTX64.EFI"
        umount "${MDIR}"
        rmdir "${MDIR}"
    } || {
        # Fallback: mformat + mcopy
        if command -v mformat >/dev/null 2>&1 && command -v mcopy >/dev/null 2>&1; then
            mformat -F -i "${EFI_IMG}" ::
            mmd -i "${EFI_IMG}" ::/EFI ::/EFI/BOOT
            mcopy -i "${EFI_IMG}" "${ISODIR}/EFI/BOOT/BOOTX64.EFI" ::/EFI/BOOT/
        fi
        rmdir "${MDIR}" 2>/dev/null || true
    }
fi

# ---------------------------------------------------------------- #
# Genera ISO con xorriso
# ---------------------------------------------------------------- #
log "genero ISO con xorriso"
XORRISO_OPTS=""
XORRISO_ARGS=""
BOOT_IMG="${ISODIR}/boot/grub/i386-pc/boot_hybrid.img"

# Trova cdboot.img o eltorito.img
for img in "${ISODIR}/boot/grub/i386-pc/cdboot.img" \
           "${ISODIR}/boot/grub/i386-pc/eltorito.img" \
           "/usr/lib/grub/i386-pc/cdboot.img" \
           "/usr/lib/grub/i386-pc/eltorito.img"; do
    if [ -f "${img}" ]; then
        cp "${img}" "${ISODIR}/boot/grub/i386-pc/cdboot.img" 2>/dev/null || true
        BOOT_IMG="${ISODIR}/boot/grub/i386-pc/cdboot.img"
        break
    fi
done

if [ -f "${EFI_IMG}" ]; then
    XORRISO_OPTS="-eltorito-alt-boot -e efi.img -no-emul-boot -isohybrid-gpt-basdat"
    cp "${EFI_IMG}" "${ISODIR}/efi.img"
fi

# Costruisci comando xorriso
xorriso -as mkisofs \
    -R -J -joliet-long \
    -V "SPEACE_OS" \
    -o "${ISO}" \
    -b boot/grub/i386-pc/cdboot.img \
    -no-emul-boot -boot-load-size 4 -boot-info-table \
    --grub2-boot-info \
    ${XORRISO_OPTS} \
    "${ISODIR}/" 2>&1 | tee -a "${LOGFILE}"
XORRISO_RC=$?

# Verifica ISO
if [ ! -f "${ISO}" ]; then
    log "FAIL: ISO non scritto, xorriso exit=${XORRISO_RC}"
    exit ${XORRISO_RC:-1}
fi

# Fallback: se xorriso ha fallito e l'ISO non è valida, prova con la versione
# semplificata (solo BIOS boot)
if [ "${XORRISO_RC}" -ne 0 ] || [ ! -s "${ISO}" ]; then
    log "WARN: xorriso exit=${XORRISO_RC}, riprovo senza UEFI"
    rm -f "${ISO}"
    xorriso -as mkisofs \
        -R -J -joliet-long \
        -V "SPEACE_OS" \
        -o "${ISO}" \
        -b boot/grub/i386-pc/cdboot.img \
        -no-emul-boot -boot-load-size 4 -boot-info-table \
        --grub2-boot-info --grub2-mbr "/usr/lib/grub/i386-pc/boot_hybrid.img" \
        "${ISODIR}/" 2>&1 | tee -a "${LOGFILE}" || true
fi

if [ -f "${ISO}" ] && [ -s "${ISO}" ]; then
    log "ISO scritto: ${ISO} ($(du -h "${ISO}" | cut -f1))"
    rm -f "${ISODIR}/efi.img" 2>/dev/null || true
    exit 0
else
    log "FAIL: ISO non prodotto"
    exit 1
fi
