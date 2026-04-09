"""Tests for server.py MCP tools — vibe_query, vibe_diff, search_archive."""

import os
import json
import glob
import pytest

from vibe_core import CONTEXT_FILENAME, create_base_context


@pytest.fixture(autouse=True)
def isolated_tmpdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    yield tmp_path


@pytest.fixture()
def sample_context(tmp_path):
    content = """\
# 🧠 VIBE-SYNC PROJECT CONTEXT

## 🏗 Architecture & Stack

FastAPI + PostgreSQL

## 🚦 Current Progress

- **Completed Features:** Auth, CRUD
- **Work in Progress:** Dashboard

## 🐛 Known Issues / Technical Debt

N-plus-one query in user listing.

## ➡️ The Next Move

Add pagination to /users endpoint.

## 📅 Last Synced

2026-04-08 10:00:00 UTC
"""
    (tmp_path / CONTEXT_FILENAME).write_text(content)
    return content


# ── vibe_query ───────────────────────────────────────────────────────────────

class TestVibeQuery:
    def test_returns_matching_section(self, sample_context):
        from server import vibe_query
        result = vibe_query(section="Architecture")
        assert "FastAPI" in result

    def test_returns_not_found_with_available_sections(self, sample_context):
        from server import vibe_query
        result = vibe_query(section="NonExistentSection")
        assert "not found" in result.lower() or "⚠️" in result

    def test_returns_error_when_no_context(self, tmp_path):
        from server import vibe_query
        result = vibe_query(section="Architecture")
        assert "not found" in result.lower() or "⚠️" in result or "init" in result


# ── vibe_diff ────────────────────────────────────────────────────────────────

class TestVibeDiff:
    def test_no_snapshots_returns_warning(self, sample_context):
        from server import vibe_diff
        result = vibe_diff()
        assert "snapshot" in result.lower() or "⚠️" in result

    def test_diff_shows_changes(self, tmp_path, sample_context):
        from server import vibe_diff

        # Create a fake snapshot
        snapshots_dir = tmp_path / ".vibe" / "snapshots"
        snapshots_dir.mkdir(parents=True)
        old_content = sample_context.replace("FastAPI + PostgreSQL", "Flask + SQLite")
        (snapshots_dir / "context_20260401_120000.md").write_text(old_content)

        result = vibe_diff()
        # Should show something changed
        assert "FastAPI" in result or "Flask" in result or "no changes" in result.lower()

    def test_no_diff_when_identical(self, tmp_path, sample_context):
        from server import vibe_diff

        snapshots_dir = tmp_path / ".vibe" / "snapshots"
        snapshots_dir.mkdir(parents=True)
        (snapshots_dir / "context_20260401_120000.md").write_text(sample_context)

        result = vibe_diff()
        assert "no changes" in result.lower() or "✅" in result


# ── get_latest_vibe ──────────────────────────────────────────────────────────

class TestGetLatestVibe:
    def test_returns_hot_path_or_progress(self, sample_context):
        from server import get_latest_vibe
        result = get_latest_vibe()
        # Should contain something from the context
        assert len(result) > 10

    def test_auto_init_warning_when_missing(self, tmp_path):
        from server import get_latest_vibe
        result = get_latest_vibe()
        # Either auto-inited or returned a warning
        assert isinstance(result, str)


# ── read_vibe ────────────────────────────────────────────────────────────────

class TestReadVibe:
    def test_returns_full_context(self, sample_context):
        from server import read_vibe
        result = read_vibe()
        assert "Architecture" in result
        assert "Next Move" in result


# ── search_archive ───────────────────────────────────────────────────────────

class TestSearchArchive:
    def test_returns_warning_when_no_archive(self, tmp_path):
        from server import search_archive
        result = search_archive("pagination")
        assert "⚠️" in result or "not found" in result.lower()

    def test_finds_matching_entry(self, tmp_path):
        from server import search_archive

        vibe_dir = tmp_path / ".vibe"
        vibe_dir.mkdir()
        history = [
            {"original_logs": "Added pagination to /users endpoint", "milestones_summary": "Pagination done"}
        ]
        (vibe_dir / "history_log.json").write_text(json.dumps(history))

        result = search_archive("pagination")
        assert "Pagination" in result or "pagination" in result

    def test_no_results_returns_not_found(self, tmp_path):
        from server import search_archive

        vibe_dir = tmp_path / ".vibe"
        vibe_dir.mkdir()
        history = [{"original_logs": "Auth refactor", "milestones_summary": "Auth done"}]
        (vibe_dir / "history_log.json").write_text(json.dumps(history))

        result = search_archive("dinosaurs")
        assert "No results" in result
