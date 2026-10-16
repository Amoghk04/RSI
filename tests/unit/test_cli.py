from typer.testing import CliRunner

from rsi_harness.cli import app

runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "rsi-harness" in result.stdout.lower() or "harness" in result.stdout


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_validate_config_ci_mock() -> None:
    result = runner.invoke(app, ["validate-config", "configs/ci-mock.yaml"])
    assert result.exit_code == 0
    assert "ci-mock" in result.stdout


def test_run_dry_run() -> None:
    result = runner.invoke(app, ["run", "-c", "configs/ci-mock.yaml", "--dry-run"])
    assert result.exit_code == 0
    assert "dry-run" in result.stdout
