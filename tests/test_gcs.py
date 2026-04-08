"""Tests for vibe_sync.gcs."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch


def _make_gcs(bucket_name="test-bucket"):
    """Return a VibeGCS with a mocked storage.Client."""
    with patch("vibe_sync.gcs.storage.Client") as MockClient:
        mock_client = MockClient.return_value
        mock_bucket = MagicMock()
        mock_client.bucket.return_value = mock_bucket

        from vibe_sync.gcs import VibeGCS

        gcs = VibeGCS(bucket_name)
        gcs._client = mock_client
        gcs._bucket = mock_bucket
        return gcs, mock_client, mock_bucket


def _make_blob(exists=True, content=b""):
    blob = MagicMock()
    blob.exists.return_value = exists
    decoded = content.decode() if isinstance(content, bytes) else content
    blob.download_as_text.return_value = decoded
    encoded = content if isinstance(content, bytes) else content.encode()
    blob.download_as_bytes.return_value = encoded
    return blob


def test_get_manifest_missing_returns_empty():
    gcs, _, mock_bucket = _make_gcs()
    blob = _make_blob(exists=False)
    mock_bucket.blob.return_value = blob

    manifest = gcs.get_manifest("dotfiles")
    assert manifest == {"name": "dotfiles", "current_version": 0, "versions": []}


def test_get_manifest_existing():
    gcs, _, mock_bucket = _make_gcs()
    existing = {
        "name": "dotfiles",
        "current_version": 2,
        "versions": [{"version": 1}, {"version": 2}],
    }
    blob = _make_blob(exists=True, content=json.dumps(existing).encode())
    mock_bucket.blob.return_value = blob

    manifest = gcs.get_manifest("dotfiles")
    assert manifest["current_version"] == 2


def test_upload_increments_version(tmp_path):
    gcs, _, mock_bucket = _make_gcs()

    manifest_blob = _make_blob(exists=False)
    data_blob = MagicMock()
    mock_bucket.blob.side_effect = [manifest_blob, data_blob, manifest_blob]

    test_file = tmp_path / "settings.json"
    test_file.write_bytes(b'{"theme":"dark"}')

    version = gcs.upload("dotfiles", test_file)
    assert version == 1
    assert data_blob.upload_from_string.called


def test_download_latest(tmp_path):
    gcs, _, mock_bucket = _make_gcs()

    manifest_data = {
        "name": "dotfiles",
        "current_version": 1,
        "versions": [
            {
                "version": 1,
                "blob_path": "blobs/dotfiles/v1",
                "timestamp": "2024-01-01T00:00:00+00:00",
                "size": 10,
            }
        ],
    }
    manifest_blob = _make_blob(exists=True, content=json.dumps(manifest_data).encode())
    data_blob = _make_blob(content=b"hello world")

    def _blob_factory(path):
        if "manifests" in path:
            return manifest_blob
        return data_blob

    mock_bucket.blob.side_effect = _blob_factory

    data = gcs.download("dotfiles")
    assert data == b"hello world"


def test_download_no_versions_raises():
    gcs, _, mock_bucket = _make_gcs()
    blob = _make_blob(
        exists=True,
        content=json.dumps({"name": "x", "current_version": 0, "versions": []}).encode(),
    )
    mock_bucket.blob.return_value = blob

    import pytest

    with pytest.raises(KeyError):
        gcs.download("x")


def test_undo_removes_latest_version():
    gcs, _, mock_bucket = _make_gcs()

    manifest_data = {
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
    manifest_blob = _make_blob(exists=True, content=json.dumps(manifest_data).encode())
    mock_bucket.blob.return_value = manifest_blob

    prev = gcs.undo("dotfiles")
    assert prev == 1
    # Manifest was saved with only version 1
    saved_content = manifest_blob.upload_from_string.call_args[0][0]
    saved = json.loads(saved_content)
    assert saved["current_version"] == 1
    assert len(saved["versions"]) == 1


def test_undo_single_version_raises():
    gcs, _, mock_bucket = _make_gcs()
    manifest_data = {
        "name": "x",
        "current_version": 1,
        "versions": [
            {
                "version": 1,
                "blob_path": "blobs/x/v1",
                "timestamp": "2024-01-01T00:00:00+00:00",
                "size": 1,
            }
        ],
    }
    blob = _make_blob(exists=True, content=json.dumps(manifest_data).encode())
    mock_bucket.blob.return_value = blob

    import pytest

    with pytest.raises(ValueError):
        gcs.undo("x")


def test_list_vibes():
    gcs, mock_client, mock_bucket = _make_gcs()

    manifest1 = {"name": "dotfiles", "current_version": 1, "versions": [{"version": 1}]}
    manifest2 = {"name": "nvim", "current_version": 2, "versions": [{"version": 1}, {"version": 2}]}

    blob1 = MagicMock()
    blob1.name = "manifests/dotfiles.json"
    blob1.download_as_text.return_value = json.dumps(manifest1)

    blob2 = MagicMock()
    blob2.name = "manifests/nvim.json"
    blob2.download_as_text.return_value = json.dumps(manifest2)

    mock_client.list_blobs.return_value = [blob1, blob2]

    vibes = gcs.list_vibes()
    assert len(vibes) == 2
    names = {v["name"] for v in vibes}
    assert names == {"dotfiles", "nvim"}
