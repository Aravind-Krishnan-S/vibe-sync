import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import os
import json
import shutil
import subprocess
import sys
import difflib
from datetime import datetime
from typing import Optional

from vibe_core import (
    create_base_context, get_recent_changes, get_staleness_info,
    stamp_context, CONTEXT_FILENAME,
)
from ai_bridge import update_context_via_ai, MissingAPIKeyError
from hooks import install_hooks as _install_hooks, install_pre_commit_hook as _install_pre_commit_hook
from config import (
    init_config, load_config, record_sync, get_last_synced,
    set_gcs_bucket, set_google_project, set_cloud_run_url,
)

app = typer.Typer(
    name="vibe-sync",
    help="AI context preservation CLI tool for tracking project progress.",
)
console = Console()

ANTIGRAVITY_BRAIN = os.path.expanduser(
    os.path.join("~", ".gemini", "antigravity", "brain")
)

ARCHIVE_DIR = os.path.join(".vibe", "snapshots")


# ═══════════════════════════════════════════════════════════════════════════════
# INIT
# ═══════════════════════════════════════════════════════════════════════════════

@app.command()
def init():
    """Initialize a new vibe-sync project in the current directory."""
    with console.status("[bold blue]Initialising Vibe-Sync...[/bold blue]"):
        create_base_context()
        cfg = init_config()
    console.print("[bold green]✅ VIBE_CONTEXT.md generated![/bold green]")
    console.print(f"[dim]Project: {cfg['project_name']} | Config: .vibe/config.json[/dim]")


# ═══════════════════════════════════════════════════════════════════════════════
# COMMIT
# ═══════════════════════════════════════════════════════════════════════════════

@app.command()
def commit(
    message: Optional[str] = typer.Option(
        None, "--message", "-m",
        help="Commit message to include as extra context for the AI.",
    ),
    depth: int = typer.Option(
        5, "--depth", "-d",
        help="Number of recent commits to analyze (default: 5).",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run",
        help="Print what the AI would write without modifying VIBE_CONTEXT.md.",
    ),
    ci: bool = typer.Option(
        False, "--ci",
        help="CI mode: plain text output, no spinners.",
    ),
):
    """Create an AI-powered context commit based on recent Git changes."""
    if not os.path.exists(CONTEXT_FILENAME):
        console.print(
            f"[bold red]❌ Error:[/bold red] {CONTEXT_FILENAME} not found. "
            "Run [bold]vibe-sync init[/bold] first."
        )
        raise typer.Exit(code=1)

    def _print(msg: str):
        if ci:
            # Strip rich markup for CI
            import re
            print(re.sub(r"\[.*?\]", "", msg))
        else:
            console.print(msg)

    try:
        ctx_mgr = console.status("[bold magenta]Analyzing recent changes...[/bold magenta]")
        if ci:
            from contextlib import nullcontext
            ctx_mgr = nullcontext()

        with ctx_mgr:
            with open(CONTEXT_FILENAME, "r", encoding="utf-8") as f:
                current_context = f.read()

            git_diff = get_recent_changes(depth=depth)

            if message:
                git_diff += f"\n\n## Commit Message\n{message}\n"

            updated_context = update_context_via_ai(current_context, git_diff)

        if dry_run:
            _print("\n[bold cyan]🔍 Dry Run — proposed VIBE_CONTEXT.md update:[/bold cyan]\n")
            console.print(Panel(updated_context[:2000] + ("..." if len(updated_context) > 2000 else ""),
                                title="Proposed Update", border_style="cyan"))
            _print("[dim]No files were modified (--dry-run).[/dim]")
            return

        # Save a snapshot before overwriting
        _save_snapshot(current_context)

        with open(CONTEXT_FILENAME, "w", encoding="utf-8") as f:
            f.write(updated_context)

        stamp_context()

        commit_hash = _get_latest_commit_hash()
        record_sync(commit_hash=commit_hash, commit_message=message)

        _print("[bold blue]🧠 Vibe-Sync Brain Updated successfully![/bold blue]")

    except MissingAPIKeyError as e:
        _print(f"[bold red]🔑 API Key Error:[/bold red] {str(e)}")
        raise typer.Exit(code=1)
    except Exception as e:
        _print(f"[bold red]💥 An unexpected error occurred:[/bold red] {str(e)}")
        raise typer.Exit(code=1)


# ═══════════════════════════════════════════════════════════════════════════════
# UNDO
# ═══════════════════════════════════════════════════════════════════════════════

@app.command()
def undo():
    """Roll back VIBE_CONTEXT.md to the last saved snapshot."""
    snapshots = _list_snapshots()
    if not snapshots:
        console.print("[bold red]❌ No snapshots found.[/bold red] Run [bold]vibe-sync commit[/bold] at least once.")
        raise typer.Exit(code=1)

    latest = snapshots[-1]
    snapshot_path = os.path.join(ARCHIVE_DIR, latest)

    console.print(f"[dim]Restoring from snapshot: {latest}[/dim]")
    shutil.copy2(snapshot_path, CONTEXT_FILENAME)
    console.print("[bold green]✅ VIBE_CONTEXT.md restored to previous snapshot.[/bold green]")


# ═══════════════════════════════════════════════════════════════════════════════
# DIFF
# ═══════════════════════════════════════════════════════════════════════════════

@app.command()
def diff():
    """Show a human-readable diff between current context and the last snapshot."""
    snapshots = _list_snapshots()
    if not snapshots:
        console.print("[bold red]❌ No snapshots found.[/bold red] Run [bold]vibe-sync commit[/bold] at least once.")
        raise typer.Exit(code=1)

    latest = snapshots[-1]
    snapshot_path = os.path.join(ARCHIVE_DIR, latest)

    with open(snapshot_path, "r", encoding="utf-8") as f:
        old_lines = f.readlines()

    if not os.path.exists(CONTEXT_FILENAME):
        console.print(f"[bold red]❌ {CONTEXT_FILENAME} not found.[/bold red]")
        raise typer.Exit(code=1)

    with open(CONTEXT_FILENAME, "r", encoding="utf-8") as f:
        new_lines = f.readlines()

    delta = list(difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"snapshot/{latest}",
        tofile=CONTEXT_FILENAME,
        lineterm="",
    ))

    if not delta:
        console.print("[dim]No differences found. Context matches last snapshot.[/dim]")
        return

    for line in delta:
        if line.startswith("+"):
            console.print(f"[green]{line}[/green]", end="")
        elif line.startswith("-"):
            console.print(f"[red]{line}[/red]", end="")
        elif line.startswith("@@"):
            console.print(f"[cyan]{line}[/cyan]", end="")
        else:
            console.print(line, end="")


# ═══════════════════════════════════════════════════════════════════════════════
# DOCTOR
# ═══════════════════════════════════════════════════════════════════════════════

@app.command()
def doctor():
    """Run a full diagnostic check on the Vibe-Sync setup."""
    console.print()
    results: list[tuple[str, bool, str]] = []

    # 1. Git repo
    try:
        import git as _git
        _git.Repo(os.getcwd(), search_parent_directories=True)
        results.append(("Git repository", True, "Detected git repo in current tree"))
    except Exception:
        results.append(("Git repository", False, "Not inside a git repository"))

    # 2. VIBE_CONTEXT.md
    ctx_exists = os.path.exists(CONTEXT_FILENAME)
    results.append((
        "VIBE_CONTEXT.md",
        ctx_exists,
        "Present" if ctx_exists else "Missing — run vibe-sync init",
    ))

    # 3. Staleness
    if ctx_exists:
        stale = get_staleness_info()
        if stale["is_stale"]:
            results.append(("Context freshness", False, f"{stale['commits_since_sync']} commits behind"))
        else:
            results.append(("Context freshness", True, "Up to date"))

    # 4. .vibe/ config
    vibe_cfg = os.path.exists(os.path.join(".vibe", "config.json"))
    results.append((
        ".vibe/config.json",
        vibe_cfg,
        "Present" if vibe_cfg else "Missing — run vibe-sync init",
    ))

    # 5. Post-commit hook
    hook_ok = _check_hook_exists()
    results.append((
        "Post-commit hook",
        hook_ok,
        "Installed" if hook_ok else "Not installed — run vibe-sync install-hooks",
    ))

    # 6. GEMINI_API_KEY
    gemini_key = bool(os.environ.get("GEMINI_API_KEY") or _load_dotenv_key("GEMINI_API_KEY"))
    results.append((
        "GEMINI_API_KEY",
        gemini_key,
        "Set" if gemini_key else "Missing — add to .env file",
    ))

    # 7. GCS config
    cfg = load_config()
    gcs_bucket = cfg.get("gcs_bucket")
    results.append((
        "GCS bucket",
        bool(gcs_bucket),
        gcs_bucket if gcs_bucket else "Not configured — run vibe-sync cloud-init",
    ))

    # 8. Cloud Run URL
    cr_url = cfg.get("cloud_run_url")
    results.append((
        "Cloud Run MCP URL",
        bool(cr_url),
        cr_url if cr_url else "Not deployed — run vibe-sync deploy",
    ))

    # 9. FastMCP importable
    try:
        import fastmcp  # noqa: F401
        results.append(("fastmcp package", True, "Installed"))
    except ImportError:
        results.append(("fastmcp package", False, "pip install fastmcp"))

    # Print table
    table = Table(
        title="🩺 Vibe-Sync Doctor",
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
    )
    table.add_column("Check", style="bold white", min_width=24)
    table.add_column("Status", justify="center", min_width=10)
    table.add_column("Details", style="dim")

    for check_name, passed, detail in results:
        status_str = "[green]✅ OK[/green]" if passed else "[red]❌ FAIL[/red]"
        table.add_row(check_name, status_str, detail)

    console.print(table)

    all_ok = all(p for _, p, _ in results)
    console.print()
    if all_ok:
        console.print(Panel(
            "[bold green]All checks passed. Vibe-Sync is healthy![/bold green]",
            title="✅ Health Check", border_style="green",
        ))
    else:
        fails = sum(1 for _, p, _ in results if not p)
        console.print(Panel(
            f"[bold yellow]{fails} check(s) need attention.[/bold yellow]\n"
            "Review the table above for details.",
            title="⚠️ Health Check", border_style="yellow",
        ))
    console.print()


# ═══════════════════════════════════════════════════════════════════════════════
# INSTALL-HOOKS
# ═══════════════════════════════════════════════════════════════════════════════

@app.command("install-hooks")
def install_hooks(
    pre_commit: bool = typer.Option(
        False, "--pre-commit",
        help="Also install a pre-commit hook that warns when context is stale.",
    ),
):
    """Install Git hooks to auto-update VIBE_CONTEXT.md on every commit."""
    _install_hooks()
    if pre_commit:
        _install_pre_commit_hook()


# ═══════════════════════════════════════════════════════════════════════════════
# BUNDLE
# ═══════════════════════════════════════════════════════════════════════════════

@app.command()
def bundle(
    output: str = typer.Option(
        "vibe_bundle.md", "--output", "-o",
        help="Output markdown file for the project bundle.",
    ),
    include: Optional[str] = typer.Option(
        None, "--include",
        help="Comma-separated list of file extensions to include (e.g. py,ts,js).",
    ),
    exclude: Optional[str] = typer.Option(
        None, "--exclude",
        help="Comma-separated list of file extensions to exclude.",
    ),
    max_tokens: Optional[int] = typer.Option(
        None, "--max-tokens",
        help="Approximate token budget. Files exceeding this are truncated.",
    ),
):
    """Bundle project source code into a single Markdown file for AI upload."""
    include_exts = set(e.strip().lstrip(".") for e in include.split(",")) if include else None
    exclude_exts = set(e.strip().lstrip(".") for e in exclude.split(",")) if exclude else set()
    # Sensible defaults always excluded
    exclude_exts.update({"pyc", "pyo", "pyd", "png", "jpg", "jpeg", "gif",
                          "exe", "dll", "so", "log", "lock", "egg-info"})

    # Rough token estimate: 1 token ≈ 4 chars
    token_budget = max_tokens * 4 if max_tokens else None
    chars_written = 0

    with console.status("[bold cyan]Bundling project files...[/bold cyan]"):
        try:
            with open(output, "w", encoding="utf-8") as out:
                out.write("# 📦 VIBE-SYNC PROJECT BUNDLE\n\n")

                if os.path.exists(CONTEXT_FILENAME):
                    with open(CONTEXT_FILENAME, "r", encoding="utf-8") as f:
                        ctx = f.read()
                    out.write("## Current Vibe Context\n\n")
                    out.write(ctx)
                    out.write("\n\n---\n\n")
                    chars_written += len(ctx)

                out.write("## Source Code\n\n")

                for root, dirs, files in os.walk("."):
                    dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("__pycache__", "node_modules")]

                    for file in sorted(files):
                        if file.startswith(".") or file == output:
                            continue

                        ext = file.rsplit(".", 1)[-1] if "." in file else ""
                        if include_exts and ext not in include_exts:
                            continue
                        if ext in exclude_exts:
                            continue

                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, ".")

                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                content = f.read()

                            if token_budget and chars_written + len(content) > token_budget:
                                # Truncate to remaining budget
                                remaining = token_budget - chars_written
                                if remaining <= 0:
                                    break
                                content = content[:remaining] + "\n... (truncated due to token budget)"

                            lang = ext if ext else "text"
                            out.write(f"### File: `{rel_path}`\n")
                            out.write(f"```{lang}\n{content}\n```\n\n")
                            chars_written += len(content)

                        except Exception:
                            pass

        except Exception as e:
            console.print(f"[bold red]💥 Error bundling project:[/bold red] {str(e)}")
            raise typer.Exit(code=1)

    est_tokens = chars_written // 4
    console.print(f"[bold green]✅ Bundled to {output}[/bold green] (~{est_tokens:,} tokens)")


# ═══════════════════════════════════════════════════════════════════════════════
# STATUS
# ═══════════════════════════════════════════════════════════════════════════════

@app.command()
def status():
    """Show the current Vibe-Sync project status and sync history."""
    config = load_config()

    table = Table(
        title="🧠 Vibe-Sync Status",
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
    )
    table.add_column("Property", style="bold white", min_width=22)
    table.add_column("Value", style="green")

    table.add_row("Project Name", config.get("project_name", "Unknown"))
    table.add_row("Created At", _format_timestamp(config.get("created_at")))

    last_synced = config.get("last_synced")
    if last_synced:
        table.add_row("Last Synced", _format_timestamp(last_synced))
        table.add_row("Time Since Sync", _time_ago(last_synced))
    else:
        table.add_row("Last Synced", "[yellow]Never[/yellow]")

    table.add_row("Total Syncs", str(config.get("sync_count", 0)))

    last_hash = config.get("last_commit_hash")
    if last_hash:
        table.add_row("Last Commit", f"{last_hash[:8]}")
    last_msg = config.get("last_commit_message")
    if last_msg:
        table.add_row("Commit Message", last_msg[:60])

    ctx_exists = os.path.exists(CONTEXT_FILENAME)
    table.add_row(
        "VIBE_CONTEXT.md",
        "[green]✅ Present[/green]" if ctx_exists else "[red]❌ Missing[/red]",
    )

    # Staleness check
    if ctx_exists:
        stale = get_staleness_info()
        if stale["is_stale"]:
            stale_str = f"[yellow]⚠ {stale['commits_since_sync']} commit(s) behind[/yellow]"
        else:
            stale_str = "[green]✅ Up to date[/green]"
        table.add_row("Context Freshness", stale_str)

    vibe_dir_exists = os.path.exists(".vibe")
    table.add_row(
        ".vibe/ Config",
        "[green]✅ Present[/green]" if vibe_dir_exists else "[red]❌ Missing[/red]",
    )

    snapshots = _list_snapshots()
    table.add_row("Snapshots", f"{len(snapshots)} saved")

    hook_exists = _check_hook_exists()
    table.add_row(
        "Post-Commit Hook",
        "[green]✅ Installed[/green]" if hook_exists else "[yellow]⚠ Not installed[/yellow]",
    )

    gcs = config.get("gcs_bucket")
    table.add_row(
        "GCS Bucket",
        f"[green]{gcs}[/green]" if gcs else "[dim]Not configured[/dim]",
    )

    gcp_project = config.get("google_project_id")
    table.add_row(
        "GCP Project",
        gcp_project if gcp_project else "[dim]Not configured[/dim]",
    )

    cr_url = config.get("cloud_run_url")
    table.add_row(
        "Cloud Run URL",
        f"[blue]{cr_url}[/blue]" if cr_url else "[dim]Not deployed[/dim]",
    )

    console.print()
    console.print(table)
    console.print()


# ═══════════════════════════════════════════════════════════════════════════════
# PUSH
# ═══════════════════════════════════════════════════════════════════════════════

@app.command()
def push(
    target: str = typer.Argument(
        "antigravity",
        help="Push target: 'antigravity' to sync into Antigravity's brain.",
    ),
):
    """Push the current VIBE_CONTEXT.md into an AI agent's persistent memory."""
    if not os.path.exists(CONTEXT_FILENAME):
        console.print(
            f"[bold red]❌ Error:[/bold red] {CONTEXT_FILENAME} not found. "
            "Run [bold]vibe-sync init[/bold] first."
        )
        raise typer.Exit(code=1)

    if target.lower() == "antigravity":
        _push_to_antigravity()
    else:
        console.print(f"[bold red]❌ Unknown target:[/bold red] '{target}'")
        console.print("[dim]Supported targets: antigravity[/dim]")
        raise typer.Exit(code=1)


# ═══════════════════════════════════════════════════════════════════════════════
# MCP-TEST
# ═══════════════════════════════════════════════════════════════════════════════

@app.command("mcp-test")
def mcp_test():
    """Test MCP server connectivity and verify tools are registered."""
    console.print()
    with console.status("[bold cyan]Testing MCP server...[/bold cyan]"):
        results = _run_mcp_tests()

    table = Table(
        title="🔌 MCP Server Connectivity Test",
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
    )
    table.add_column("Check", style="bold white", min_width=28)
    table.add_column("Status", justify="center", min_width=12)
    table.add_column("Details", style="dim")

    for check_name, passed, detail in results:
        status_str = "[green]✅ PASS[/green]" if passed else "[red]❌ FAIL[/red]"
        table.add_row(check_name, status_str, detail)

    console.print(table)

    all_passed = all(p for _, p, _ in results)
    console.print()
    if all_passed:
        console.print(Panel(
            "[bold green]All MCP checks passed.[/bold green]\n"
            "The server is ready for agent use.",
            title="✅ Result",
            border_style="green",
        ))
    else:
        console.print(Panel(
            "[bold yellow]Some checks failed.[/bold yellow]\n"
            "Review the table above for details.",
            title="⚠️ Result",
            border_style="yellow",
        ))
    console.print()


# ═══════════════════════════════════════════════════════════════════════════════
# CLOUD COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@app.command("cloud-init")
def cloud_init(
    bucket: str = typer.Option(..., "--bucket", "-b", help="GCS bucket name."),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="GCP project ID."),
):
    """Configure Google Cloud Storage for cross-machine context sync."""
    from deploy import get_current_project

    with console.status("[bold cyan]Configuring GCS...[/bold cyan]"):
        set_gcs_bucket(bucket)
        project_id = project or get_current_project()
        if project_id:
            set_google_project(project_id)

    console.print("[bold green]✅ Cloud storage configured![/bold green]")
    console.print(f"  [dim]Bucket:[/dim]  [cyan]{bucket}[/cyan]")
    if project_id:
        console.print(f"  [dim]Project:[/dim] [cyan]{project_id}[/cyan]")
    console.print()
    console.print("[dim]Run [bold]vibe-sync cloud-push[/bold] to upload your context.[/dim]")


@app.command("cloud-push")
def cloud_push():
    """Push VIBE_CONTEXT.md and metadata to Google Cloud Storage (with versioned backup)."""
    config = load_config()
    bucket = config.get("gcs_bucket")

    if not bucket:
        console.print("[bold red]❌ Error:[/bold red] No GCS bucket configured.")
        raise typer.Exit(code=1)
    if not os.path.exists(CONTEXT_FILENAME):
        console.print(f"[bold red]❌ Error:[/bold red] {CONTEXT_FILENAME} not found.")
        raise typer.Exit(code=1)

    try:
        from cloud import upload_context
        with console.status("[bold magenta]Uploading to GCS...[/bold magenta]"):
            result = upload_context(bucket, versioned=True)

        console.print("[bold green]☁️  Pushed to GCS successfully![/bold green]")
        for f in result["files_uploaded"]:
            console.print(f"  [dim]📄 gs://{bucket}/{f}[/dim]")
        if result.get("backup_path"):
            console.print(f"  [dim]🗄  Backup: gs://{bucket}/{result['backup_path']}[/dim]")

    except Exception as e:
        console.print(f"[bold red]💥 GCS push failed:[/bold red] {str(e)}")
        raise typer.Exit(code=1)


@app.command("cloud-pull")
def cloud_pull():
    """Pull the latest VIBE_CONTEXT.md from Google Cloud Storage."""
    config = load_config()
    bucket = config.get("gcs_bucket")

    if not bucket:
        console.print("[bold red]❌ Error:[/bold red] No GCS bucket configured.")
        raise typer.Exit(code=1)

    try:
        from cloud import download_context
        with console.status("[bold magenta]Downloading from GCS...[/bold magenta]"):
            result = download_context(bucket)

        console.print("[bold green]☁️  Pulled from GCS successfully![/bold green]")
        for f in result["files_downloaded"]:
            console.print(f"  [dim]📄 {f} ← gs://{bucket}/[/dim]")

    except FileNotFoundError as e:
        console.print(f"[bold red]❌ Not found:[/bold red] {str(e)}")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]💥 GCS pull failed:[/bold red] {str(e)}")
        raise typer.Exit(code=1)


@app.command("cloud-diff")
def cloud_diff():
    """Show a diff between local VIBE_CONTEXT.md and the version stored in GCS."""
    config = load_config()
    bucket = config.get("gcs_bucket")

    if not bucket:
        console.print("[bold red]❌ Error:[/bold red] No GCS bucket configured.")
        raise typer.Exit(code=1)

    try:
        from cloud import read_context_from_gcs
        with console.status("[bold cyan]Fetching remote context...[/bold cyan]"):
            remote_content = read_context_from_gcs(bucket)

        if not os.path.exists(CONTEXT_FILENAME):
            console.print(f"[bold red]❌ Local {CONTEXT_FILENAME} not found.[/bold red]")
            raise typer.Exit(code=1)

        with open(CONTEXT_FILENAME, "r", encoding="utf-8") as f:
            local_content = f.read()

        delta = list(difflib.unified_diff(
            remote_content.splitlines(keepends=True),
            local_content.splitlines(keepends=True),
            fromfile=f"gs://{bucket}/VIBE_CONTEXT.md",
            tofile=f"local/{CONTEXT_FILENAME}",
            lineterm="",
        ))

        if not delta:
            console.print("[dim]✅ Local and remote contexts are identical.[/dim]")
            return

        for line in delta:
            if line.startswith("+"):
                console.print(f"[green]{line}[/green]", end="")
            elif line.startswith("-"):
                console.print(f"[red]{line}[/red]", end="")
            elif line.startswith("@@"):
                console.print(f"[cyan]{line}[/cyan]", end="")
            else:
                console.print(line, end="")

    except Exception as e:
        console.print(f"[bold red]💥 cloud-diff failed:[/bold red] {str(e)}")
        raise typer.Exit(code=1)


@app.command()
def deploy(
    project: Optional[str] = typer.Option(None, "--project", "-p", help="GCP project ID."),
    region: str = typer.Option("us-central1", "--region", "-r", help="Cloud Run region."),
    service_name: str = typer.Option("vibe-sync-mcp", "--name", "-n", help="Cloud Run service name."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the deploy command without executing."),
):
    """Deploy the Vibe-Sync MCP server to Google Cloud Run."""
    from deploy import deploy as run_deploy, check_gcloud_installed, get_current_project

    if not check_gcloud_installed():
        console.print("[bold red]❌ Error:[/bold red] gcloud CLI not found.")
        raise typer.Exit(code=1)

    config = load_config()
    project_id = project or config.get("google_project_id") or get_current_project()
    if not project_id:
        console.print("[bold red]❌ Error:[/bold red] No GCP project found.")
        raise typer.Exit(code=1)

    gcs_bucket = config.get("gcs_bucket")

    try:
        service_url = run_deploy(
            project_id=project_id,
            region=region,
            service_name=service_name,
            gcs_bucket=gcs_bucket,
            dry_run=dry_run,
        )

        if service_url and not dry_run:
            set_google_project(project_id)
            set_cloud_run_url(service_url, region=region)
            console.print("[dim]Config updated with deployment URL.[/dim]")

    except RuntimeError as e:
        console.print(f"[bold red]💥 Deployment failed:[/bold red] {str(e)}")
        raise typer.Exit(code=1)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _save_snapshot(content: str) -> None:
    """Save the current context to a timestamped snapshot file."""
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(ARCHIVE_DIR, f"context_{ts}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _list_snapshots() -> list[str]:
    """Return a sorted list of snapshot filenames."""
    if not os.path.isdir(ARCHIVE_DIR):
        return []
    files = sorted(f for f in os.listdir(ARCHIVE_DIR) if f.endswith(".md"))
    return files


def _load_dotenv_key(key: str) -> Optional[str]:
    """Try to load a key from .env without the dotenv package."""
    env_path = ".env"
    if not os.path.exists(env_path):
        return None
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _get_latest_commit_hash() -> Optional[str]:
    try:
        import git
        repo = git.Repo(os.getcwd(), search_parent_directories=True)
        commits = list(repo.iter_commits(max_count=1))
        return commits[0].hexsha if commits else None
    except Exception:
        return None


def _format_timestamp(ts: Optional[str]) -> str:
    if not ts:
        return "[dim]—[/dim]"
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return ts


def _time_ago(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts)
        now = datetime.now(dt.tzinfo)
        delta = now - dt
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return f"{seconds}s ago"
        elif seconds < 3600:
            return f"{seconds // 60}m ago"
        elif seconds < 86400:
            return f"{seconds // 3600}h ago"
        else:
            return f"{seconds // 86400}d ago"
    except Exception:
        return "[dim]Unknown[/dim]"


def _check_hook_exists() -> bool:
    try:
        import git
        repo = git.Repo(os.getcwd(), search_parent_directories=True)
        hook_path = os.path.join(repo.git_dir, "hooks", "post-commit")
        return os.path.exists(hook_path)
    except Exception:
        return False


def _push_to_antigravity():
    with console.status("[bold magenta]Pushing to Antigravity brain...[/bold magenta]"):
        with open(CONTEXT_FILENAME, "r", encoding="utf-8") as f:
            context_content = f.read()

        os.makedirs(ANTIGRAVITY_BRAIN, exist_ok=True)
        memory_path = os.path.join(ANTIGRAVITY_BRAIN, "memory.json")
        config = load_config()

        memory = {
            "source": "vibe-sync",
            "project_name": config.get("project_name", "Unknown"),
            "last_updated": datetime.now().isoformat(),
            "persistent_context": context_content,
            "sync_count": config.get("sync_count", 0),
            "last_commit_hash": config.get("last_commit_hash"),
            "last_commit_message": config.get("last_commit_message"),
        }

        with open(memory_path, "w", encoding="utf-8") as f:
            json.dump(memory, f, indent=2)

        vibe_copy_path = os.path.join(ANTIGRAVITY_BRAIN, "VIBE_CONTEXT.md")
        shutil.copy2(CONTEXT_FILENAME, vibe_copy_path)

    console.print("[bold green]✅ Pushed to Antigravity brain successfully![/bold green]")
    console.print(f"[dim]  📄 memory.json  → {memory_path}[/dim]")
    console.print(f"[dim]  📄 VIBE_CONTEXT  → {vibe_copy_path}[/dim]")


def _run_mcp_tests() -> list[tuple[str, bool, str]]:
    results = []

    try:
        import server  # noqa: F401
        results.append(("Server module import", True, "server.py loads OK"))
    except Exception as e:
        results.append(("Server module import", False, str(e)[:60]))

    try:
        from fastmcp import FastMCP  # noqa: F401
        results.append(("FastMCP package", True, "fastmcp is installed"))
    except ImportError:
        results.append(("FastMCP package", False, "pip install fastmcp"))

    try:
        from server import mcp as server_mcp
        tools_found = hasattr(server_mcp, "tool")
        results.append(("MCP tools registered", tools_found, "get_latest_vibe, read_vibe, vibe_query, vibe_diff"))
    except Exception as e:
        results.append(("MCP tools registered", False, str(e)[:60]))

    try:
        from server import get_latest_vibe
        vibe_output = get_latest_vibe()
        has_content = len(vibe_output) > 20 and "not found" not in vibe_output.lower()
        detail = f"{len(vibe_output)} chars returned" if has_content else "File missing or empty"
        results.append(("VIBE_CONTEXT.md readable", has_content, detail))
    except Exception as e:
        results.append(("VIBE_CONTEXT.md readable", False, str(e)[:60]))

    try:
        mcp_config_path = os.path.expanduser(
            os.path.join("~", ".gemini", "antigravity", "mcp_config.json")
        )
        if os.path.exists(mcp_config_path):
            with open(mcp_config_path, "r") as f:
                mcp_cfg = json.load(f)
            registered = "vibe-sync" in mcp_cfg.get("mcpServers", {})
            detail = "Registered in mcp_config.json" if registered else "Not found in config"
            results.append(("Antigravity registration", registered, detail))
        else:
            results.append(("Antigravity registration", False, "mcp_config.json not found"))
    except Exception as e:
        results.append(("Antigravity registration", False, str(e)[:60]))

    return results


if __name__ == "__main__":
    app()
