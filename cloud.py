"""
Vibe-Sync Google Cloud Storage integration.
Handles uploading/downloading VIBE_CONTEXT.md and metadata to/from GCS buckets.
"""

import os
import json
from datetime import datetime, timezone
from typing import Optional

from rich.console import Console

console = Console()

CONTEXT_FILENAME = "VIBE_CONTEXT.md"
VIBE_DIR = ".vibe"
CONFIG_FILE = os.path.join(VIBE_DIR, "config.json")


def _get_storage_client():
    """Get an authenticated GCS client."""
    try:
        from google.cloud import storage
        return storage.Client()
    except Exception as e:
        raise RuntimeError(
            f"Failed to create GCS client. Ensure you have run "
            f"'gcloud auth application-default login' and the "
            f"google-cloud-storage package is installed.\n\nError: {e}"
        )


def _get_or_create_bucket(client, bucket_name: str, location: str = "us-central1"):
    """Get a bucket, or create it if it doesn't exist."""
    bucket = client.bucket(bucket_name)
    if not bucket.exists():
        console.print(f"[dim]Bucket '{bucket_name}' not found — creating it...[/dim]")
        bucket = client.create_bucket(bucket_name, location=location)
        console.print(f"[green]Created bucket '{bucket_name}' in {location}[/green]")
    return bucket


def _project_prefix() -> str:
    """Return a GCS prefix based on the project name from config."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            cfg = json.load(f)
        name = cfg.get("project_name", "unknown")
    else:
        name = os.path.basename(os.getcwd())
    # Sanitize for use as GCS prefix
    return name.replace(" ", "_").lower()


def upload_context(bucket_name: str, location: str = "us-central1", versioned: bool = False) -> dict:
    """Upload VIBE_CONTEXT.md and .vibe/config.json to a GCS bucket.

    Files are stored under a project-specific prefix:
        vibes/<project_name>/VIBE_CONTEXT.md
        vibes/<project_name>/config.json

    If versioned=True, a timestamped backup is also saved:
        vibes/<project_name>/history/VIBE_CONTEXT_<timestamp>.md

    Returns a dict with upload details.
    """
    client = _get_storage_client()
    bucket = _get_or_create_bucket(client, bucket_name, location)
    prefix = _project_prefix()

    uploaded = []
    backup_path = None

    # Upload VIBE_CONTEXT.md
    if os.path.exists(CONTEXT_FILENAME):
        blob = bucket.blob(f"vibes/{prefix}/{CONTEXT_FILENAME}")

        # Create a versioned backup before overwriting
        if versioned:
            try:
                existing = blob.download_as_text(encoding="utf-8")
                ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                backup_key = f"vibes/{prefix}/history/VIBE_CONTEXT_{ts}.md"
                backup_blob = bucket.blob(backup_key)
                backup_blob.upload_from_string(existing, content_type="text/markdown")
                backup_path = backup_key
            except Exception:
                pass  # No existing file to back up — skip silently

        blob.upload_from_filename(CONTEXT_FILENAME)
        blob.metadata = {"synced_at": datetime.now(timezone.utc).isoformat()}
        blob.patch()
        uploaded.append(f"vibes/{prefix}/{CONTEXT_FILENAME}")

    # Upload .vibe/config.json
    if os.path.exists(CONFIG_FILE):
        blob = bucket.blob(f"vibes/{prefix}/config.json")
        blob.upload_from_filename(CONFIG_FILE)
        uploaded.append(f"vibes/{prefix}/config.json")

    return {
        "bucket": bucket_name,
        "prefix": f"vibes/{prefix}/",
        "files_uploaded": uploaded,
        "backup_path": backup_path,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def download_context(bucket_name: str) -> dict:
    """Download VIBE_CONTEXT.md and config.json from a GCS bucket.

    Overwrites local files with the remote versions.

    Returns a dict with download details.
    """
    client = _get_storage_client()
    bucket = client.bucket(bucket_name)

    if not bucket.exists():
        raise FileNotFoundError(f"Bucket '{bucket_name}' does not exist.")

    prefix = _project_prefix()
    downloaded = []

    # Download VIBE_CONTEXT.md
    blob = bucket.blob(f"vibes/{prefix}/{CONTEXT_FILENAME}")
    if blob.exists():
        blob.download_to_filename(CONTEXT_FILENAME)
        downloaded.append(CONTEXT_FILENAME)

    # Download config.json
    blob = bucket.blob(f"vibes/{prefix}/config.json")
    if blob.exists():
        os.makedirs(VIBE_DIR, exist_ok=True)
        blob.download_to_filename(CONFIG_FILE)
        downloaded.append(CONFIG_FILE)

    if not downloaded:
        raise FileNotFoundError(
            f"No vibe files found in gs://{bucket_name}/vibes/{prefix}/"
        )

    return {
        "bucket": bucket_name,
        "prefix": f"vibes/{prefix}/",
        "files_downloaded": downloaded,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def list_remote_vibes(bucket_name: str) -> list[dict]:
    """List all projects that have synced context to the GCS bucket.

    Returns a list of dicts with project name and last modified time.
    """
    client = _get_storage_client()
    bucket = client.bucket(bucket_name)

    if not bucket.exists():
        raise FileNotFoundError(f"Bucket '{bucket_name}' does not exist.")

    # List all prefixes under vibes/
    projects = []
    seen = set()

    blobs = bucket.list_blobs(prefix="vibes/")
    for blob in blobs:
        # Extract project name from path like vibes/<project>/VIBE_CONTEXT.md
        parts = blob.name.split("/")
        if len(parts) >= 3:
            project_name = parts[1]
            if project_name not in seen:
                seen.add(project_name)
                projects.append({
                    "project": project_name,
                    "last_modified": blob.updated.isoformat() if blob.updated else "Unknown",
                    "path": f"gs://{bucket_name}/vibes/{project_name}/",
                })

    return projects


def read_context_from_gcs(bucket_name: str, project_name: Optional[str] = None) -> str:
    """Read VIBE_CONTEXT.md directly from GCS. Used by the Cloud Run server.

    Args:
        bucket_name: The GCS bucket name.
        project_name: Optional project prefix; defaults to auto-detected.

    Returns:
        The contents of the remote VIBE_CONTEXT.md.
    """
    client = _get_storage_client()
    bucket = client.bucket(bucket_name)

    prefix = project_name or _project_prefix()
    blob = bucket.blob(f"vibes/{prefix}/{CONTEXT_FILENAME}")

    if not blob.exists():
        return f"⚠️ No VIBE_CONTEXT.md found in gs://{bucket_name}/vibes/{prefix}/"

    return blob.download_as_text(encoding="utf-8")
