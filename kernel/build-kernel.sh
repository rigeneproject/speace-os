#!/bin/sh
# build-kernel.sh — build del kernel Linux minimale per SPEACE OS.
# Prodotto: bzImage + modules (non servono per boot base) in out/.
#
# Richiede: gcc, make, bison, flex, libelf-dev, bc, openssl-dev
# Uso:      ./build-kernel.sh [linux-version]
# Default:  6.6.46 (LTS)

set -eu

LINUX_VERSION="${1:-6.6.46}"
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="${HERE}/../out"
KERNELDIR="${OUT}/linux-${LINUX_VERSION}"
LOG="${OUT}/kernel-build.log"

mkdir -p "${OUT}"

if [ ! -d "${KERNELDIR}" ]; then
    echo "[kernel] scarico linux-${LINUX_VERSION}.tar.xz"
    cd "${OUT}"
    if command -v curl >/dev/null 2>&1; then
        curl -fsSLO "https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-${LINUX_VERSION}.tar.xz"
    else
        wget -q "https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-${LINUX_VERSION}.tar.xz"
    fi
    tar -xf "linux-${LINUX_VERSION}.tar.xz"
fi

cd "${KERNELDIR}"

echo "[kernel] applico config SPEACE OS"
cp "${HERE}/linux-config" .config

# Disabilita signing del keyring (richiede chiavi) per build riproducibile.
scripts/config --set-str SYSTEM_TRUSTED_KEYS ""
scripts/config --set-str SYSTEM_REVOCATION_KEYS ""

echo "[kernel] make -j$(nproc) bzImage"
make -j"$(nproc)" bzImage >"${LOG}" 2>&1

mkdir -p "${OUT}/kernel"
cp arch/x86/boot/bzImage "${OUT}/kernel/bzImage"
echo "[kernel] bzImage scritto in ${OUT}/kernel/bzImage ($(du -h "${OUT}/kernel/bzImage" | cut -f1))"
