#!/bin/sh
# pack-qcow2.sh — genera immagine QCOW2 per KVM/QEMU.
# Output: out/speace-os-0.1.0-cos.qcow2

set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${HERE}/.." && pwd)"
OUT="${ROOT}/out"
VERSION="$(cat "${ROOT}/VERSION")"
QCOW2="${OUT}/speace-os-${VERSION}.qcow2"

if [ ! -d "${OUT}/rootfs/bin" ]; then
    "${HERE}/build.sh"
fi

# Crea immagine raw 4 GB, partizionata: EFI (256MB) + rootfs (3.7GB)
RAW="${OUT}/speace-os-${VERSION}.raw"
truncate -s 4G "${RAW}"

# Loop-mount per formattare le partizioni
# ... (richiede root, è più semplice creare l'immagine direttamente)

# Strategia semplificata: usiamo virt-make-fs o genimage se disponibili
# Altrimenti creiamo direttamente un disco "BIOS+EFI" con due partizioni

if command -v virt-make-fs >/dev/null 2>&1; then
    # Crea un filesystem ext4 standalone
    OFFSET_ROOT=$((4 * 1024 * 1024 * 1024 - 100 * 1024 * 1024))
    OFFSET_EFI=$((1 * 1024 * 1024))  # partizione EFI da 256MB
    SECTORS_PER_MB=$((1024 * 1024 / 512))

    # Scrivi partizione EFI
    dd if=/dev/zero of="${RAW}" bs=512 count=$((256 * SECTORS_PER_MB))
    mkfs.fat -F12 -n SPEACE_EFI "${RAW}" 2>&1 | head -5

    # Crea filesystem rootfs in file separato
    virt-make-fs --type=ext4 --size=+3G -o "${OUT}/rootfs.img" "${OUT}/rootfs"

    # Concatena
    cat "${OUT}/rootfs.img" >> "${RAW}"

    # Converti in qcow2
    qemu-img convert -f raw -O qcow2 "${RAW}" "${QCOW2}"
    rm -f "${RAW}" "${OUT}/rootfs.img"
else
    # Fallback: crea direttamente un qcow2 con il rootfs come "device"
    qemu-img create -f qcow2 -o backing_file="${OUT}/rootfs.tar.gz" "${QCOW2}" 100M 2>&1
    echo "[pack-qcow2] (warn) virt-make-fs non disponibile, qcow2 minimale"
fi

echo "[pack-qcow2] QCOW2 scritto: ${QCOW2} ($(du -h "${QCOW2}" | cut -f1))"
