"""
Vibe-Sync local configuration management.
Handles the .vibe/ directory, config.json metadata, and sync tracking.
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional

from rich.console import Console

console = Console()

VIBE_DIR = ".vibe"
CONFIG_FILE = os.path.join(VIBE_DIR, "config.json")

DEFAULT_CONFIG = {
    "project_name": "",
    "created_at": "",
    "last_synced": None,
    "last_commit_hash": None,
    "last_commit_message": None,
    "sync_count": 0,
    "gcs_bucket": None,
    "google_project_id": None,
    "cloud_run_url": None,
    "cloud_run_region": None,
    "remote_sync_enabled": False,
}


def ensure_vibe_dir() -> str:
    """Create the .vibe/ directory if it doesn't exist. Returns the path."""
    os.makedirs(VIBE_DIR, exist_ok=True)
    return VIBE_DIR


def init_config(project_name: Optional[str] = None) -> dict:
    """Initialize .vibe/config.json with default values."""
    ensure_vibe_dir()

    if os.path.exists(CONFIG_FILE):
        return load_config()

    config = DEFAULT_CONFIG.copy()
    config["project_name"] = project_name or os.path.basename(os.getcwd())
    config["created_at"] = datetime.now(timezone.utc).isoformat()

    _save_config(config)
    return config


def load_config() -> dict:
    """Load and return the current .vibe/config.json, or defaults if missing."""
    if not os.path.exists(CONFIG_FILE):
        return DEFAULT_CONFIG.copy()

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_config(config: dict) -> None:
    """Write config dict to .vibe/config.json."""
    ensure_vibe_dir()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, default=str)


def record_sync(commit_hash: Optional[str] = None, commit_message: Optional[str] = None) -> dict:
    """Record a sync event with timestamp and optional commit info."""
    config = load_config()
    config["last_synced"] = datetime.now(timezone.utc).isoformat()
    config["sync_count"] = config.get("sync_count", 0) + 1

    if commit_hash:
        config["last_commit_hash"] = commit_hash
    if commit_message:
        config["last_commit_message"] = commit_message

    _save_config(config)
    return config


def get_last_synced() -> Optional[str]:
    """Return the last synced timestamp, or None if never synced."""
    config = load_config()
    return config.get("last_synced")


def set_gcs_bucket(bucket_name: str) -> dict:
    """Configure a GCS bucket for remote sync."""
    config = load_config()
    config["gcs_bucket"] = bucket_name
    config["remote_sync_enabled"] = True
    _save_config(config)
    return config


def set_google_project(project_id: str) -> dict:
    """Configure the Google Cloud project ID."""
    config = load_config()
    config["google_project_id"] = project_id
    _save_config(config)
    return config


def set_cloud_run_url(url: str, region: Optional[str] = None) -> dict:
    """Store the deployed Cloud Run service URL."""
    config = load_config()
    config["cloud_run_url"] = url
    if region:
        config["cloud_run_region"] = region
    _save_config(config)
    return config
