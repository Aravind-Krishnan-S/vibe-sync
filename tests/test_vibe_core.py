"""Tests for vibe_core.py — context creation, stamping, staleness, and diff parsing."""

import os
import time
import textwrap
import pytest

from vibe_core import (
    create_base_context,
    stamp_context,
    get_staleness_info,
    categorize_diff,
    CONTEXT_FILENAME,
    CONTEXT_TEMPLATE,
)


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_tmpdir(tmp_path, monkeypatch):
    """Run every test in its own temp directory."""
    monkeypatch.chdir(tmp_path)
    yield tmp_path


# ── create_base_context ──────────────────────────────────────────────────────

class TestCreateBaseContext:
    def test_creates_file(self):
        create_base_context()
        assert os.path.exists(CONTEXT_FILENAME)

    def test_file_contains_template_sections(self):
        create_base_context()
        with open(CONTEXT_FILENAME) as f:
            content = f.read()
        assert "Architecture & Stack" in content
        assert "Current Progress" in content
        assert "The Next Move" in content
        assert "Last Synced" in content

    def test_does_not_overwrite_existing(self, tmp_path):
        custom = "# My custom context\n"
        (tmp_path / CONTEXT_FILENAME).write_text(custom)
        create_base_context()
        assert (tmp_path / CONTEXT_FILENAME).read_text() == custom

    def test_adds_to_gitignore_when_missing(self):
        create_base_context()
        assert os.path.exists(".gitignore")
        with open(".gitignore") as f:
            content = f.read()
        assert CONTEXT_FILENAME in content

    def test_does_not_duplicate_gitignore_entry(self):
        with open(".gitignore", "w") as f:
            f.write(f"{CONTEXT_FILENAME}\n")
        create_base_context()
        with open(".gitignore") as f:
            content = f.read()
        assert content.count(CONTEXT_FILENAME) == 1


# ── stamp_context ────────────────────────────────────────────────────────────

class TestStampContext:
    def test_stamp_updates_last_synced(self):
        create_base_context()
        stamp_context()
        with open(CONTEXT_FILENAME) as f:
            content = f.read()
        assert "UTC" in content
        # Should not have "Never" anymore
        lines_with_utc = [l for l in content.splitlines() if "UTC" in l]
        assert lines_with_utc

    def test_stamp_replaces_existing_timestamp(self):
        create_base_context()
        stamp_context()
        first_stamp = _read_last_synced_line()
        time.sleep(1)
        stamp_context()
        second_stamp = _read_last_synced_line()
        assert first_stamp != second_stamp

    def test_stamp_appends_section_if_missing(self, tmp_path):
        (tmp_path / CONTEXT_FILENAME).write_text("# Project\n\nSome content.\n")
        stamp_context()
        with open(CONTEXT_FILENAME) as f:
            content = f.read()
        assert "Last Synced" in content


def _read_last_synced_line() -> str:
    with open(CONTEXT_FILENAME) as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if "Last Synced" in line:
            # The timestamp is the next non-empty line
            for j in range(i + 1, len(lines)):
                stripped = lines[j].strip()
                if stripped:
                    return stripped
    return ""


# ── get_staleness_info ───────────────────────────────────────────────────────

class TestGetStalenessInfo:
    def test_stale_when_file_missing(self):
        info = get_staleness_info()
        assert info["is_stale"] is True
        assert "does not exist" in info["warning"]

    def test_not_stale_in_non_git_dir(self, tmp_path):
        (tmp_path / CONTEXT_FILENAME).write_text("# ctx\n")
        info = get_staleness_info()
        # No git repo → no commit timestamps → not stale
        assert info["commits_since_sync"] == 0
        assert info["context_mtime"] is not None


# ── categorize_diff ──────────────────────────────────────────────────────────

class TestCategorizeDiff:
    def test_new_file_detected(self):
        diff = textwrap.dedent("""\
            diff --git a/foo.py b/foo.py
            new file mode 100644
            index 0000000..abc1234
            --- /dev/null
            +++ b/foo.py
            @@ -0,0 +1 @@
            +print("hello")
        """)
        cats = categorize_diff(diff)
        assert "foo.py" in cats["new"]
        assert cats["deleted"] == []

    def test_deleted_file_detected(self):
        diff = textwrap.dedent("""\
            diff --git a/old.py b/old.py
            deleted file mode 100644
            index abc1234..0000000
            --- a/old.py
            +++ /dev/null
        """)
        cats = categorize_diff(diff)
        assert "old.py" in cats["deleted"]
        assert cats["new"] == []

    def test_modified_file_detected(self):
        diff = textwrap.dedent("""\
            diff --git a/main.py b/main.py
            index abc..def 100644
            --- a/main.py
            +++ b/main.py
            @@ -1 +1 @@
            -old
            +new
        """)
        cats = categorize_diff(diff)
        assert "main.py" in cats["modified"]

    def test_empty_diff(self):
        cats = categorize_diff("")
        assert cats == {"new": [], "modified": [], "deleted": []}

    def test_multiple_files(self):
        diff = textwrap.dedent("""\
            diff --git a/a.py b/a.py
            new file mode 100644
            index 0000000..abc
            diff --git a/b.py b/b.py
            deleted file mode 100644
            index abc..0000000
            diff --git a/c.py b/c.py
            index abc..def 100644
        """)
        cats = categorize_diff(diff)
        assert "a.py" in cats["new"]
        assert "b.py" in cats["deleted"]
        assert "c.py" in cats["modified"]
