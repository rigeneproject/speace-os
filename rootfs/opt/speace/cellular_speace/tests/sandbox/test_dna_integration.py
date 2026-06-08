"""Stage 2.5 — Sandbox Autonomy — DNA integration tests.

These tests verify that Stage 2.5 (Sandboxed Lab Autonomy) has been
correctly integrated into the SPEACE DNA (genome) and that the
sandbox profile exists and is well-formed.

Specifically:
- species_orientation.yaml declares stage_2_5 with the right name
- species_orientation.yaml lists the 3 required invariants
- bootstrap.yaml has the safe-mode comment at the top
- sandbox/sandbox_profile.yaml exists
- sandbox_profile.yaml has activation.required_env == "SPEACE_SANDBOX=1"
- sandbox_profile.yaml has hard_limits.no_network_bind_outside_container == True
- sandbox_profile.yaml lists >= 3 fragments in always_blocked_fragments
- sandbox/__init__.py exists
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
GENOME_CORE = REPO_ROOT / "speace_core" / "dna" / "genome" / "core"
BOOTSTRAP_YAML = REPO_ROOT / "speace_core" / "dna" / "genome" / "bootstrap.yaml"
SPECIES_YAML = GENOME_CORE / "species_orientation.yaml"
SANDBOX_DIR = REPO_ROOT / "sandbox"
SANDBOX_PROFILE_YAML = SANDBOX_DIR / "sandbox_profile.yaml"
SANDBOX_INIT_PY = SANDBOX_DIR / "__init__.py"


# ------------------------------------------------------------------ #
# File presence
# ------------------------------------------------------------------ #


def test_species_orientation_yaml_exists() -> None:
    assert SPECIES_YAML.is_file(), f"species_orientation.yaml missing: {SPECIES_YAML}"


def test_bootstrap_yaml_exists() -> None:
    assert BOOTSTRAP_YAML.is_file(), f"bootstrap.yaml missing: {BOOTSTRAP_YAML}"


def test_sandbox_dir_exists() -> None:
    assert SANDBOX_DIR.is_dir(), f"sandbox/ directory missing: {SANDBOX_DIR}"


def test_sandbox_profile_yaml_exists() -> None:
    assert SANDBOX_PROFILE_YAML.is_file(), (
        f"sandbox_profile.yaml missing: {SANDBOX_PROFILE_YAML}"
    )


def test_sandbox_init_py_exists() -> None:
    assert SANDBOX_INIT_PY.is_file(), f"sandbox/__init__.py missing: {SANDBOX_INIT_PY}"


# ------------------------------------------------------------------ #
# species_orientation.yaml: stage_2_5
# ------------------------------------------------------------------ #


@pytest.fixture(scope="module")
def species_orientation() -> dict:
    with SPECIES_YAML.open("r", encoding="utf-8") as f:
        loaded = yaml.safe_load(f)
    # The YAML wraps the document under the 'species_orientation' top-level key.
    # We expose the inner mapping so tests can directly assert on stage_2_5 etc.
    assert isinstance(loaded, dict)
    assert "species_orientation" in loaded, (
        "species_orientation.yaml must have a 'species_orientation' top-level key"
    )
    return loaded["species_orientation"]


def test_species_orientation_has_stage_2_5(species_orientation: dict) -> None:
    assert "stage_2_5" in species_orientation, (
        "species_orientation.yaml must define stage_2_5"
    )


def test_species_orientation_stage_2_5_name(species_orientation: dict) -> None:
    stage = species_orientation.get("stage_2_5")
    assert isinstance(stage, dict), "stage_2_5 must be a mapping"
    assert stage.get("name") == "Sandboxed Lab Autonomy", (
        f"stage_2_5.name must be 'Sandboxed Lab Autonomy', got: {stage.get('name')!r}"
    )


def test_species_orientation_stage_2_5_invariants(species_orientation: dict) -> None:
    """The 3 required invariants must be listed as strings."""
    stage = species_orientation.get("stage_2_5")
    assert isinstance(stage, dict), "stage_2_5 must be a mapping"
    invariants = stage.get("invariants")
    assert isinstance(invariants, list), "stage_2_5.invariants must be a list"
    assert len(invariants) >= 3, (
        f"stage_2_5 must list at least 3 invariants, found {len(invariants)}"
    )
    joined = "\n".join(str(x) for x in invariants)

    required_substrings = [
        "internal guardrails",
        "logged persistently",
        "device passthrough",
    ]
    for needle in required_substrings:
        assert needle in joined, (
            f"stage_2_5.invariants must mention '{needle}'. Got: {invariants!r}"
        )

    # Tutti gli invarianti devono essere stringhe
    for inv in invariants:
        assert isinstance(inv, str), f"each invariant must be a string, got {type(inv)}"


# ------------------------------------------------------------------ #
# bootstrap.yaml: safe-mode comment
# ------------------------------------------------------------------ #


def test_bootstrap_has_safe_mode_comment() -> None:
    text = BOOTSTRAP_YAML.read_text(encoding="utf-8")
    # Il commento YAML inizia con '#'. Deve menzionare SAFE MODE e SPEACE_SANDBOX.
    lines = text.splitlines()
    # Prendiamo le prime 30 righe: il commento è "in cima"
    top = "\n".join(lines[:30])
    assert "SAFE MODE" in top.upper() or "SAFE MODE" in top, (
        "bootstrap.yaml must have a SAFE MODE comment at the top"
    )
    assert "SPEACE_SANDBOX" in top, (
        "bootstrap.yaml comment must mention SPEACE_SANDBOX=1 opt-in"
    )
    # Deve iniziare con un commento (la prima riga non-vuota è '#' o il file
    # inizia con righe di commento)
    first_non_empty = next((ln for ln in lines if ln.strip()), "")
    assert first_non_empty.lstrip().startswith("#"), (
        "bootstrap.yaml must start with a YAML comment about safe mode"
    )


def test_bootstrap_yaml_still_loads() -> None:
    """The added comment must not break YAML parsing."""
    with BOOTSTRAP_YAML.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert isinstance(data, dict)
    assert "speace_bootstrap_dna" in data


# ------------------------------------------------------------------ #
# sandbox_profile.yaml: structure
# ------------------------------------------------------------------ #


@pytest.fixture(scope="module")
def sandbox_profile() -> dict:
    with SANDBOX_PROFILE_YAML.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_sandbox_profile_root(sandbox_profile: dict) -> None:
    assert "sandbox_profile" in sandbox_profile, (
        "sandbox_profile.yaml must be wrapped in a 'sandbox_profile' top-level key"
    )
    sp = sandbox_profile["sandbox_profile"]
    assert isinstance(sp, dict)
    assert sp.get("name") == "lab_sandbox"
    assert "version" in sp


def test_sandbox_profile_required_env(sandbox_profile: dict) -> None:
    sp = sandbox_profile["sandbox_profile"]
    activation = sp.get("activation")
    assert isinstance(activation, dict), "activation must be a mapping"
    assert activation.get("required_env") == "SPEACE_SANDBOX=1", (
        f"activation.required_env must be 'SPEACE_SANDBOX=1', got: "
        f"{activation.get('required_env')!r}"
    )


def test_sandbox_profile_hard_limits_no_network(sandbox_profile: dict) -> None:
    sp = sandbox_profile["sandbox_profile"]
    hard = sp.get("hard_limits")
    assert isinstance(hard, dict), "hard_limits must be a mapping"
    assert hard.get("no_network_bind_outside_container") is True, (
        "hard_limits.no_network_bind_outside_container must be True"
    )


def test_sandbox_profile_always_blocked_fragments(sandbox_profile: dict) -> None:
    sp = sandbox_profile["sandbox_profile"]
    ext = sp.get("extended_capabilities", {})
    actuator = ext.get("actuator", {}) if isinstance(ext, dict) else {}
    fragments = actuator.get("always_blocked_fragments")
    assert isinstance(fragments, list), "always_blocked_fragments must be a list"
    assert len(fragments) >= 3, (
        f"always_blocked_fragments must list at least 3 items, found {len(fragments)}"
    )
    for f in fragments:
        assert isinstance(f, str) and f.strip(), (
            f"each blocked fragment must be a non-empty string, got {f!r}"
        )


def test_sandbox_profile_extended_capabilities_unsafe_free() -> None:
    """Le allowed_cmd_patterns NON devono contenere comandi distruttivi."""
    import re as _re

    with SANDBOX_PROFILE_YAML.open("r", encoding="utf-8") as f:
        raw = f.read()
    # Nessun pattern "pericoloso" tra le allowed_cmd_patterns
    # (sono commenti che le escludono esplicitamente, non patterns attivi)
    dangerous = ["rm\\s", "del\\s", "format\\s", "dd\\s", "mkfs", "sudo"]
    # Cerchiamo SOLO dentro al blocco extended_capabilities -> additional_allowed_cmd_patterns
    m = _re.search(
        r"additional_allowed_cmd_patterns:\s*\n((?:\s*-\s*\S.*\n)+)",
        raw,
    )
    if m is None:
        pytest.fail("additional_allowed_cmd_patterns block not found")
    block = m.group(1)
    for d in dangerous:
        assert not _re.search(d, block), (
            f"additional_allowed_cmd_patterns must not include dangerous token {d!r}"
        )
