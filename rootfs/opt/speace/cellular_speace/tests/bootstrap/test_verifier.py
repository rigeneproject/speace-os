"""Tests for bootstrap package verifier (T115)."""

import pytest

from speace_core.bootstrap.verifier import HashAllowlist, PackageVerifier


def test_allowlist_add_and_check():
    allowlist = HashAllowlist()
    allowlist.add_hash("https://github.com/rigeneproject/cellular_speace", "abc123")
    assert allowlist.is_approved("https://github.com/rigeneproject/cellular_speace", "abc123")
    assert not allowlist.is_approved("https://github.com/other/repo", "abc123")
    assert not allowlist.is_approved("https://github.com/rigeneproject/cellular_speace", "def456")


def test_allowlist_short_hash():
    allowlist = HashAllowlist()
    allowlist.add_hash("https://github.com/rigeneproject/cellular_speace", "abc123def456")
    assert allowlist.is_approved("https://github.com/rigeneproject/cellular_speace", "abc123")
    assert allowlist.is_approved("https://github.com/rigeneproject/cellular_speace", "abc123def456")


def test_allowlist_repo_allowed():
    allowlist = HashAllowlist()
    assert allowlist.repo_allowed("https://github.com/rigeneproject/cellular_speace")
    assert not allowlist.repo_allowed("https://github.com/other/repo")


def test_verifier_file_hash(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello speace")
    verifier = PackageVerifier()
    h = verifier.compute_file_hash(test_file)
    assert len(h) == 64  # sha256 hex length
    assert verifier.verify_file(test_file, h)
    assert not verifier.verify_file(test_file, "0" * 64)


def test_verifier_bytes_hash():
    verifier = PackageVerifier()
    h = verifier.compute_bytes_hash(b"hello")
    assert len(h) == 64


def test_verifier_repo_hash_approved():
    allowlist = HashAllowlist()
    allowlist.add_hash("https://github.com/rigeneproject/cellular_speace", "deadbeef")
    verifier = PackageVerifier(allowlist)
    assert verifier.verify_repo_hash("https://github.com/rigeneproject/cellular_speace", "deadbeef")


def test_verifier_repo_hash_unapproved_repo():
    verifier = PackageVerifier()
    assert not verifier.verify_repo_hash("https://github.com/other/repo", "deadbeef")
