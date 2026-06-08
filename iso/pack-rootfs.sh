#!/bin/sh
# pack-rootfs.sh — impacchetta il rootfs in un tar compresso scaricabile.
# Output: out/rootfs.tar.gz

set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${HERE}/.." && pwd)"
OUT="${ROOT}/out"
TARBALL="${OUT}/rootfs.tar.gz"

if [ ! -d "${OUT}/rootfs/bin" ]; then
    "${HERE}/build.sh"
fi

cd "${OUT}"
tar -czf "${TARBALL}" rootfs/
echo "[pack-rootfs] ${TARBALL} ($(du -h "${TARBALL}" | cut -f1))"
