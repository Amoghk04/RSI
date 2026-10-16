"""CLI entry point. Invariant: no paid API calls from `doctor` or default CI."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from rsi_harness import __version__
from rsi_harness.config import load_run_config

app = typer.Typer(
    name="rsi-harness",
    help="Governed harness improvement for LLM agents (frozen weights).",
    no_args_is_help=True,
)
console = Console()


@app.command()
def version() -> None:
    """Print package version."""
    console.print(__version__)


@app.command("validate-config")
def validate_config(
    config: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
) -> None:
    """Parse and validate a YAML run config."""
    cfg = load_run_config(config)
    console.print(f"OK  run_id={cfg.run_id} benchmark={cfg.benchmark.name}")
    console.print(f"    budget total_dollars={cfg.budget.total_dollars}")


@app.command()
def run(
    config: Path = typer.Option(..., "--config", "-c", exists=True, readable=True),
    dry_run: bool = typer.Option(False, help="Load config and exit without calling APIs."),
) -> None:
    """Run the improvement loop (orchestrator wired in M4)."""
    cfg = load_run_config(config)
    if dry_run:
        console.print(f"[yellow]dry-run[/] would run {cfg.run_id} -> {cfg.workdir}")
        raise typer.Exit(0)

    from rsi_harness.runner import run_orchestrator

    state = run_orchestrator(cfg)
    console.print(
        f"[green]done[/] rounds={state.round_index} finalist={state.finalist_harness_id} "
        f"finished={state.finished}"
    )


@app.command("baseline")
def baseline(
    name: str = typer.Argument(..., help="Baseline id: b0, b2, or b3"),
    config: Path = typer.Option(..., "--config", "-c", exists=True, readable=True),
) -> None:
    """Run a dev baseline (B0=eval only; B2/B3=naive loops)."""
    from rsi_harness.baselines import run_baseline

    if name not in {"b0", "b2", "b3"}:
        raise typer.BadParameter("name must be b0, b2, or b3")
    cfg = load_run_config(config)
    path = run_baseline(cfg, name)  # type: ignore[arg-type]
    console.print(f"[green]baseline {name}[/] report -> {path}")


@app.command()
def doctor() -> None:
    """Check local environment (no paid API calls)."""
    ok = True
    if not Path("DESIGN.md").exists():
        console.print("[red]MISS[/] DESIGN.md not found (run from repo root?)")
        ok = False
    else:
        console.print("[green]OK[/]  DESIGN.md present")
    console.print("[green]OK[/]  llm.provider=mock available for CI (set in experiment configs)")
    import os

    tau2_root = os.environ.get("TAU2_BENCH_ROOT")
    if tau2_root and Path(tau2_root).exists():
        console.print(f"[green]OK[/]  TAU2_BENCH_ROOT={tau2_root}")
    else:
        console.print("[yellow]hint[/] set TAU2_BENCH_ROOT for live τ² telecom runs")
    if not ok:
        raise typer.Exit(1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
