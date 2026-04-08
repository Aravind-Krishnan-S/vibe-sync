"""Tests for vibe_sync.auth."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock


def test_configure_saves_config(tmp_path, monkeypatch):
    """configure() should write bucket (and optionally key_path) to config.json."""
    config_dir = tmp_path / ".vibe-sync"
    config_file = config_dir / "config.json"

    monkeypatch.setattr("vibe_sync.auth.CONFIG_DIR", config_dir)
    monkeypatch.setattr("vibe_sync.auth.CONFIG_FILE", config_file)

    from vibe_sync.auth import VibeAuth

    VibeAuth.configure("my-bucket")
    assert config_file.exists()
    data = json.loads(config_file.read_text())
    assert data["bucket"] == "my-bucket"
    assert "key_path" not in data


def test_configure_saves_key_path(tmp_path, monkeypatch):
    config_dir = tmp_path / ".vibe-sync"
    config_file = config_dir / "config.json"
    key_file = tmp_path / "key.json"
    key_file.write_text("{}")

    monkeypatch.setattr("vibe_sync.auth.CONFIG_DIR", config_dir)
    monkeypatch.setattr("vibe_sync.auth.CONFIG_FILE", config_file)

    from vibe_sync.auth import VibeAuth

    VibeAuth.configure("my-bucket", str(key_file))
    data = json.loads(config_file.read_text())
    assert data["key_path"] == str(key_file)


def test_load_config_missing_returns_empty(tmp_path, monkeypatch):
    missing = tmp_path / "does-not-exist" / "config.json"
    monkeypatch.setattr("vibe_sync.auth.CONFIG_FILE", missing)

    from vibe_sync.auth import load_config

    assert load_config() == {}


def test_load_config_reads_existing(tmp_path, monkeypatch):
    config_dir = tmp_path / ".vibe-sync"
    config_dir.mkdir()
    config_file = config_dir / "config.json"
    config_file.write_text(json.dumps({"bucket": "test-bucket"}))

    monkeypatch.setattr("vibe_sync.auth.CONFIG_FILE", config_file)

    from vibe_sync.auth import load_config

    assert load_config() == {"bucket": "test-bucket"}


def test_from_service_account_missing_raises(tmp_path):
    from vibe_sync.auth import VibeAuth

    with unittest.TestCase().assertRaises(FileNotFoundError):
        VibeAuth.from_service_account(tmp_path / "nonexistent.json")


def test_from_adc(monkeypatch):
    mock_creds = MagicMock()
    monkeypatch.setattr("google.auth.default", lambda scopes=None: (mock_creds, "proj"))

    from vibe_sync.auth import VibeAuth

    auth = VibeAuth.from_adc()
    assert auth.get_credentials() is mock_creds
