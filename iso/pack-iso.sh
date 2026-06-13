#!/bin/sh
# pack-iso.sh - genera ISO avviabile (BIOS + UEFI) con GRUB.
# Output: out/speace-os-${VERSION}.iso
#
# Strategia: costruiamo l'ISO direttamente in ${WORK} con bzImage, initramfs,
# grub.cfg, rootfs.tar.gz, e poi usiamo grub-mkrescue che internamente usa
# xorriso e produce un ISO BIOS+UEFI valido.
#
# NOTA: Questo ISO e' pensato per CD-ROM/QEMU. Per boot da USB usare
# l'immagine IMG (speace-os-*.img) generata da pack-usb-img.sh.

set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${HERE}/.." && pwd)"
OUT="${ROOT}/out"
VERSION="$(cat "${ROOT}/VERSION")"
ISO="${OUT}/speace-os-${VERSION}.iso"
WORK="${OUT}/iso-build"
LOGFILE="${OUT}/iso-build.log"
GRUB_RESCUE_ISO="${OUT}/grub-rescue.iso"

log() { echo "[pack-iso] $*" | tee -a "${LOGFILE}"; }

# Verifica prerequisiti
for f in "${OUT}/kernel/bzImage" "${OUT}/initramfs.cpio.gz"; do
    if [ ! -f "$f" ]; then
        log "FATAL: file mancante: $f"
        exit 1
    fi
done

rm -rf "${WORK}"
mkdir -p "${WORK}/boot/grub" "${WORK}/EFI/BOOT" "${WORK}/speace"

# 1) grub.cfg
cat > "${WORK}/boot/grub/grub.cfg" <<'EOF'
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

# 2) Copia payload SPEACE
log "copio bzImage, initramfs"
cp -f "${OUT}/kernel/bzImage" "${WORK}/boot/bzImage"
cp -f "${OUT}/initramfs.cpio.gz" "${WORK}/boot/initramfs.cpio.gz"

if [ -d "${OUT}/rootfs" ] && [ -f "${OUT}/rootfs/etc/speace/coordinator.yaml" ]; then
    log "creo speace/rootfs.tar.gz (rootfs overlay presente)"
    tar -czf "${WORK}/speace/rootfs.tar.gz" -C "${OUT}" rootfs
else
    log "(warn) rootfs non pronto: ${OUT}/rootfs/etc/speace/coordinator.yaml mancante"
    : > "${WORK}/speace/.gitkeep"
fi

# 3) grub-mkrescue (BIOS+UEFI, deterministico)
log "eseguo grub-mkrescue"
rm -f "${GRUB_RESCUE_ISO}"
if ! grub-mkrescue -o "${GRUB_RESCUE_ISO}" "${WORK}" 2>&1 | tee -a "${LOGFILE}"; then
    log "FATAL: grub-mkrescue fallita"
    exit 1
fi

# 4) Verifica e sposta
if [ ! -s "${GRUB_RESCUE_ISO}" ]; then
    log "FAIL: ISO vuota (grub-mkrescue non ha prodotto output)"
    exit 1
fi
rm -f "${ISO}"
mv "${GRUB_RESCUE_ISO}" "${ISO}"
rm -rf "${WORK}"

# 5) Report finale
ISO_SIZE=$(du -h "${ISO}" | cut -f1)
log "ISO scritto: ${ISO} (${ISO_SIZE})"
log "=== report El Torito ==="
xorriso -indev "${ISO}" -report_el_torito plain 2>&1 | tee -a "${LOGFILE}" | head -20 || true

log "=== NOTE PER BOOT ==="
log "  - QEMU/KVM: qemu-system-x86_64 -cdrom ${ISO} -m 2G -smp 2"
log "  - CD/DVD: masterizzare come immagine ISO, boot BIOS o UEFI"
log "  - USB: NON scrivere l'ISO direttamente su USB."
log "    Usare invece l'immagine IMG: speace-os-${VERSION}.img (da pack-usb-img.sh)"
log "    Oppure: Rufus in modalita' DD Image (non ISO mode), o balenaEtcher"
exit 0
