"""Tests for vibe_sync.operations."""

from __future__ import annotations

import json
from unittest.mock import MagicMock


def _make_gcs():
    return MagicMock()


def test_push_success(tmp_path):
    gcs = _make_gcs()
    gcs.upload.return_value = 1
    test_file = tmp_path / "settings.json"
    test_file.write_bytes(b'{"a":1}')

    from vibe_sync.operations import push

    version = push("settings", test_file, gcs)
    assert version == 1
    gcs.upload.assert_called_once_with("settings", test_file)


def test_push_missing_path_raises(tmp_path):
    import pytest

    from vibe_sync.operations import push

    with pytest.raises(FileNotFoundError):
        push("settings", tmp_path / "nope.json", _make_gcs())


def test_pull_writes_file(tmp_path):
    gcs = _make_gcs()
    gcs.download.return_value = b"content bytes"
    dest = tmp_path / "out.json"

    from vibe_sync.operations import pull

    pull("settings", dest, gcs)
    assert dest.read_bytes() == b"content bytes"


def test_pull_creates_parent_dirs(tmp_path):
    gcs = _make_gcs()
    gcs.download.return_value = b"data"
    dest = tmp_path / "deep" / "nested" / "file.txt"

    from vibe_sync.operations import pull

    pull("settings", dest, gcs)
    assert dest.exists()


def test_undo_vibe(capsys):
    gcs = _make_gcs()
    gcs.undo.return_value = 2

    from vibe_sync.operations import undo_vibe

    undo_vibe("dotfiles", gcs)
    gcs.undo.assert_called_once_with("dotfiles")


def test_diff_vibe_no_differences(tmp_path):
    gcs = _make_gcs()
    content = b"same content"
    gcs.get_blob_content.return_value = content
    local = tmp_path / "file.txt"
    local.write_bytes(content)

    from vibe_sync.operations import diff_vibe

    diff_vibe("file", str(local), gcs)  # should not raise


def test_diff_vibe_text_differences(tmp_path):
    gcs = _make_gcs()
    gcs.get_blob_content.return_value = b"remote content\n"
    local = tmp_path / "file.txt"
    local.write_bytes(b"local content\n")

    from vibe_sync.operations import diff_vibe

    diff_vibe("file", str(local), gcs)  # should not raise


def test_diff_vibe_binary(tmp_path):
    gcs = _make_gcs()
    gcs.get_blob_content.return_value = bytes(range(256))
    local = tmp_path / "file.bin"
    local.write_bytes(bytes(range(200)))

    from vibe_sync.operations import diff_vibe

    diff_vibe("file", str(local), gcs)  # should not raise


def test_diff_vibe_between_versions(tmp_path):
    gcs = _make_gcs()
    manifest = {
        "name": "dotfiles",
        "current_version": 2,
        "versions": [
            {
                "version": 1,
                "blob_path": "blobs/dotfiles/v1",
                "timestamp": "2024-01-01T00:00:00+00:00",
                "size": 5,
            },
            {
                "version": 2,
                "blob_path": "blobs/dotfiles/v2",
                "timestamp": "2024-01-02T00:00:00+00:00",
                "size": 8,
            },
        ],
    }
    gcs.get_manifest.return_value = manifest
    # First call: get_blob_content(name) → latest (v2), second call: get_blob_content(name, v1)
    gcs.get_blob_content.side_effect = [b"v2 content", b"v1 content"]

    from vibe_sync.operations import diff_vibe

    diff_vibe("dotfiles", None, gcs)


def test_doctor_missing_config(tmp_path, monkeypatch):
    missing = tmp_path / "no-config.json"
    monkeypatch.setattr("vibe_sync.operations.console", MagicMock())
    import vibe_sync.auth as auth_mod

    monkeypatch.setattr(auth_mod, "CONFIG_FILE", missing)

    from vibe_sync.operations import doctor

    result = doctor({})
    assert result is False


def test_doctor_with_valid_config(tmp_path, monkeypatch):
    config_dir = tmp_path / ".vibe-sync"
    config_dir.mkdir()
    config_file = config_dir / "config.json"
    config_file.write_text(json.dumps({"bucket": "my-bucket"}))

    monkeypatch.setattr("vibe_sync.operations.console", MagicMock())
    import vibe_sync.auth as auth_mod

    monkeypatch.setattr(auth_mod, "CONFIG_FILE", config_file)

    mock_creds = MagicMock()
    monkeypatch.setattr("google.auth.default", lambda scopes=None: (mock_creds, "proj"))

    mock_gcs = MagicMock()
    mock_gcs.list_vibes.return_value = []

    import vibe_sync.auth as auth_mod2
    import vibe_sync.gcs as gcs_mod

    monkeypatch.setattr(gcs_mod, "VibeGCS", lambda b, c: mock_gcs)
    monkeypatch.setattr(
        auth_mod2,
        "VibeAuth",
        MagicMock(
            from_config=MagicMock(
                return_value=MagicMock(get_credentials=MagicMock(return_value=mock_creds))
            )
        ),
    )

    from vibe_sync.operations import doctor

    result = doctor({"bucket": "my-bucket"})
    assert result is True
