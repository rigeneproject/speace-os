#!/bin/sh
# cleanup.sh — rimuove tutti gli artefatti di build.

set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${HERE}/.." && pwd)"
OUT="${ROOT}/out"

if [ -d "${OUT}" ]; then
    echo "[cleanup] rimuovo ${OUT}"
    rm -rf "${OUT}"
fi
