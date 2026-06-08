"""Stage 2.5 — Sandbox Autonomy (laboratory) — configuration tests.

These tests verify the sandbox configuration files without requiring
Docker to be installed. They check:

- Required files exist in docker/
- Dockerfile uses non-root user
- docker-compose drops privileges and uses cap_drop
- docker-compose sets memory/cpu/pids limits
- docker-compose sets no-new-privileges and network isolation
- entrypoint refuses to run as root
- entrypoint logs sandbox activation when SPEACE_SANDBOX=1
- systemd unit file is documentation-only and not host-installable
"""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKER_DIR = REPO_ROOT / "docker"


# ------------------------------------------------------------------ #
# File presence
# ------------------------------------------------------------------ #


def test_docker_dir_exists() -> None:
    assert DOCKER_DIR.is_dir(), f"docker/ directory missing: {DOCKER_DIR}"


def test_dockerfile_sandbox_exists() -> None:
    assert (DOCKER_DIR / "Dockerfile.sandbox").is_file()


def test_docker_compose_sandbox_exists() -> None:
    assert (DOCKER_DIR / "docker-compose.sandbox.yml").is_file()


def test_entrypoint_sandbox_exists() -> None:
    assert (DOCKER_DIR / "entrypoint_sandbox.sh").is_file()


def test_systemd_unit_exists() -> None:
    assert (DOCKER_DIR / "speace-lab.service").is_file()


def test_docker_readme_exists() -> None:
    assert (DOCKER_DIR / "README.md").is_file()


# ------------------------------------------------------------------ #
# Dockerfile content
# ------------------------------------------------------------------ #


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_dockerfile_base_image() -> None:
    content = _read(DOCKER_DIR / "Dockerfile.sandbox")
    assert "FROM python:3.12-slim" in content
    # Non deve usare immagini :latest non-pinned (es. ubuntu:latest)
    assert "ubuntu:latest" not in content
    assert "debian:latest" not in content


def test_dockerfile_non_root_user() -> None:
    content = _read(DOCKER_DIR / "Dockerfile.sandbox")
    # deve creare un utente dedicato
    assert re.search(r"useradd\s+--system\s+--uid\s+1001", content), (
        "Dockerfile must create a system user with uid 1001"
    )
    # deve fare USER speace prima di CMD/ENTRYPOINT
    assert re.search(r"^USER\s+speace", content, re.MULTILINE), (
        "Dockerfile must switch to non-root USER before ENTRYPOINT"
    )


def test_dockerfile_uses_tini() -> None:
    content = _read(DOCKER_DIR / "Dockerfile.sandbox")
    assert "tini" in content, "Dockerfile must use tini as PID 1"


def test_dockerfile_no_privileged_instructions() -> None:
    """The Dockerfile itself must not set privileged escalation flags.

    Those belong to docker-compose, not to the Dockerfile.
    """
    content = _read(DOCKER_DIR / "Dockerfile.sandbox")
    # The Dockerfile should not contain 'privileged' as a build instruction
    assert "privileged" not in content.lower() or "privileged=true" not in content.lower()


def test_dockerfile_uses_editable_install() -> None:
    content = _read(DOCKER_DIR / "Dockerfile.sandbox")
    assert "pip install" in content
    assert "-e" in content, "Should install SPEACE in editable mode"


# ------------------------------------------------------------------ #
# docker-compose content
# ------------------------------------------------------------------ #


def test_compose_network_isolated() -> None:
    """Default network must be 'none' to enforce isolation."""
    content = _read(DOCKER_DIR / "docker-compose.sandbox.yml")
    # Either network_mode: none OR a networks section with internal: true
    has_none = "network_mode: none" in content
    has_internal_bridge = "internal: true" in content
    assert has_none or has_internal_bridge, (
        "docker-compose must isolate the network (network_mode: none or internal bridge)"
    )


def test_compose_no_privileged() -> None:
    """Il docker-compose NON deve impostare privileged: true su un servizio attivo.

    La stringa può apparire nei commenti che negano la cosa, ma non deve
    essere una chiave YAML attiva. Verifichiamo rimuovendo le righe di commento.
    """
    content = _read(DOCKER_DIR / "docker-compose.sandbox.yml")
    # Rimuovi le righe di commento per il check effettivo
    active_lines = [
        line for line in content.splitlines()
        if not line.lstrip().startswith("#")
    ]
    active_content = "\n".join(active_lines)
    assert "privileged: true" not in active_content
    assert "privileged:true" not in active_content


def test_compose_no_new_privileges() -> None:
    content = _read(DOCKER_DIR / "docker-compose.sandbox.yml")
    assert "no-new-privileges:true" in content


def test_compose_drops_capabilities() -> None:
    content = _read(DOCKER_DIR / "docker-compose.sandbox.yml")
    assert "cap_drop:" in content
    # deve droppare TUTTO esplicitamente
    assert re.search(r"cap_drop:\s*\n\s*-\s*ALL", content), (
        "docker-compose must explicitly drop ALL capabilities"
    )


def test_compose_resource_limits() -> None:
    content = _read(DOCKER_DIR / "docker-compose.sandbox.yml")
    assert "memory: 2G" in content or "memory:2G" in content
    assert re.search(r"cpus:\s*[\"']?2", content), "cpu limit must be 2"
    assert "pids: 256" in content or "pids:256" in content


def test_compose_no_host_volumes_outside_project() -> None:
    """Le uniche mount dall'host ammesse sono il working dir del progetto."""
    content = _read(DOCKER_DIR / "docker-compose.sandbox.yml")
    # Bandire mount pericolosi tipici
    forbidden_mounts = [
        "/:",
        "/etc:",
        "/var:",
        "/root:",
        "/home:",
        "/boot:",
        "/sys:",
        "/proc:",
    ]
    for forbidden in forbidden_mounts:
        assert forbidden not in content, (
            f"docker-compose must not mount {forbidden} from host"
        )


def test_compose_speace_sandbox_env_var() -> None:
    """The compose must read SPEACE_SANDBOX from env (default 0)."""
    content = _read(DOCKER_DIR / "docker-compose.sandbox.yml")
    assert "SPEACE_SANDBOX" in content
    assert "${SPEACE_SANDBOX:-0}" in content, (
        "SPEACE_SANDBOX must default to 0 (safe mode)"
    )


def test_compose_healthcheck() -> None:
    content = _read(DOCKER_DIR / "docker-compose.sandbox.yml")
    assert "healthcheck:" in content


# ------------------------------------------------------------------ #
# Entrypoint content
# ------------------------------------------------------------------ #


def test_entrypoint_is_executable() -> None:
    p = DOCKER_DIR / "entrypoint_sandbox.sh"
    if os.name == "posix":
        mode = p.stat().st_mode
        assert mode & stat.S_IXUSR, "entrypoint must be executable by owner"
        assert mode & stat.S_IXGRP, "entrypoint must be executable by group"
    else:
        # On Windows, the file is checked in via Write; execution is via the
        # container's tini/busybox. We don't enforce POSIX bits on Windows.
        pytest.skip("executable bits not enforced on Windows")


def test_entrypoint_refuses_root() -> None:
    content = _read(DOCKER_DIR / "entrypoint_sandbox.sh")
    assert 'id -u' in content
    assert "root" in content.lower()
    # Deve fallire se è root
    assert "exit 1" in content


def test_entrypoint_detects_container() -> None:
    content = _read(DOCKER_DIR / "entrypoint_sandbox.sh")
    # Cerca il marker /.dockerenv o /proc/1/cgroup
    assert "/.dockerenv" in content or "cgroup" in content


def test_entrypoint_logs_sandbox_activation() -> None:
    content = _read(DOCKER_DIR / "entrypoint_sandbox.sh")
    assert "SPEACE_SANDBOX" in content
    assert "activations.jsonl" in content
    # Deve scrivere un record JSON con timestamp e run_id
    assert "timestamp" in content
    assert "run_id" in content


def test_entrypoint_default_safe_mode() -> None:
    """If SPEACE_SANDBOX is not set, the default must be safe (0)."""
    content = _read(DOCKER_DIR / "entrypoint_sandbox.sh")
    assert 'SPEACE_SANDBOX:-0' in content or 'SPEACE_SANDBOX:-"0"' in content


# ------------------------------------------------------------------ #
# Systemd unit
# ------------------------------------------------------------------ #


def test_systemd_unit_documentation_only() -> None:
    """The unit file must declare itself as container-only and not installable on host."""
    content = _read(DOCKER_DIR / "speace-lab.service")
    # Deve dichiarare esplicitamente che è solo per il container
    assert "DENTRO IL CONTAINER" in content or "container" in content.lower()
    # Non deve avere path dell'host hard-coded
    forbidden_host_paths = ["/home/", "/Users/", "C:\\"]
    for forbidden in forbidden_host_paths:
        assert forbidden not in content, (
            f"systemd unit must not reference host path {forbidden}"
        )


def test_systemd_unit_hardening() -> None:
    content = _read(DOCKER_DIR / "speace-lab.service")
    hardening_options = [
        "NoNewPrivileges=true",
        "PrivateTmp=true",
        "ProtectSystem=strict",
        "ProtectHome=true",
    ]
    for opt in hardening_options:
        assert opt in content, f"systemd unit missing hardening option {opt}"


# ------------------------------------------------------------------ #
# README / documentation
# ------------------------------------------------------------------ #


def test_readme_documents_verification_commands() -> None:
    content = _read(DOCKER_DIR / "README.md")
    assert "docker inspect" in content
    assert "Privileged" in content or "privileged" in content
    # deve indicare i comandi di verifica del perimetro
    assert "Capability" in content or "CapAdd" in content


def test_readme_documents_invariants() -> None:
    content = _read(DOCKER_DIR / "README.md")
    # Deve elencare cosa NON è permesso
    assert "Niente" in content or "❌" in content
    # Deve elencare cosa È permesso
    assert "✅" in content


# ------------------------------------------------------------------ #
# Perimetro: nessun file di docker/ deve poter essere eseguito sull'host
# ------------------------------------------------------------------ #


def test_no_executable_on_windows() -> None:
    """Su Windows, i file in docker/ non devono avere extension eseguibile."""
    if os.name != "nt":
        pytest.skip("Windows-specific check")
    for p in DOCKER_DIR.iterdir():
        if p.suffix.lower() in {".exe", ".bat", ".cmd", ".ps1"}:
            pytest.fail(f"Unexpected executable in docker/: {p.name}")
