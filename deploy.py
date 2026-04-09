"""
Vibe-Sync Cloud Run deployment helper.
Generates and optionally executes gcloud commands to deploy the MCP server.
"""

import os
import subprocess
import shutil
from typing import Optional

from rich.console import Console
from rich.syntax import Syntax

console = Console()


def check_gcloud_installed() -> bool:
    """Check if the gcloud CLI is available."""
    return shutil.which("gcloud") is not None


def get_current_project() -> Optional[str]:
    """Get the currently configured gcloud project."""
    try:
        result = subprocess.run(
            ["gcloud", "config", "get-value", "project"],
            capture_output=True, text=True, timeout=10,
        )
        project = result.stdout.strip()
        return project if project and project != "(unset)" else None
    except Exception:
        return None


def build_deploy_command(
    project_id: str,
    region: str = "us-central1",
    service_name: str = "vibe-sync-mcp",
    gcs_bucket: Optional[str] = None,
    port: int = 8080,
) -> list[str]:
    """Build the gcloud run deploy command.

    Returns the command as a list of strings.
    """
    cmd = [
        "gcloud", "run", "deploy", service_name,
        "--source", ".",
        "--project", project_id,
        "--region", region,
        "--port", str(port),
        "--allow-unauthenticated",
        "--memory", "256Mi",
        "--cpu", "1",
        "--min-instances", "0",
        "--max-instances", "2",
        "--timeout", "60",
    ]

    # Pass GCS bucket as env var so server.py can read from cloud storage
    env_vars = []
    if gcs_bucket:
        env_vars.append(f"GCS_BUCKET={gcs_bucket}")

    if env_vars:
        cmd.extend(["--set-env-vars", ",".join(env_vars)])

    return cmd


def deploy(
    project_id: str,
    region: str = "us-central1",
    service_name: str = "vibe-sync-mcp",
    gcs_bucket: Optional[str] = None,
    dry_run: bool = False,
) -> Optional[str]:
    """Deploy the MCP server to Cloud Run.

    Args:
        project_id: GCP project ID.
        region: Cloud Run region.
        service_name: Name of the Cloud Run service.
        gcs_bucket: Optional GCS bucket for remote context storage.
        dry_run: If True, only print the command without executing.

    Returns:
        The service URL if deployed, None if dry run.
    """
    if not check_gcloud_installed():
        raise RuntimeError(
            "gcloud CLI not found. Install it from: "
            "https://cloud.google.com/sdk/docs/install"
        )

    cmd = build_deploy_command(
        project_id=project_id,
        region=region,
        service_name=service_name,
        gcs_bucket=gcs_bucket,
    )

    cmd_str = " \\\n  ".join(cmd)

    if dry_run:
        console.print("\n[bold cyan]Dry run — command that would be executed:[/bold cyan]\n")
        console.print(Syntax(cmd_str, "bash", theme="monokai"))
        console.print()
        return None

    console.print(f"\n[bold]Deploying [cyan]{service_name}[/cyan] to Cloud Run...[/bold]\n")
    console.print(Syntax(cmd_str, "bash", theme="monokai"))
    console.print()

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Deployment failed (exit code {result.returncode}):\n"
            f"{result.stderr}"
        )

    # Extract the service URL from stdout
    service_url = None
    for line in result.stdout.splitlines():
        if "https://" in line:
            # gcloud typically outputs: Service URL: https://...
            parts = line.split("https://")
            if parts:
                service_url = "https://" + parts[-1].strip()
                break

    if service_url:
        console.print(f"\n[bold green]✅ Deployed successfully![/bold green]")
        console.print(f"[bold]Service URL:[/bold] {service_url}\n")
    else:
        console.print(f"\n[bold green]✅ Deployment completed.[/bold green]")
        console.print("[dim]Could not auto-detect service URL from output.[/dim]\n")

    return service_url


def get_service_url(
    project_id: str,
    region: str = "us-central1",
    service_name: str = "vibe-sync-mcp",
) -> Optional[str]:
    """Get the URL of an already-deployed Cloud Run service."""
    try:
        result = subprocess.run(
            [
                "gcloud", "run", "services", "describe", service_name,
                "--project", project_id,
                "--region", region,
                "--format", "value(status.url)",
            ],
            capture_output=True, text=True, timeout=15,
        )
        url = result.stdout.strip()
        return url if url.startswith("https://") else None
    except Exception:
        return None
