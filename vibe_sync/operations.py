"""High-level operations for vibe-sync."""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from vibe_sync.gcs import VibeGCS

from rich.console import Console

console = Console()


def push(name: str, path: str | Path, gcs: "VibeGCS") -> int:
    """Validate *path* exists and upload it as vibe *name*.

    Returns the new version number.
    """
    local_path = Path(path)
    if not local_path.exists():
        raise FileNotFoundError(f"Path does not exist: {local_path}")
    version = gcs.upload(name, local_path)
    console.print(f"[green]✔[/green] Pushed [bold]{name}[/bold] → version {version}")
    return version


def pull(name: str, path: str | Path, gcs: "VibeGCS", version: Optional[int] = None) -> None:
    """Download vibe *name* to *path*."""
    local_path = Path(path)
    data = gcs.download(name, version)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(data)
    ver_label = f"v{version}" if version else "latest"
    console.print(f"[green]✔[/green] Pulled [bold]{name}[/bold] ({ver_label}) → {local_path}")


def undo_vibe(name: str, gcs: "VibeGCS") -> None:
    """Revert vibe *name* to its previous version."""
    prev_version = gcs.undo(name)
    console.print(f"[yellow]↩[/yellow] Reverted [bold]{name}[/bold] to version {prev_version}")


def diff_vibe(name: str, path: Optional[str | Path], gcs: "VibeGCS") -> None:
    """Show diff between local *path* and the latest GCS version of *name*.

    If *path* is None, show diff between the two most recent GCS versions.
    """
    remote_bytes = gcs.get_blob_content(name)

    if path is None:
        # Diff the two most recent versions
        manifest = gcs.get_manifest(name)
        versions = manifest.get("versions", [])
        if len(versions) < 2:
            console.print("[yellow]Only one version exists; nothing to diff.[/yellow]")
            return
        prev_bytes = gcs.get_blob_content(name, versions[-2]["version"])
        _print_diff(
            prev_bytes,
            remote_bytes,
            f"{name}@v{versions[-2]['version']}",
            f"{name}@v{versions[-1]['version']}",
        )
        return

    local_path = Path(path)
    if not local_path.exists():
        console.print(f"[red]Local path does not exist:[/red] {local_path}")
        return

    local_bytes = local_path.read_bytes()
    _print_diff(local_bytes, remote_bytes, str(local_path), f"{name}@GCS")


def _print_diff(a_bytes: bytes, b_bytes: bytes, a_label: str, b_label: str) -> None:
    def _is_text(data: bytes) -> bool:
        try:
            data.decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False

    if not _is_text(a_bytes) or not _is_text(b_bytes):
        console.print(
            f"[cyan]Binary diff:[/cyan] {a_label} ({len(a_bytes)} bytes) ↔ "
            f"{b_label} ({len(b_bytes)} bytes)"
        )
        if a_bytes == b_bytes:
            console.print("[green]Files are identical.[/green]")
        else:
            diff_bytes = abs(len(b_bytes) - len(a_bytes))
            console.print(f"[yellow]Files differ by {diff_bytes} bytes.[/yellow]")
        return

    a_lines = a_bytes.decode("utf-8").splitlines(keepends=True)
    b_lines = b_bytes.decode("utf-8").splitlines(keepends=True)
    diff = list(difflib.unified_diff(a_lines, b_lines, fromfile=a_label, tofile=b_label))
    if not diff:
        console.print("[green]No differences found.[/green]")
    else:
        for line in diff:
            if line.startswith("+"):
                console.print(f"[green]{line}[/green]", end="")
            elif line.startswith("-"):
                console.print(f"[red]{line}[/red]", end="")
            else:
                console.print(line, end="")


def doctor(config: dict) -> bool:
    """Diagnose auth/connectivity/config issues.

    Returns True if everything looks healthy.
    """
    all_ok = True

    # 1. Config file
    from vibe_sync.auth import CONFIG_FILE

    if CONFIG_FILE.exists():
        console.print(f"[green]✔[/green] Config file found: {CONFIG_FILE}")
    else:
        console.print(f"[yellow]⚠[/yellow] Config file missing: {CONFIG_FILE}")
        console.print("  Run [bold]vibe-sync configure --bucket BUCKET[/bold] to set up.")
        all_ok = False

    # 2. Bucket configured
    bucket = config.get("bucket")
    if bucket:
        console.print(f"[green]✔[/green] Bucket configured: {bucket}")
    else:
        console.print("[red]✗[/red] No bucket configured.")
        all_ok = False

    # 3. Credentials
    key_path = config.get("key_path")
    if key_path:
        from pathlib import Path as _Path

        if _Path(key_path).exists():
            console.print(f"[green]✔[/green] Service account key found: {key_path}")
        else:
            console.print(f"[red]✗[/red] Service account key not found: {key_path}")
            all_ok = False
    else:
        # Check ADC
        try:
            import google.auth

            creds, project = google.auth.default()
            console.print(
                f"[green]✔[/green] Application Default Credentials found"
                f"{f' (project: {project})' if project else ''}"
            )
        except Exception as exc:
            console.print(f"[red]✗[/red] No credentials found: {exc}")
            console.print(
                "  Set GOOGLE_APPLICATION_CREDENTIALS or run "
                "[bold]gcloud auth application-default login[/bold]."
            )
            all_ok = False

    # 4. GCS connectivity
    if bucket and all_ok:
        try:
            from vibe_sync.auth import VibeAuth
            from vibe_sync.gcs import VibeGCS

            auth = VibeAuth.from_config()
            gcs = VibeGCS(bucket, auth.get_credentials())
            gcs.list_vibes()
            console.print("[green]✔[/green] GCS bucket accessible.")
        except Exception as exc:
            console.print(f"[red]✗[/red] Cannot access GCS bucket: {exc}")
            all_ok = False

    if all_ok:
        console.print("\n[bold green]All checks passed![/bold green]")
    else:
        console.print("\n[bold yellow]Some checks failed. See above for details.[/bold yellow]")

    return all_ok
