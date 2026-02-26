"""CLI entry point for agentcore-sdk.

Invoked as::

    agentcore-sdk [OPTIONS] COMMAND [ARGS]...

or, during development::

    python -m agentcore.cli.main
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()
error_console = Console(stderr=True, style="bold red")


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------


@click.group()
@click.version_option()
def cli() -> None:
    """Agent substrate: event schemas, identity, telemetry bridge, plugin registry"""


# ---------------------------------------------------------------------------
# version
# ---------------------------------------------------------------------------


@cli.command(name="version")
def version_command() -> None:
    """Show detailed version information."""
    from agentcore import __version__

    console.print(f"[bold]agentcore-sdk[/bold] v{__version__}")
    console.print(f"Python {sys.version}")


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


@cli.command(name="init")
@click.option(
    "--directory",
    "-d",
    default=".",
    show_default=True,
    help="Directory in which to create the config file.",
)
def init_command(directory: str) -> None:
    """Initialise an agentcore config file in DIRECTORY."""
    target_dir = Path(directory).resolve()
    config_path = target_dir / "agentcore.yaml"

    if config_path.exists():
        console.print(
            f"[yellow]Config already exists at {config_path}. Skipping.[/yellow]"
        )
        return

    default_yaml = """\
# agentcore configuration
agent_name: my-agent
agent_version: "0.1.0"
framework: custom
model: claude-sonnet-4-5
telemetry_enabled: true
cost_tracking_enabled: true
event_bus_enabled: true
plugins: []
custom_settings: {}
"""
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        config_path.write_text(default_yaml, encoding="utf-8")
        console.print(f"[green]Created agentcore config at {config_path}[/green]")
    except OSError as exc:
        error_console.print(f"Failed to create config: {exc}")
        raise SystemExit(1) from exc


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


@cli.command(name="status")
@click.option(
    "--config",
    "-c",
    default=None,
    help="Path to agentcore config file.",
)
def status_command(config: str | None) -> None:
    """Show agentcore status (identity, event bus, telemetry)."""
    from agentcore.config.loader import ConfigLoader

    loader = ConfigLoader()
    try:
        if config:
            cfg = loader.load_yaml(config)
        else:
            cfg = loader.load_auto()
    except Exception as exc:  # noqa: BLE001
        error_console.print(f"Could not load config: {exc}")
        raise SystemExit(1) from exc

    table = Table(title="agentcore status", show_header=True, header_style="bold cyan")
    table.add_column("Setting", style="dim")
    table.add_column("Value")

    table.add_row("agent_name", cfg.agent_name)
    table.add_row("agent_version", cfg.agent_version)
    table.add_row("framework", cfg.framework)
    table.add_row("model", cfg.model)
    table.add_row("telemetry_enabled", str(cfg.telemetry_enabled))
    table.add_row("cost_tracking_enabled", str(cfg.cost_tracking_enabled))
    table.add_row("event_bus_enabled", str(cfg.event_bus_enabled))
    table.add_row("plugins", ", ".join(cfg.plugins) if cfg.plugins else "(none)")

    console.print(table)


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------


@cli.command(name="config")
@click.option("--show", is_flag=True, help="Show the current configuration.")
@click.option("--validate", is_flag=True, help="Validate the config file.")
@click.option(
    "--set",
    "set_kv",
    nargs=2,
    metavar="KEY VALUE",
    default=None,
    help="Print a specific config value (informational only).",
)
@click.option(
    "--config",
    "-c",
    default=None,
    help="Path to agentcore config file.",
)
def config_command(
    show: bool,
    validate: bool,
    set_kv: tuple[str, str] | None,
    config: str | None,
) -> None:
    """Manage agentcore configuration."""
    from agentcore.config.loader import ConfigLoader

    loader = ConfigLoader()
    try:
        if config:
            cfg = loader.load_yaml(config)
        else:
            cfg = loader.load_auto()
    except Exception as exc:  # noqa: BLE001
        error_console.print(f"Could not load config: {exc}")
        raise SystemExit(1) from exc

    if show or (not validate and set_kv is None):
        console.print_json(cfg.model_dump_json(indent=2))

    if validate:
        from agentcore.config.schema import validate_config

        try:
            validate_config(cfg.model_dump())
            console.print("[green]Configuration is valid.[/green]")
        except Exception as exc:  # noqa: BLE001
            error_console.print(f"Validation failed: {exc}")
            raise SystemExit(1) from exc

    if set_kv is not None:
        key, value = set_kv
        current = cfg.model_dump()
        if key not in current:
            error_console.print(f"Unknown config key: {key!r}")
            raise SystemExit(1)
        console.print(
            f"[dim]Note: --set is informational. "
            f"Edit your agentcore.yaml to persist changes.[/dim]"
        )
        console.print(f"[bold]{key}[/bold] = {value!r}  (would set)")


# ---------------------------------------------------------------------------
# identity
# ---------------------------------------------------------------------------


@cli.command(name="identity")
@click.option("--create", is_flag=True, help="Create a new agent identity.")
@click.option("--list", "list_all", is_flag=True, help="List all registered identities.")
@click.option("--show", "show_id", default=None, metavar="ID", help="Show details for agent ID.")
@click.option("--name", default="my-agent", show_default=True, help="Agent name (--create).")
@click.option("--version", "ver", default="0.1.0", show_default=True, help="Agent version.")
@click.option("--framework", default="custom", show_default=True, help="Framework name.")
@click.option("--model", default="claude-sonnet-4-5", show_default=True, help="Model ID.")
def identity_command(
    create: bool,
    list_all: bool,
    show_id: str | None,
    name: str,
    ver: str,
    framework: str,
    model: str,
) -> None:
    """Manage agent identities."""
    from agentcore.identity.agent_id import create_identity
    from agentcore.identity.registry import AgentRegistry

    registry = AgentRegistry()

    if create:
        identity = create_identity(name=name, version=ver, framework=framework, model=model)
        console.print("[green]Created identity:[/green]")
        console.print_json(json.dumps(identity.to_dict(), default=str))
        return

    if list_all:
        all_identities = registry.list_all()
        if not all_identities:
            console.print("[dim](No identities in registry)[/dim]")
            return
        table = Table(title="Registered identities", header_style="bold cyan")
        table.add_column("agent_id")
        table.add_column("name")
        table.add_column("framework")
        table.add_column("model")
        for ident in all_identities:
            table.add_row(ident.agent_id, ident.name, ident.framework, ident.model)
        console.print(table)
        return

    if show_id:
        try:
            ident = registry.get(show_id)
            console.print_json(json.dumps(ident.to_dict(), default=str))
        except Exception as exc:  # noqa: BLE001
            error_console.print(f"Identity not found: {exc}")
            raise SystemExit(1) from exc
        return

    # Default: show help hint
    console.print("Use [bold]--create[/bold], [bold]--list[/bold], or [bold]--show ID[/bold].")


# ---------------------------------------------------------------------------
# cost
# ---------------------------------------------------------------------------


@cli.command(name="cost")
@click.option("--show", "show_costs", is_flag=True, help="Show all tracked costs.")
@click.option("--reset", "reset_all", is_flag=True, help="Reset all cost records.")
@click.option("--budget", "show_budgets", is_flag=True, help="Show all budget entries.")
def cost_command(show_costs: bool, reset_all: bool, show_budgets: bool) -> None:
    """Cost tracking commands."""
    from agentcore.cost.tracker import CostTracker
    from agentcore.cost.budget import BasicBudgetManager

    tracker = CostTracker()
    budget_mgr = BasicBudgetManager()

    if show_costs:
        all_costs = tracker.get_all_costs()
        if not all_costs:
            console.print("[dim](No cost records found)[/dim]")
            return
        table = Table(title="Agent costs", header_style="bold cyan")
        table.add_column("agent_id")
        table.add_column("total_cost_usd", justify="right")
        table.add_column("input_tokens", justify="right")
        table.add_column("output_tokens", justify="right")
        for agent_id, costs in all_costs.items():
            table.add_row(
                agent_id,
                f"${costs.total_cost_usd:.6f}",
                str(costs.total_input_tokens),
                str(costs.total_output_tokens),
            )
        console.print(table)
        return

    if reset_all:
        tracker.reset_all()
        console.print("[green]All cost records reset.[/green]")
        return

    if show_budgets:
        budgets = budget_mgr.get_all_budgets()
        if not budgets:
            console.print("[dim](No budgets configured)[/dim]")
            return
        table = Table(title="Agent budgets", header_style="bold cyan")
        table.add_column("agent_id")
        table.add_column("budget_usd", justify="right")
        table.add_column("spent_usd", justify="right")
        table.add_column("remaining_usd", justify="right")
        for agent_id, entry in budgets.items():
            table.add_row(
                agent_id,
                f"${entry['budget']:.4f}",
                f"${entry['spent']:.4f}",
                f"${entry['remaining']:.4f}",
            )
        console.print(table)
        return

    console.print("Use [bold]--show[/bold], [bold]--reset[/bold], or [bold]--budget[/bold].")


# ---------------------------------------------------------------------------
# health
# ---------------------------------------------------------------------------


@cli.command(name="health")
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["table", "json"]),
    show_default=True,
    help="Output format.",
)
def health_command(output_format: str) -> None:
    """Run health checks and report status."""
    from agentcore.bus.event_bus import EventBus
    from agentcore.cost.tracker import CostTracker
    from agentcore.health.check import HealthCheck, HealthStatus
    from agentcore.identity.registry import AgentRegistry

    bus = EventBus()
    registry = AgentRegistry()
    tracker = CostTracker()

    hc = HealthCheck()
    hc.register_event_bus_check(bus)
    hc.register_identity_registry_check(registry)
    hc.register_cost_tracker_check(tracker)

    report = hc.run_checks()

    if output_format == "json":
        console.print_json(json.dumps(report.to_dict()))
        return

    status_colour = {
        HealthStatus.HEALTHY: "green",
        HealthStatus.DEGRADED: "yellow",
        HealthStatus.UNHEALTHY: "red",
    }
    colour = status_colour.get(report.status, "white")
    console.print(
        f"Overall status: [{colour}]{report.status.value.upper()}[/{colour}]"
    )

    table = Table(header_style="bold cyan")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Message")

    for name, result in report.checks.items():
        c = status_colour.get(result.status, "white")
        table.add_row(name, f"[{c}]{result.status.value}[/{c}]", result.message)

    console.print(table)

    if report.status is HealthStatus.UNHEALTHY:
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# plugins
# ---------------------------------------------------------------------------


@cli.command(name="plugins")
def plugins_command() -> None:
    """List all registered plugins loaded from entry-points."""
    from agentcore.plugins.registry import AgentPluginRegistry

    registry = AgentPluginRegistry()
    discovered = registry.auto_discover("agentcore.plugins")

    if not discovered:
        console.print(
            "[bold]Registered plugins:[/bold]\n"
            "  [dim](No plugins registered. Install a plugin package to see entries here.)[/dim]"
        )
        return

    table = Table(title="Installed plugins", header_style="bold cyan")
    table.add_column("Name")
    for name in discovered:
        table.add_row(name)
    console.print(table)


if __name__ == "__main__":
    cli()
