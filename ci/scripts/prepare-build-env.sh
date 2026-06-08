#!/bin/sh
# prepare-build-env.sh — installa le dipendenze di build su Ubuntu/Debian.
# Eseguibile come root. Idempotente.

set -eu

if [ "$(id -u)" -ne 0 ]; then
    echo "[prepare] richiesto root, usa sudo"
    exec sudo "$0" "$@"
fi

apt-get update
apt-get install -y --no-install-recommends \
    build-essential bc bison flex libelf-dev libssl-dev \
    curl wget cpio gzip rsync xorriso \
    grub-pc-bin grub-efi-amd64-bin grub-common \
    qemu-utils qemu-system-x86 mtools dosfstools \
    debootstrap

# Per Alpine (alternativa a debootstrap per Debian/Ubuntu hosts)
# apk-tools non è nei repo Debian; si scarica lo script di Alpine.

echo "[prepare] ambiente pronto"
