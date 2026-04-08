"""Tests for vibe_sync.mcp_server."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch


def _get_tool_fn(app):
    """Extract the vibe_query tool function from the MCP app."""
    for name, tool in app._tool_manager._tools.items():
        if name == "vibe_query":
            return tool.fn
    return None


def test_vibe_query_not_configured():
    """When GCS is not configured, return error JSON."""
    with patch("vibe_sync.mcp_server._get_gcs", return_value=None):
        from vibe_sync.mcp_server import build_mcp_app

        app = build_mcp_app()
        tool_fn = _get_tool_fn(app)
        assert tool_fn is not None
        result = tool_fn()
        data = json.loads(result)
        assert "error" in data


def test_vibe_query_list_all():
    """With no name argument, return list of all vibes."""
    mock_gcs = MagicMock()
    mock_gcs.list_vibes.return_value = [{"name": "dotfiles", "current_version": 1, "versions": []}]

    with patch("vibe_sync.mcp_server._get_gcs", return_value=mock_gcs):
        from vibe_sync.mcp_server import build_mcp_app

        app = build_mcp_app()
        tool_fn = _get_tool_fn(app)
        result = tool_fn()
        data = json.loads(result)
        assert "vibes" in data
        assert data["vibes"][0]["name"] == "dotfiles"


def test_vibe_query_single_vibe():
    """With a name argument, return vibe content."""
    mock_gcs = MagicMock()
    mock_gcs.get_manifest.return_value = {
        "name": "dotfiles",
        "current_version": 1,
        "versions": [
            {
                "version": 1,
                "blob_path": "blobs/dotfiles/v1",
                "timestamp": "2024-01-01T00:00:00+00:00",
                "size": 5,
            }
        ],
    }
    mock_gcs.get_blob_content.return_value = b'{"theme":"dark"}'

    with patch("vibe_sync.mcp_server._get_gcs", return_value=mock_gcs):
        from vibe_sync.mcp_server import build_mcp_app

        app = build_mcp_app()
        tool_fn = _get_tool_fn(app)
        result = tool_fn(name="dotfiles")
        data = json.loads(result)
        assert data["name"] == "dotfiles"
        assert data["content"] == '{"theme":"dark"}'


def test_vibe_query_missing_vibe():
    """If vibe not found, return error JSON."""
    mock_gcs = MagicMock()
    mock_gcs.get_manifest.return_value = {"name": "x", "current_version": 0, "versions": []}

    with patch("vibe_sync.mcp_server._get_gcs", return_value=mock_gcs):
        from vibe_sync.mcp_server import build_mcp_app

        app = build_mcp_app()
        tool_fn = _get_tool_fn(app)
        result = tool_fn(name="x")
        data = json.loads(result)
        assert "error" in data
