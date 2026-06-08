#!/bin/sh
# pack-iso.sh — genera ISO avviabile (BIOS + UEFI) con GRUB.
# Output: out/speace-os-0.1.0-cos.iso

set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${HERE}/.." && pwd)"
OUT="${ROOT}/out"
VERSION="$(cat "${ROOT}/VERSION")"
ISO="${OUT}/speace-os-${VERSION}.iso"

mkdir -p "${OUT}/iso/boot/grub"

# GRUB config
cat > "${OUT}/iso/boot/grub/grub.cfg" <<'EOF'
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
cp "${OUT}/kernel/bzImage" "${OUT}/iso/boot/bzImage"
cp "${OUT}/initramfs.cpio.gz" "${OUT}/iso/boot/initramfs.cpio.gz"

# Copia i binari GRUB necessari per il boot (BIOS + EFI)
mkdir -p "${OUT}/iso/boot/grub/i386-pc"
GRUB_PC_DIR="/usr/lib/grub/i386-pc"
# Su Ubuntu 24.04 grub-pc-bin NON fornisce eltorito.img ma solo cdboot.img
# (per CD/ISO boot) e boot.img (per MBR/HDD). Usiamo cdboot.img che è
# l'equivalente moderno di eltorito.img.
for f in cdboot.img boot_hybrid.img; do
    if [ -f "${GRUB_PC_DIR}/${f}" ]; then
        cp "${GRUB_PC_DIR}/${f}" "${OUT}/iso/boot/grub/i386-pc/${f}"
    fi
done
# Crea un alias eltorito.img → cdboot.img per retro-compatibilità
if [ ! -f "${OUT}/iso/boot/grub/i386-pc/eltorito.img" ] && [ -f "${OUT}/iso/boot/grub/i386-pc/cdboot.img" ]; then
    cp "${OUT}/iso/boot/grub/i386-pc/cdboot.img" "${OUT}/iso/boot/grub/i386-pc/eltorito.img"
fi
# Immagine EFI (per boot UEFI)
GRUB_EFI_DIR="/usr/lib/grub/x86_64-efi"
if [ -f "${GRUB_EFI_DIR}/bootx64.efi" ]; then
    mkdir -p "${OUT}/iso/EFI/BOOT"
    cp "${GRUB_EFI_DIR}/bootx64.efi" "${OUT}/iso/EFI/BOOT/BOOTX64.EFI"
fi

# Copia rootfs come filesystem accessibile (per debug e installazione)
mkdir -p "${OUT}/iso/speace"
tar -czf "${OUT}/iso/speace/rootfs.tar.gz" -C "${OUT}" rootfs

# Genera ISO con xorriso (BIOS)
# Su Ubuntu 24.04 grub-pc-bin non ha eltorito.img, quindi usiamo cdboot.img
xorriso -as mkisofs \
    -R -J -joliet-long \
    -V "SPEACE_OS" \
    -o "${ISO}" \
    -b boot/grub/i386-pc/cdboot.img \
    -no-emul-boot -boot-load-size 4 -boot-info-table \
    --grub2-boot-info --grub2-mbr "${OUT}/iso/boot/grub/i386-pc/boot_hybrid.img" \
    "${OUT}/iso/" 2>&1

echo "[pack-iso] ISO scritto: ${ISO} ($(du -h "${ISO}" | cut -f1))"
