"""Authentication helpers for vibe-sync."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import google.auth
import google.oauth2.service_account

CONFIG_DIR = Path.home() / ".vibe-sync"
CONFIG_FILE = CONFIG_DIR / "config.json"

SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


class VibeAuth:
    """Manages Google Cloud credentials and vibe-sync configuration."""

    def __init__(self, credentials=None, config: Optional[dict] = None):
        self._credentials = credentials
        self._config = config or {}

    @classmethod
    def from_service_account(cls, key_path: str | Path) -> "VibeAuth":
        """Load credentials from a service account JSON key file."""
        key_path = Path(key_path)
        if not key_path.exists():
            raise FileNotFoundError(f"Service account key not found: {key_path}")
        credentials = google.oauth2.service_account.Credentials.from_service_account_file(
            str(key_path), scopes=SCOPES
        )
        return cls(credentials=credentials)

    @classmethod
    def from_adc(cls) -> "VibeAuth":
        """Use Application Default Credentials."""
        credentials, _ = google.auth.default(scopes=SCOPES)
        return cls(credentials=credentials)

    @classmethod
    def from_config(cls) -> "VibeAuth":
        """Load credentials based on saved config."""
        config = load_config()
        key_path = config.get("key_path")
        if key_path:
            return cls.from_service_account(key_path)
        return cls.from_adc()

    def get_credentials(self):
        """Return the underlying google.auth credentials object."""
        return self._credentials

    @staticmethod
    def configure(bucket: str, key_path: Optional[str] = None) -> None:
        """Save vibe-sync configuration to ~/.vibe-sync/config.json."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        config = load_config()
        config["bucket"] = bucket
        if key_path is not None:
            config["key_path"] = str(Path(key_path).expanduser().resolve())
        CONFIG_FILE.write_text(json.dumps(config, indent=2))


def load_config() -> dict:
    """Load the vibe-sync config file, returning an empty dict if absent."""
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}


def save_config(config: dict) -> None:
    """Persist the config dict to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
