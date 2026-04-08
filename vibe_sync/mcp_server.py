"""Model Context Protocol server exposing a vibe_query tool."""

from __future__ import annotations

import json
from typing import Optional


def _get_gcs():
    """Try to build a VibeGCS instance from saved config; return None if not configured."""
    try:
        from vibe_sync.auth import VibeAuth, load_config
        from vibe_sync.gcs import VibeGCS

        config = load_config()
        bucket = config.get("bucket")
        if not bucket:
            return None
        auth = VibeAuth.from_config()
        return VibeGCS(bucket, auth.get_credentials())
    except Exception:
        return None


def build_mcp_app():
    """Build and return the FastMCP application (importable for testing)."""
    from mcp.server.fastmcp import FastMCP

    mcp_app = FastMCP("vibe-sync")

    @mcp_app.tool()
    def vibe_query(name: Optional[str] = None, version: Optional[int] = None) -> str:
        """Query vibes stored in GCS.

        If *name* is omitted, lists all vibes. Otherwise returns the content
        (or metadata) for the named vibe at the given *version* (latest if None).
        """
        gcs = _get_gcs()
        if gcs is None:
            return json.dumps({"error": "vibe-sync not configured", "vibes": []})

        if name is None:
            vibes = gcs.list_vibes()
            return json.dumps({"vibes": vibes})

        try:
            manifest = gcs.get_manifest(name)
            if not manifest["versions"]:
                return json.dumps({"error": f"No versions found for vibe '{name}'"})

            content_bytes = gcs.get_blob_content(name, version)
            try:
                content = content_bytes.decode("utf-8")
                is_text = True
            except UnicodeDecodeError:
                content = f"<binary: {len(content_bytes)} bytes>"
                is_text = False

            return json.dumps(
                {
                    "name": name,
                    "version": version or manifest["current_version"],
                    "is_text": is_text,
                    "content": content,
                    "manifest": manifest,
                }
            )
        except KeyError as exc:
            return json.dumps({"error": str(exc)})

    return mcp_app


def run_server() -> None:
    """Entry point: start the MCP server over stdio."""
    mcp_app = build_mcp_app()
    mcp_app.run(transport="stdio")
