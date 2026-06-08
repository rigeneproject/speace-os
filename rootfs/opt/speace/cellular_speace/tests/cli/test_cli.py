from typer.testing import CliRunner

from speace_core.cli import app

runner = CliRunner()


def test_cli_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "0.9.0" in result.output


def test_cli_status():
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "Status: ready" in result.output
    assert "Version: 0.9.0" in result.output


def test_cli_audit():
    result = runner.invoke(app, ["audit", "--ticks", "1"])
    assert result.exit_code == 0
    assert "Audit complete" in result.output


def test_cli_run_mvp():
    result = runner.invoke(app, ["run-mvp", "--ticks", "2", "--patterns", "1"])
    assert result.exit_code == 0
    assert "Final Metrics" in result.output


def test_cli_seed_aborts_without_yes():
    from unittest.mock import patch

    with patch("builtins.input", return_value="n"):
        result = runner.invoke(app, ["seed"])
    assert result.exit_code == 0
    assert "aborted" in result.output.lower()


def test_cli_seed_help():
    result = runner.invoke(app, ["seed", "--help"])
    assert result.exit_code == 0
    assert "Bootstrap" in result.output
    assert "--repo" in result.output
    assert "--pairing-token" in result.output
