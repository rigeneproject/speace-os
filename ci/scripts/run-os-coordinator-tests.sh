#!/bin/sh
# run-os-coordinator-tests.sh — esegue la suite di test del coordinatore.
# Wrapper usato sia in locale che in CI.

set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${HERE}/../.." && pwd)"
COORD="${ROOT}/os_coordinator"

if [ ! -d "${COORD}" ]; then
    echo "ERRORE: directory os_coordinator non trovata in ${ROOT}"
    exit 1
fi

cd "${COORD}"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    .venv/bin/pip install --quiet --upgrade pip
    .venv/bin/pip install --quiet -e ".[dev]"
fi

.venv/bin/python -m pytest tests/ -v --tb=short --cov=os_coordinator --cov-report=term-missing
