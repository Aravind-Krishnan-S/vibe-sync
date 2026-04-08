"""Google Cloud Storage backend for vibe-sync."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from google.cloud import storage

MANIFEST_PREFIX = "manifests/"
BLOB_PREFIX = "blobs/"


class VibeGCS:
    """Wraps google.cloud.storage to provide versioned vibe storage."""

    def __init__(self, bucket_name: str, credentials=None):
        self._bucket_name = bucket_name
        if credentials is not None:
            self._client = storage.Client(credentials=credentials)
        else:
            self._client = storage.Client()
        self._bucket = self._client.bucket(bucket_name)

    # ------------------------------------------------------------------
    # Manifest helpers
    # ------------------------------------------------------------------

    def _manifest_blob(self, name: str) -> storage.Blob:
        return self._bucket.blob(f"{MANIFEST_PREFIX}{name}.json")

    def get_manifest(self, name: str) -> dict:
        """Return the version manifest for *name*, or an empty manifest."""
        blob = self._manifest_blob(name)
        if not blob.exists():
            return {"name": name, "current_version": 0, "versions": []}
        return json.loads(blob.download_as_text())

    def _save_manifest(self, name: str, manifest: dict) -> None:
        blob = self._manifest_blob(name)
        blob.upload_from_string(json.dumps(manifest, indent=2), content_type="application/json")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def upload(self, name: str, local_path: str | Path) -> int:
        """Upload *local_path* as a new version of vibe *name*.

        Returns the new version number.
        """
        local_path = Path(local_path)
        manifest = self.get_manifest(name)
        new_version = manifest["current_version"] + 1
        blob_path = f"{BLOB_PREFIX}{name}/v{new_version}"
        blob = self._bucket.blob(blob_path)
        data = local_path.read_bytes()
        blob.upload_from_string(data)
        entry = {
            "version": new_version,
            "blob_path": blob_path,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "size": len(data),
        }
        manifest["versions"].append(entry)
        manifest["current_version"] = new_version
        self._save_manifest(name, manifest)
        return new_version

    def download(self, name: str, version: Optional[int] = None) -> bytes:
        """Download and return the bytes for vibe *name* at *version* (latest if None)."""
        manifest = self.get_manifest(name)
        if not manifest["versions"]:
            raise KeyError(f"No versions found for vibe '{name}'")
        entry = _resolve_version(manifest, version)
        blob = self._bucket.blob(entry["blob_path"])
        return blob.download_as_bytes()

    def get_blob_content(self, name: str, version: Optional[int] = None) -> bytes:
        """Alias for download; returns raw bytes."""
        return self.download(name, version)

    def undo(self, name: str) -> int:
        """Revert *name* to the previous version.

        Returns the version number that is now current.
        Raises ValueError if there is only one (or zero) versions.
        """
        manifest = self.get_manifest(name)
        versions = manifest["versions"]
        if len(versions) < 2:
            raise ValueError(f"Vibe '{name}' has no previous version to revert to.")
        # Remove the latest entry
        versions.pop()
        manifest["current_version"] = versions[-1]["version"]
        self._save_manifest(name, manifest)
        return manifest["current_version"]

    def list_vibes(self) -> list[dict]:
        """Return a list of vibe summary dicts."""
        blobs = self._client.list_blobs(self._bucket_name, prefix=MANIFEST_PREFIX)
        vibes = []
        for blob in blobs:
            if not blob.name.endswith(".json"):
                continue
            manifest = json.loads(blob.download_as_text())
            vibes.append(
                {
                    "name": manifest["name"],
                    "current_version": manifest["current_version"],
                    "versions": manifest["versions"],
                }
            )
        return vibes


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _resolve_version(manifest: dict, version: Optional[int]) -> dict:
    versions = manifest["versions"]
    if version is None:
        return versions[-1]
    for entry in versions:
        if entry["version"] == version:
            return entry
    raise KeyError(f"Version {version} not found for vibe '{manifest['name']}'")
