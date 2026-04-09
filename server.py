"""
Vibe-Sync MCP Server
Exposes project context to AI agents via the Model Context Protocol.
Supports both local filesystem and GCS-backed context reading.
Authentication: set MCP_API_KEY env var to require bearer token on all requests.
"""

import os
import json
import logging
import difflib
from fastmcp import FastMCP

CONTEXT_FILENAME = "VIBE_CONTEXT.md"
logger = logging.getLogger("vibe-sync")

# When deployed to Cloud Run, GCS_BUCKET env var enables cloud-backed reads
GCS_BUCKET = os.environ.get("GCS_BUCKET")
MCP_API_KEY = os.environ.get("MCP_API_KEY")  # Optional: require bearer token for all tool calls


def _check_auth(token: str | None = None) -> bool:
    """Return True if auth passes. If MCP_API_KEY is unset, always allow."""
    if not MCP_API_KEY:
        return True
    return token == MCP_API_KEY


mcp = FastMCP(
    name="vibe-sync",
    instructions=(
        "Vibe-Sync is a project context preservation tool. "
        "Use the get_latest_vibe tool to read the current project state "
        "before exploring the filesystem. This saves tokens and prevents "
        "cold-start waste."
    ),
)


def _auto_init_if_needed() -> str | None:
    """Auto-initialize vibe-sync in cwd if VIBE_CONTEXT.md is missing.

    Returns the path to the newly created context file, or None if init fails.
    """
    context_path = _find_context_file()
    if context_path:
        return context_path  # Already exists, nothing to do

    # No VIBE_CONTEXT.md found anywhere up the tree — auto-init in cwd
    cwd = os.getcwd()
    logger.info("VIBE_CONTEXT.md not found — auto-initializing in %s", cwd)

    try:
        from vibe_core import create_base_context
        from config import init_config

        create_base_context()
        init_config()

        # Verify it was actually created
        candidate = os.path.join(cwd, CONTEXT_FILENAME)
        if os.path.isfile(candidate):
            logger.info("Auto-init successful: %s", candidate)
            return candidate
    except Exception as exc:
        logger.warning("Auto-init failed: %s", exc)

    return None


def _read_context_content() -> str | None:
    """Read VIBE_CONTEXT.md from GCS (if configured) or local filesystem.

    If the file doesn't exist locally, auto-initializes the project first.
    """
    # Cloud mode: read from GCS bucket
    if GCS_BUCKET:
        try:
            from cloud import read_context_from_gcs
            content = read_context_from_gcs(GCS_BUCKET)
            if content and "not found" not in content.lower():
                return content
        except Exception:
            pass  # Fall through to local

    # Local mode: search filesystem (auto-init if missing)
    context_path = _auto_init_if_needed()
    if context_path:
        with open(context_path, "r", encoding="utf-8") as f:
            return f.read()

    return None


@mcp.tool()
def get_latest_vibe() -> str:
    """
    Returns the Budget Mode overview: only the 'Hot Path' and 'Active Goals'.

    Use this tool at the START of every session to understand the project's
    current state, architecture, progress, and next steps — without needing
    to explore the file tree. This budget mode saves ~70% context costs.
    """
    content = _read_context_content()
    if content is None:
        return (
            "⚠️  Auto-initialization failed. "
            "Please run `vibe-sync init` manually in your project directory."
        )

    lines = content.splitlines(keepends=True)

    # --- Build the response ---
    sections: list[str] = []

    if GCS_BUCKET:
        sections.append(f"[Source: gs://{GCS_BUCKET}]")

    sections.append("## 📉 Budget Mode Active: Vibe Summary")

    hot_path = _extract_section(lines, "Hot Path") or _extract_section(lines, "Warm Path") or _extract_section(lines, "Current Progress")
    if hot_path:
        sections.append("## 🔥 Hot Path")
        sections.append(hot_path)

    # Extract active goals from "The Next Move" section
    active_goals = _extract_section(lines, "➡️ The Next Move")
    if active_goals:
        sections.append("\n## 🎯 Active Goals")
        sections.append(active_goals)

    return "\n\n".join(sections)


@mcp.tool()
def read_vibe() -> str:
    """
    Returns the full contents of VIBE_CONTEXT.md.

    Use this as the FIRST action in a new session to load full project context
    in a single read, avoiding expensive file-tree exploration.
    """
    content = _read_context_content()
    if content is None:
        return (
            "⚠️  Auto-initialization failed. "
            "Please run `vibe-sync init` manually in your project directory."
        )

    return content


from typer.testing import CliRunner
from main import app

runner = CliRunner()

@mcp.tool()
def vibe_init() -> str:
    """Initialize a new vibe-sync project in the current directory."""
    result = runner.invoke(app, ["init"])
    return result.stdout

@mcp.tool()
def vibe_commit(message: str | None = None) -> str:
    """Create an AI-powered context commit based on recent Git changes."""
    import importlib
    import ai_bridge
    importlib.reload(ai_bridge)
    import main as main_mod
    main_mod.update_context_via_ai = ai_bridge.update_context_via_ai
    importlib.reload(main_mod)

    # Auto-init if VIBE_CONTEXT.md doesn't exist yet
    _auto_init_if_needed()

    from typer.testing import CliRunner as _CR
    _runner = _CR()
    args = ["commit"]
    if message:
        args.extend(["--message", message])
    result = _runner.invoke(main_mod.app, args)
    return result.stdout

@mcp.tool()
def vibe_install_hooks() -> str:
    """Install a Git post-commit hook to auto-update VIBE_CONTEXT.md on every commit."""
    result = runner.invoke(app, ["install-hooks"])
    return result.stdout

@mcp.tool()
def vibe_bundle(output: str = "vibe_bundle.md") -> str:
    """Bundle the entire project source code into a single Markdown file for AI upload."""
    result = runner.invoke(app, ["bundle", "--output", output])
    return result.stdout

@mcp.tool()
def vibe_status() -> str:
    """Show the current Vibe-Sync project status and sync history."""
    result = runner.invoke(app, ["status"])
    return result.stdout

@mcp.tool()
def vibe_push(target: str = "antigravity") -> str:
    """Push the current VIBE_CONTEXT.md into an AI agent's persistent memory."""
    result = runner.invoke(app, ["push", target])
    return result.stdout

@mcp.tool()
def vibe_mcp_test() -> str:
    """Test MCP server connectivity and verify tools are registered."""
    result = runner.invoke(app, ["mcp-test"])
    return result.stdout

@mcp.tool()
def vibe_cloud_init(bucket: str, project: str | None = None) -> str:
    """Configure Google Cloud Storage for cross-machine context sync."""
    args = ["cloud-init", "--bucket", bucket]
    if project:
        args.extend(["--project", project])
    result = runner.invoke(app, args)
    return result.stdout

@mcp.tool()
def vibe_cloud_push() -> str:
    """Push VIBE_CONTEXT.md and metadata to Google Cloud Storage."""
    result = runner.invoke(app, ["cloud-push"])
    return result.stdout

@mcp.tool()
def vibe_cloud_pull() -> str:
    """Pull the latest VIBE_CONTEXT.md from Google Cloud Storage."""
    result = runner.invoke(app, ["cloud-pull"])
    return result.stdout

@mcp.tool()
def vibe_deploy(project: str | None = None, region: str = "us-central1", service_name: str = "vibe-sync-mcp", dry_run: bool = False) -> str:
    """Deploy the Vibe-Sync MCP server to Google Cloud Run."""
    args = ["deploy", "--region", region, "--name", service_name]
    if project:
        args.extend(["--project", project])
    if dry_run:
        args.append("--dry-run")
    result = runner.invoke(app, args)
    return result.stdout


@mcp.tool()
def vibe_query(section: str, api_key: str | None = None) -> str:
    """
    Return a specific named section from VIBE_CONTEXT.md.

    Instead of loading the entire file, request only the section you need.
    Useful for targeted queries like architecture, known issues, or next steps.

    Args:
        section: Partial heading text to match (e.g. "Architecture", "Next Move", "Progress").
        api_key: Optional API key if MCP_API_KEY is configured on the server.
    """
    if not _check_auth(api_key):
        return "⛔ Unauthorized. Provide the correct api_key."

    content = _read_context_content()
    if content is None:
        return "⚠️ VIBE_CONTEXT.md not found. Run `vibe-sync init` first."

    lines = content.splitlines(keepends=True)
    extracted = _extract_section(lines, section)

    if not extracted:
        # List available sections as a helpful fallback
        headings = [l.strip() for l in lines if l.startswith("## ")]
        available = ", ".join(headings) if headings else "none found"
        return (
            f"⚠️ Section matching '{section}' not found.\n"
            f"Available sections: {available}"
        )

    return f"## {section}\n\n{extracted}"


@mcp.tool()
def vibe_diff(api_key: str | None = None) -> str:
    """
    Show what changed between the current VIBE_CONTEXT.md and the last archived snapshot.

    Use this to understand what the AI agent updated in the last commit,
    without reading the full context file.

    Args:
        api_key: Optional API key if MCP_API_KEY is configured on the server.
    """
    if not _check_auth(api_key):
        return "⛔ Unauthorized. Provide the correct api_key."

    import glob

    archive_dir = os.path.join(os.getcwd(), ".vibe", "snapshots")
    if not os.path.isdir(archive_dir):
        return "⚠️ No snapshots directory found. Run `vibe-sync commit` to create snapshots."

    snapshots = sorted(glob.glob(os.path.join(archive_dir, "context_*.md")))
    if not snapshots:
        return "⚠️ No snapshots found. Run `vibe-sync commit` at least once."

    latest_snapshot = snapshots[-1]
    with open(latest_snapshot, "r", encoding="utf-8") as f:
        old_lines = f.readlines()

    current = _read_context_content()
    if current is None:
        return "⚠️ Current VIBE_CONTEXT.md not found."

    new_lines = current.splitlines(keepends=True)
    delta = list(difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"snapshot/{os.path.basename(latest_snapshot)}",
        tofile="VIBE_CONTEXT.md (current)",
        lineterm="",
    ))

    if not delta:
        return "✅ No changes since last snapshot."

    return "\n".join(delta)


# ── Helpers ──────────────────────────────────────────────────────────────────

@mcp.tool()
def search_archive(query: str) -> str:
    """
    Searches the historical logs in .vibe/history_log.json for specific historical context.
    Use this if you explicitly realize you are missing history during Budget Mode reads.
    """
    current = os.getcwd()
    target_path = None
    while True:
        candidate = os.path.join(current, ".vibe", "history_log.json")
        if os.path.isfile(candidate):
            target_path = candidate
            break
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent

    if not target_path:
        return "⚠️ Archive not found. No history tracked yet."

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            history = json.load(f)
            
        results = []
        query_lower = query.lower()
        for idx, entry in enumerate(history):
            original = entry.get("original_logs", "")
            summary = entry.get("milestones_summary", "")
            if query_lower in original.lower() or query_lower in summary.lower():
                # Provide a snippet of the original log
                original_snippet = (original[:500] + "...") if len(original) > 500 else original
                results.append(f"--- Archive Entry {idx+1} ---\nSummary: {summary}\nLogs Match:\n{original_snippet}")
                
        if not results:
            return f"No results found in archive for query: '{query}'"
            
        return f"Found {len(results)} match(es) in archive:\n\n" + "\n\n".join(results)
    except Exception as e:
        return f"Error reading archive: {e}"


def _find_context_file() -> str | None:
    """Search for VIBE_CONTEXT.md starting from cwd, walking upward."""
    current = os.getcwd()
    while True:
        candidate = os.path.join(current, CONTEXT_FILENAME)
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def _extract_section(lines: list[str], heading_fragment: str) -> str:
    """Pull the text under a heading that contains `heading_fragment`."""
    capturing = False
    captured: list[str] = []
    for line in lines:
        if heading_fragment in line:
            capturing = True
            continue
        if capturing:
            # Stop at the next heading
            if line.startswith("## "):
                break
            captured.append(line)
    return "".join(captured).strip()


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
