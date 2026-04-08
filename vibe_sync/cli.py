"""Command-line interface for vibe-sync."""

from __future__ import annotations

import sys
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

console = Console()


def _load_config():
    from vibe_sync.auth import load_config

    return load_config()


def _make_gcs(config: dict):
    from vibe_sync.auth import VibeAuth
    from vibe_sync.gcs import VibeGCS

    bucket = config.get("bucket")
    if not bucket:
        console.print("[red]No bucket configured. Run:[/red] vibe-sync configure --bucket BUCKET")
        sys.exit(1)
    auth = VibeAuth.from_config()
    return VibeGCS(bucket, auth.get_credentials())


@click.group()
@click.version_option(package_name="vibe-sync")
def main():
    """vibe-sync – sync configuration snapshots to Google Cloud Storage."""


@main.command()
@click.argument("name")
@click.argument("path", type=click.Path())
def push(name: str, path: str):
    """Push a local file/dir as a named vibe to GCS."""
    from vibe_sync.operations import push as _push

    config = _load_config()
    gcs = _make_gcs(config)
    try:
        _push(name, path, gcs)
    except FileNotFoundError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(1)


@main.command()
@click.argument("name")
@click.argument("path", type=click.Path(), required=False, default=None)
@click.option("--version", "-v", type=int, default=None, help="Specific version to pull.")
def pull(name: str, path: Optional[str], version: Optional[int]):
    """Pull a vibe from GCS to a local path."""
    from vibe_sync.operations import pull as _pull

    config = _load_config()
    gcs = _make_gcs(config)
    dest = path or name
    try:
        _pull(name, dest, gcs, version)
    except KeyError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(1)


@main.command()
@click.argument("name")
def undo(name: str):
    """Revert a vibe to its previous version."""
    from vibe_sync.operations import undo_vibe

    config = _load_config()
    gcs = _make_gcs(config)
    try:
        undo_vibe(name, gcs)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(1)


@main.command()
@click.argument("name")
@click.argument("path", type=click.Path(), required=False, default=None)
def diff(name: str, path: Optional[str]):
    """Show diff between local file and GCS version."""
    from vibe_sync.operations import diff_vibe

    config = _load_config()
    gcs = _make_gcs(config)
    try:
        diff_vibe(name, path, gcs)
    except KeyError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(1)


@main.command()
def doctor():
    """Diagnose auth/connectivity/config issues."""
    from vibe_sync.operations import doctor as _doctor

    config = _load_config()
    ok = _doctor(config)
    if not ok:
        sys.exit(1)


@main.command(name="list")
def list_vibes():
    """List all vibes and their versions."""
    config = _load_config()
    gcs = _make_gcs(config)
    vibes = gcs.list_vibes()
    if not vibes:
        console.print("[yellow]No vibes found.[/yellow]")
        return
    table = Table(title="Vibes", show_header=True, header_style="bold cyan")
    table.add_column("Name")
    table.add_column("Current Version", justify="right")
    table.add_column("# Versions", justify="right")
    table.add_column("Latest Timestamp")
    for vibe in vibes:
        versions = vibe["versions"]
        latest_ts = versions[-1]["timestamp"] if versions else "—"
        table.add_row(
            vibe["name"],
            str(vibe["current_version"]),
            str(len(versions)),
            latest_ts,
        )
    console.print(table)


@main.command()
@click.option("--bucket", required=True, help="GCS bucket name.")
@click.option("--key-path", default=None, help="Path to service account JSON key (optional).")
def configure(bucket: str, key_path: Optional[str]):
    """Save bucket and optional service account key to config."""
    from vibe_sync.auth import VibeAuth

    VibeAuth.configure(bucket, key_path)
    console.print(f"[green]✔[/green] Configuration saved (bucket=[bold]{bucket}[/bold]).")


@main.command()
def mcp():
    """Start the vibe_query MCP server (stdio)."""
    from vibe_sync.mcp_server import run_server

    run_server()
