import asyncio
import datetime
import pathlib
from typing import Optional

import typer

from speace_core.dna.parser import load_genome
from speace_core.orchestrator import CellularBrainOrchestrator

app = typer.Typer(name="speace", help="SPEACE Cellular Brain CLI")

SPEACE_VERSION = "0.9.0"


def _default_genome_path() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent / "dna" / "genome" / "default_genome.yaml"


@app.command()
def version() -> None:
    """Show SPEACE version."""
    typer.echo(f"speace-core {SPEACE_VERSION}")


@app.command()
def status(
    genome_path: Optional[pathlib.Path] = typer.Option(
        None, "--genome", "-g", help="Path to genome YAML"
    ),
) -> None:
    """Show SPEACE system status."""
    if genome_path is None:
        genome_path = _default_genome_path()
    genome = load_genome(genome_path)
    identity = getattr(genome, "identity", {}) or {}
    species = getattr(identity, "entity_name", "SPEACE")
    stage = getattr(identity, "nature", "unknown")
    typer.echo(f"System: {species}")
    typer.echo(f"Version: {SPEACE_VERSION}")
    typer.echo(f"Stage: {stage}")
    typer.echo(f"Genome: {genome_path.name}")
    typer.echo("Status: ready")


@app.command()
def audit(
    genome_path: Optional[pathlib.Path] = typer.Option(
        None, "--genome", "-g", help="Path to genome YAML"
    ),
    ticks: int = typer.Option(10, "--ticks", "-t", help="Number of audit ticks"),
) -> None:
    """Run a quick system audit."""
    if genome_path is None:
        genome_path = _default_genome_path()
    genome = load_genome(genome_path)
    orchestrator = CellularBrainOrchestrator.build_mvp(genome)

    async def _run() -> None:
        typer.echo("Starting audit...")
        await orchestrator.run_ticks(ticks)
        metrics = orchestrator.latest_metrics
        if metrics:
            typer.echo(f"Tick: {metrics.tick}")
            typer.echo(f"Coherence Phi: {metrics.coherence_phi:.4f}")
            typer.echo(f"Mean Energy: {metrics.mean_energy:.4f}")
            typer.echo(f"Active Neurons: {metrics.active_neurons}")
            typer.echo(f"Pruned Synapses: {metrics.pruned_synapses}")
        typer.echo("Audit complete.")

    asyncio.run(_run())


@app.command()
def run_mvp(
    ticks: int = typer.Option(1000, "--ticks", "-t", help="Number of ticks to run"),
    genome_path: Optional[pathlib.Path] = typer.Option(
        None, "--genome", "-g", help="Path to genome YAML"
    ),
    patterns: int = typer.Option(100, "--patterns", "-p", help="Training patterns"),
) -> None:
    """Run the SPEACE MVP cellular brain."""
    if genome_path is None:
        genome_path = _default_genome_path()
    genome = load_genome(genome_path)
    orchestrator = CellularBrainOrchestrator.build_mvp(genome)

    async def _run() -> None:
        typer.echo(f"Starting SPEACE MVP for {ticks} ticks...")
        for i in range(patterns):
            pattern = [0.0] * 10
            pattern[i % 10] = 1.0
            orchestrator.inject(pattern)
            await orchestrator.run_ticks(1)
            score = 1.0 if i % 2 == 0 else -0.2
            orchestrator.feedback(score)
            if i % 10 == 0:
                orchestrator.run_immune()
            metrics = orchestrator.latest_metrics
            if metrics:
                typer.echo(
                    f"Tick {metrics.tick:04d} | "
                    f"Phi={metrics.coherence_phi:.3f} | "
                    f"Energy={metrics.mean_energy:.3f} | "
                    f"Active={metrics.active_neurons} | "
                    f"Pruned={metrics.pruned_synapses}"
                )
        # final burn-in
        await orchestrator.run_ticks(ticks - patterns)
        final = orchestrator.latest_metrics
        if final:
            typer.echo("\n=== Final Metrics ===")
            typer.echo(f"Tick: {final.tick}")
            typer.echo(f"Coherence Phi: {final.coherence_phi:.4f}")
            typer.echo(f"Mean Energy: {final.mean_energy:.4f}")
            typer.echo(f"Active Neurons: {final.active_neurons}")
            typer.echo(f"Pruned Synapses: {final.pruned_synapses}")

    asyncio.run(_run())


@app.command()
def ignite(
    genome_path: Optional[pathlib.Path] = typer.Option(
        None, "--genome", "-g", help="Path to genome YAML"
    ),
    warmup: int = typer.Option(60, "--warmup", "-w", help="Warmup stimulation patterns"),
    sustain: int = typer.Option(200, "--sustain", "-s", help="Sustain ticks (keep-alive)"),
) -> None:
    """Accende e avvia cervello + organismo (ILF integrato, sblocco stallo)."""
    from speace_core.bootstrap.ignition import OrganismIgnition

    igniter = OrganismIgnition(
        genome_path=genome_path,
        warmup_patterns=warmup,
        sustain_ticks=sustain,
    )
    rep = igniter.ignite()
    for line in rep["log"]:
        typer.echo(line)
    typer.echo("\n=== Stato Organismo ===")
    typer.echo(f"Vivo: {rep['alive']}")
    typer.echo(f"Tick: {rep['tick']}")
    phi = rep["coherence_phi"]
    typer.echo(f"Coherence Phi: {phi:.4f}" if phi is not None else "Coherence Phi: n/a")
    en = rep["mean_energy"]
    typer.echo(f"Mean Energy: {en:.4f}" if en is not None else "Mean Energy: n/a")
    typer.echo(f"Active Neurons: {rep['active_neurons']}")
    typer.echo(f"Systemic Coherence Index: {rep['systemic_coherence_index']:.4f}")
    ilf = rep["ilf_value"]
    typer.echo(f"ILF Value: {ilf:.4f}" if ilf is not None else "ILF Value: n/a")
    typer.echo(f"Sottosistemi nel campo: {', '.join(rep['field_subsystems'])}")
    typer.echo(f"Snapshot persistiti: {rep['snapshots_persisted']}")


@app.command()
def live(
    cycle_interval: float = typer.Option(
        300.0, "--cycle-interval", "-c", help="Secondi tra i cicli del team non-LLM"
    ),
    tick_interval: float = typer.Option(
        1.0, "--tick-interval", "-t", help="Secondi tra i tick del cervello"
    ),
    dashboards: bool = typer.Option(
        False, "--dashboards", help="Avvia anche le dashboard web del daemon"
    ),
) -> None:
    """Avvia cervello/organismo 24/7 + team agentico NON-LLM (auto-miglioramento)."""
    from evolution_daemon.launcher import LiveOrganism
    import asyncio as _asyncio

    organism = LiveOrganism(
        cycle_interval_sec=cycle_interval,
        tick_interval=tick_interval,
        start_dashboards=dashboards,
    )
    try:
        _asyncio.run(organism.run())
    except KeyboardInterrupt:
        typer.echo("Interrotto da tastiera.")


@app.command()
def dashboard() -> None:
    """Launch the SPEACE organismic web dashboard."""
    try:
        from speace_core.dashboard.server import run_server
    except ImportError as exc:
        typer.echo("Error: Flask is not installed.")
        typer.echo("Install it with: pip install \"speace-core[dashboard]\"")
        raise typer.Exit(1) from exc
    typer.echo("Starting SPEACE dashboard at http://127.0.0.1:8080")
    run_server(host="127.0.0.1", port=8080)


@app.command()
def monitor(
    genome_path: Optional[pathlib.Path] = typer.Option(
        None, "--genome", "-g", help="Path to genome YAML"
    ),
) -> None:
    """Launch the SPEACE Local Organism Monitor (T101)."""
    try:
        import uvicorn
    except ImportError as exc:
        typer.echo("Error: uvicorn is not installed.")
        typer.echo('Install with: pip install "speace-core[monitoring]"')
        raise typer.Exit(1) from exc

    host = "127.0.0.1"
    port = 8787

    if genome_path is None:
        genome_path = (
            pathlib.Path(__file__).resolve().parent
            / "dna"
            / "genome"
            / "monitoring_dashboard.yaml"
        )
    if genome_path.exists():
        try:
            genome = load_genome(genome_path)
            md = getattr(genome, "monitoring_dashboard", {}) or {}
            host = md.get("host", host)
            port = md.get("port", port)
        except Exception as exc:
            import logging
            logging.getLogger("speace.cli").warning(
                "Failed to load monitoring_dashboard genome config: %s", exc, exc_info=True
            )

    typer.echo(f"Starting SPEACE monitor at http://{host}:{port}")
    uvicorn.run(
        "speace_core.monitoring.dashboard_api:app",
        host=host,
        port=port,
        log_level="info",
    )


@app.command()
def run(
    genome_path: Optional[pathlib.Path] = typer.Option(
        None, "--genome", "-g", help="Path to genome YAML"
    ),
    tick_interval: float = typer.Option(1.0, "--tick-interval", "-t", help="Seconds between ticks"),
    duration: Optional[float] = typer.Option(
        None, "--duration", "-d", help="Optional runtime duration in seconds (for testing)"
    ),
) -> None:
    """Launch SPEACE controlled continuous runtime + monitor (T109)."""
    try:
        import uvicorn
    except ImportError as exc:
        typer.echo("Error: uvicorn is not installed.")
        typer.echo('Install with: pip install "speace-core[monitoring]"')
        raise typer.Exit(1) from exc

    # Resolve genome
    if genome_path is None:
        genome_path = pathlib.Path(__file__).resolve().parent / "dna" / "genome" / "default_genome.yaml"
    genome = load_genome(genome_path)

    # Build orchestrator and runtime engine
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.runtime.continuous_runtime_engine import ContinuousRuntimeEngine
    import speace_core.monitoring.dashboard_api as dashboard_module

    orchestrator = CellularBrainOrchestrator.build_mvp(genome)
    runtime = ContinuousRuntimeEngine(
        orchestrator=orchestrator,
        tick_interval=tick_interval,
    )
    dashboard_module._runtime_engine = runtime  # type: ignore[attr-defined]

    async def _start_runtime() -> None:
        result = await runtime.start()
        typer.echo(f"Runtime started: {result['state']} | recovery: {result['recovery']['status']}")
        typer.echo(result.get("resume_narrative", ""))
        if duration is not None:
            typer.echo(f"Running for {duration} seconds...")
            await asyncio.sleep(duration)
            typer.echo("Duration reached. Halting runtime...")
            await runtime.halt()
            await runtime.stop()
            typer.echo("Runtime stopped.")

    # Launch runtime in background and then uvicorn
    async def _main() -> None:
        runtime_task = asyncio.create_task(_start_runtime())
        host = "127.0.0.1"
        port = 8787
        config = uvicorn.Config(
            "speace_core.monitoring.dashboard_api:app",
            host=host,
            port=port,
            log_level="info",
        )
        server = uvicorn.Server(config)
        server_task = asyncio.create_task(server.serve())
        await asyncio.wait([runtime_task, server_task], return_when=asyncio.FIRST_COMPLETED)
        server.should_exit = True
        await server_task

    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        typer.echo("Interrupted by user.")


@app.command()
def seed(
    repo: Optional[str] = typer.Option(
        None, "--repo", help="GitHub repo URL"
    ),
    branch: str = typer.Option("main", "--branch", help="Git branch"),
    target_dir: Optional[pathlib.Path] = typer.Option(
        None, "--target", help="Installation directory"
    ),
    pairing_token: Optional[str] = typer.Option(
        None, "--pairing-token", help="Token to pair with existing node"
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip confirmation prompts"
    ),
) -> None:
    """Bootstrap a new SPEACE node (authorized installation only — T115)."""
    from speace_core.bootstrap import SeedEngine

    engine = SeedEngine(
        repo=repo,
        branch=branch,
        target_dir=target_dir,
        pairing_token=pairing_token,
    )
    result = engine.bootstrap(skip_confirm=yes)
    if result["status"] == "success":
        typer.echo(f"Bootstrap complete. Node ID: {result['node_id']}")
        typer.echo(f"Clone path: {result['clone_path']}")
        typer.echo("Run 'speace monitor' to start in safe mode.")
    elif result["status"] == "aborted":
        typer.echo("Bootstrap aborted by user.")
    else:
        typer.echo(f"Bootstrap failed: {result.get('reason', 'unknown')}")
        for err in result.get("errors", []):
            typer.echo(f"  Error: {err}")


@app.command()
def report(
    lookback: int = typer.Option(24, "--lookback", "-l", help="Hours to look back"),
    output_dir: pathlib.Path = typer.Option(
        "reports/observer", "--output", "-o", help="Output directory"
    ),
    format: str = typer.Option(
        "both", "--format", "-f", help="Output format: json, md, or both"
    ),
) -> None:
    """Generate a T103 observer report from organismic state and history."""
    from speace_core.monitoring.observer_report_generator import ObserverReportGenerator

    generator = ObserverReportGenerator()
    rep = generator.generate(lookback_hours=lookback)

    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")

    if format in ("json", "both"):
        json_path = output_dir / f"observer_report_{ts}.json"
        json_path.write_text(rep.model_dump_json(indent=2), encoding="utf-8")
        typer.echo(f"JSON report written to: {json_path}")

    if format in ("md", "both"):
        md_path = output_dir / f"observer_report_{ts}.md"
        md_path.write_text(rep.to_markdown(), encoding="utf-8")
        typer.echo(f"Markdown report written to: {md_path}")

    typer.echo(f"Verdict: {rep.verdict}")
    typer.echo(f"Health Score: {rep.alert_summary.health_score_current:.4f}")
    typer.echo(f"Alerts (critical/warning): {rep.alert_summary.critical_count}/{rep.alert_summary.warning_count}")
    if rep.recommendations:
        typer.echo("Recommendations:")
        for rec in rep.recommendations:
            typer.echo(f"  - [{rec.category}] {rec.message}")


@app.command()
def assimilate(
    genome_path: Optional[pathlib.Path] = typer.Option(
        None, "--genome", "-g", help="Path to genome YAML"
    ),
) -> None:
    """Assimila il sistema Windows (processi, servizi, dispositivi, storage)."""
    if genome_path is None:
        genome_path = _default_genome_path()
    genome = load_genome(genome_path)
    from speace_core.cellular_brain.system_assimilation import WindowsSystemAssimilator
    from speace_core.cellular_brain.system_assimilation.assimilation_models import SystemAssimilationConfig
    assimilator = WindowsSystemAssimilator(config=SystemAssimilationConfig(
        enable_assimilation=True, allow_wmi_queries=True,
    ))
    report = assimilator.assimilate()
    typer.echo(f"System: {report.system_info.hostname}")
    typer.echo(f"OS: {report.system_info.os_platform} {report.system_info.os_release}")
    typer.echo(f"Arch: {report.system_info.architecture}")
    typer.echo(f"Admin: {report.system_info.is_admin}")
    typer.echo(f"Processes: {report.process_count}")
    typer.echo(f"Services: {report.service_count}")
    typer.echo(f"Devices: {report.device_count}")
    typer.echo(f"Storage:")
    for d in report.storage_devices:
        size_gb = d.get("size_bytes", 0) / (1024**3)
        free_gb = d.get("free_bytes", 0) / (1024**3)
        typer.echo(f"  {d.get('device_id', '?')}: {free_gb:.1f} GB free / {size_gb:.1f} GB total")
    typer.echo("Assimilation complete.")


@app.command()
def vfs_index(
    genome_path: Optional[pathlib.Path] = typer.Option(
        None, "--genome", "-g", help="Path to genome YAML"
    ),
) -> None:
    """Indicizza la root del computer via VFS (senza duplicare file)."""
    if genome_path is None:
        genome_path = _default_genome_path()
    genome = load_genome(genome_path)
    genome_sa = getattr(genome, "system_assimilation", None)
    if genome_sa is None or not getattr(genome_sa, "enable_vfs", False):
        typer.echo("VFS not enabled in genome. Set system_assimilation.enable_vfs: true")
        raise typer.Exit(1)
    from speace_core.cellular_brain.virtual_file_system import VirtualFileSystemEngine
    from speace_core.cellular_brain.virtual_file_system.vfs_models import VFSConfig, AccessRule, VFSPermission
    rules = []
    for r in getattr(genome_sa, "access_rules", []):
        perms = []
        for p in r.allowed_permissions:
            try:
                perms.append(VFSPermission[p.upper()])
            except KeyError:
                pass
        rules.append(AccessRule(
            rule_id=f"dna_{r.path_prefix}",
            path_prefix=r.path_prefix,
            allowed_permissions=perms,
            allowed=not r.requires_approval or r.approved,
            requires_approval=r.requires_approval,
            approved=r.approved,
        ))
    vfs_config = VFSConfig(
        root_mount_point=getattr(genome_sa, "root_mount_point", "C:\\"),
        speace_install_path="C:\\cellular_speace",
        access_rules=rules,
        enable_vfs=True,
    )
    engine = VirtualFileSystemEngine(config=vfs_config)
    result = engine.index_root()
    typer.echo(f"Root: {result['root']}")
    typer.echo(f"Indexed: {result['indexed']} entries")
    typer.echo(f"Errors: {result['errors']}")
    typer.echo(f"Total in index: {result['total_indexed']}")
    typer.echo("VFS index created. Files are NOT duplicated — only metadata mapped.")


@app.command()
def vfs_ls(
    path: str = typer.Argument(".", help="Virtual path to list"),
    genome_path: Optional[pathlib.Path] = typer.Option(
        None, "--genome", "-g", help="Path to genome YAML"
    ),
) -> None:
    """Elenca una directory della root via VFS."""
    if genome_path is None:
        genome_path = _default_genome_path()
    genome = load_genome(genome_path)
    genome_sa = getattr(genome, "system_assimilation", None)
    if genome_sa is None or not getattr(genome_sa, "enable_vfs", False):
        typer.echo("VFS not enabled in genome.")
        raise typer.Exit(1)
    from speace_core.cellular_brain.virtual_file_system import VirtualFileSystemEngine
    from speace_core.cellular_brain.virtual_file_system.vfs_models import VFSConfig, AccessRule, VFSPermission
    rules = []
    for r in getattr(genome_sa, "access_rules", []):
        perms = []
        for p in r.allowed_permissions:
            try:
                perms.append(VFSPermission[p.upper()])
            except KeyError:
                pass
        rules.append(AccessRule(
            rule_id=f"dna_{r.path_prefix}", path_prefix=r.path_prefix,
            allowed_permissions=perms, allowed=not r.requires_approval or r.approved,
            requires_approval=r.requires_approval, approved=r.approved,
        ))
    vfs_config = VFSConfig(
        root_mount_point=getattr(genome_sa, "root_mount_point", "C:\\"),
        speace_install_path="C:\\cellular_speace",
        access_rules=rules, enable_vfs=True,
    )
    engine = VirtualFileSystemEngine(config=vfs_config)
    entries = engine.list_directory(path)
    if entries is None:
        typer.echo(f"Permission denied or path not found: {path}")
        raise typer.Exit(1)
    for e in entries:
        kind = "D" if e.get("is_dir") else "F"
        size = e.get("size_bytes", 0)
        name = e.get("name", "?")
        err = e.get("error", "")
        if err:
            typer.echo(f"[{kind}] {name}  ({err})")
        else:
            typer.echo(f"[{kind}] {name}  {size} bytes")


if __name__ == "__main__":
    app()
