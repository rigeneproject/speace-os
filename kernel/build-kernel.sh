#!/bin/sh
# build-kernel.sh - build del kernel Linux minimale per SPEACE OS.
# Prodotto: bzImage in out/kernel/.
#
# Richiede: gcc, make, bison, flex, libelf-dev, bc, openssl-dev
# Uso:      ./build-kernel.sh [linux-version]
# Default:  6.6.46 (LTS)
#
# Ottimizzazione WSL: l'estrazione e la compilazione avvengono in /tmp
# (filesystem nativo) e solo l'output finale viene spostato in out/.
# Su WSL il path /mnt/c e lentissimo per tar e make.

set -eu

LINUX_VERSION="${1:-6.6.46}"
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="${HERE}/../out"
LOG="${OUT}/kernel-build.log"
NPROC="$(nproc 2>/dev/null || echo 4)"

mkdir -p "${OUT}"

# Directory di lavoro veloce (su filesystem nativo)
WORKROOT="${WORKROOT:-/tmp/speace-kernel-build}"
mkdir -p "${WORKROOT}"
TARBALL="${OUT}/linux-${LINUX_VERSION}.tar.xz"
KERNELDIR="${WORKROOT}/linux-${LINUX_VERSION}"

if [ ! -d "${KERNELDIR}" ]; then
    echo "[kernel] scarico linux-${LINUX_VERSION}.tar.xz in ${OUT}"
    if [ ! -f "${TARBALL}" ]; then
        cd "${OUT}"
        if command -v curl >/dev/null 2>&1; then
            curl -fsSLO "https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-${LINUX_VERSION}.tar.xz"
        else
            wget -q "https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-${LINUX_VERSION}.tar.xz"
        fi
    fi
    echo "[kernel] estraggo in ${WORKROOT} (filesystem veloce)"
    cp "${TARBALL}" "${WORKROOT}/"
    cd "${WORKROOT}"
    tar -xf "linux-${LINUX_VERSION}.tar.xz"
fi

cd "${KERNELDIR}"

echo "[kernel] applico config SPEACE OS"
cp "${HERE}/linux-config" .config

# Disabilita signing del keyring (richiede chiavi) per build riproducibile.
scripts/config --set-str SYSTEM_TRUSTED_KEYS ""
scripts/config --set-str SYSTEM_REVOCATION_KEYS ""

echo "[kernel] risolvo dipendenze Kconfig (olddefconfig)"
yes '' | make olddefconfig >>"${LOG}" 2>&1

echo "[kernel] make -j${NPROC} bzImage"
make -j"${NPROC}" bzImage >>"${LOG}" 2>&1

mkdir -p "${OUT}/kernel"
cp arch/x86/boot/bzImage "${OUT}/kernel/bzImage"
echo "[kernel] bzImage scritto in ${OUT}/kernel/bzImage ($(du -h "${OUT}/kernel/bzImage" | cut -f1))"

# Cleanup facoltativo (mantieni /tmp per ispezione)
# rm -rf "${WORKROOT}"