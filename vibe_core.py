import os
from datetime import datetime, timezone

import git
from rich.console import Console

console = Console()

CONTEXT_FILENAME = "VIBE_CONTEXT.md"

CONTEXT_TEMPLATE = """\
# 🧠 VIBE-SYNC PROJECT CONTEXT

## 🏗 Architecture & Stack

[To be filled]

## 🚦 Current Progress

- **Completed Features:** None
- **Work in Progress:** Project Initialized

## 🐛 Known Issues / Technical Debt

None yet.

## ➡️ The Next Move

Define initial architecture.

## 📅 Last Synced

Never

"""


def create_base_context() -> None:
    """Create the VIBE_CONTEXT.md file if it doesn't already exist."""
    if os.path.exists(CONTEXT_FILENAME):
        console.print(
            f"[bold yellow]⚠ {CONTEXT_FILENAME} already exists. Skipping creation.[/bold yellow]"
        )
    else:
        with open(CONTEXT_FILENAME, "w", encoding="utf-8") as f:
            f.write(CONTEXT_TEMPLATE)
        console.print(
            f"[bold green]✅ Created {CONTEXT_FILENAME} successfully.[/bold green]"
        )
        _ensure_gitignored()


def _ensure_gitignored() -> None:
    """Ensure VIBE_CONTEXT.md is included in .gitignore."""
    gitignore_path = ".gitignore"
    if not os.path.exists(gitignore_path):
        with open(gitignore_path, "w", encoding="utf-8") as f:
            f.write(f"{CONTEXT_FILENAME}\n")
        console.print(f"[dim]Added {CONTEXT_FILENAME} to .gitignore[/dim]")
    else:
        with open(gitignore_path, "r", encoding="utf-8") as f:
            content = f.read()
        if CONTEXT_FILENAME not in content:
            with open(gitignore_path, "a", encoding="utf-8") as f:
                if content and not content.endswith("\n"):
                    f.write("\n")
                f.write(
                    f"\n# Ignore VIBE_CONTEXT.md as it may contain sensitive data\n"
                    f"{CONTEXT_FILENAME}\n"
                )
            console.print(f"[dim]Added {CONTEXT_FILENAME} to .gitignore[/dim]")


def stamp_context(filepath: str = CONTEXT_FILENAME) -> None:
    """Update the '## 📅 Last Synced' section with the current UTC time."""
    if not os.path.exists(filepath):
        return
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = content.splitlines(keepends=True)
    new_lines: list[str] = []
    skip_until_next_heading = False

    for line in lines:
        if "📅 Last Synced" in line:
            new_lines.append(line)
            new_lines.append(f"\n{now_str}\n")
            skip_until_next_heading = True
            continue
        if skip_until_next_heading:
            if line.startswith("## "):
                skip_until_next_heading = False
                new_lines.append(line)
        else:
            new_lines.append(line)

    if "📅 Last Synced" not in content:
        new_lines.append(f"\n## 📅 Last Synced\n\n{now_str}\n")

    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


def get_staleness_info() -> dict:
    """Return staleness info comparing VIBE_CONTEXT.md age vs latest commit.

    Returns a dict with:
        - is_stale (bool): True if context is older than the latest commit
        - commits_since_sync (int): commits since last context update
        - context_mtime (str | None): ISO timestamp of VIBE_CONTEXT.md
        - latest_commit_time (str | None): ISO timestamp of latest commit
        - warning (str | None): human-readable warning if stale
    """
    result: dict = {
        "is_stale": False,
        "commits_since_sync": 0,
        "context_mtime": None,
        "latest_commit_time": None,
        "warning": None,
    }

    if not os.path.exists(CONTEXT_FILENAME):
        result["is_stale"] = True
        result["warning"] = f"{CONTEXT_FILENAME} does not exist."
        return result

    ctx_mtime = os.path.getmtime(CONTEXT_FILENAME)
    result["context_mtime"] = datetime.fromtimestamp(ctx_mtime, tz=timezone.utc).isoformat()

    try:
        repo = git.Repo(os.getcwd(), search_parent_directories=True)
        commits = list(repo.iter_commits())
        if not commits:
            return result

        latest_commit = commits[0]
        result["latest_commit_time"] = datetime.fromtimestamp(
            latest_commit.committed_date, tz=timezone.utc
        ).isoformat()

        newer_commits = [c for c in commits if c.committed_date > ctx_mtime]
        result["commits_since_sync"] = len(newer_commits)

        if newer_commits:
            result["is_stale"] = True
            result["warning"] = (
                f"Context is stale — {len(newer_commits)} commit(s) since last sync. "
                "Run [bold]vibe-sync commit[/bold] to update."
            )

    except git.exc.InvalidGitRepositoryError:
        pass

    return result


def categorize_diff(diff_text: str) -> dict:
    """Parse a git diff and label files as NEW, MODIFIED, or DELETED."""
    categorized: dict[str, list[str]] = {"new": [], "modified": [], "deleted": []}
    filepath = ""
    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            parts = line.split(" ")
            filepath = parts[-1][2:] if parts[-1].startswith("b/") else parts[-1]
        elif line.startswith("new file mode"):
            if filepath and filepath not in categorized["new"]:
                categorized["new"].append(filepath)
        elif line.startswith("deleted file mode"):
            if filepath and filepath not in categorized["deleted"]:
                categorized["deleted"].append(filepath)
        elif line.startswith("index "):
            if filepath and filepath not in categorized["new"] and filepath not in categorized["deleted"]:
                if filepath not in categorized["modified"]:
                    categorized["modified"].append(filepath)
    return categorized


def get_recent_changes(depth: int = 5) -> str:
    """Return a combined summary of uncommitted changes and recent commits.

    Args:
        depth: Number of recent commits to include (default 5).
    """
    try:
        repo = git.Repo(os.getcwd(), search_parent_directories=True)
    except git.exc.InvalidGitRepositoryError:
        return "Not a git repository. No history available."

    sections: list[str] = []

    # --- Uncommitted changes ---
    uncommitted_diff = repo.git.diff()
    staged_diff = repo.git.diff("--cached")

    combined_raw = staged_diff + "\n" + uncommitted_diff
    if combined_raw.strip():
        cats = categorize_diff(combined_raw)
        summary_lines = []
        if cats["new"]:
            summary_lines.append(f"**[NEW]** {', '.join(cats['new'])}")
        if cats["modified"]:
            summary_lines.append(f"**[MODIFIED]** {', '.join(cats['modified'])}")
        if cats["deleted"]:
            summary_lines.append(f"**[DELETED]** {', '.join(cats['deleted'])}")

        combined_uncommitted = "\n".join(summary_lines) + "\n\n"
        if staged_diff:
            combined_uncommitted += f"### Staged Changes\n```diff\n{staged_diff}\n```\n\n"
        if uncommitted_diff:
            combined_uncommitted += f"### Unstaged Changes\n```diff\n{uncommitted_diff}\n```\n\n"
        sections.append(f"## Uncommitted Changes\n\n{combined_uncommitted}")
    else:
        sections.append("## Uncommitted Changes\nNo uncommitted changes detected.\n")

    # --- Recent commits (configurable depth) ---
    commits = list(repo.iter_commits(max_count=depth))
    if commits:
        commit_sections = []
        for i, commit in enumerate(commits):
            try:
                diff = repo.git.diff(f"{commit.hexsha}~1", commit.hexsha)
            except git.exc.GitCommandError:
                try:
                    diff = repo.git.show(commit.hexsha, "--format=")
                except git.exc.GitCommandError:
                    diff = ""

            cats = categorize_diff(diff)
            file_summary = []
            if cats["new"]:
                file_summary.append(f"[NEW] {', '.join(cats['new'])}")
            if cats["modified"]:
                file_summary.append(f"[MODIFIED] {', '.join(cats['modified'])}")
            if cats["deleted"]:
                file_summary.append(f"[DELETED] {', '.join(cats['deleted'])}")

            label = "Last Commit" if i == 0 else f"Commit -{i}"
            truncated = diff[:3000] + ("...(truncated)" if len(diff) > 3000 else "")
            commit_sections.append(
                f"### {label}: {commit.hexsha[:8]}\n"
                f"- **Message:** {commit.message.strip()}\n"
                f"- **Author:** {commit.author.name}\n"
                f"- **Files:** {'; '.join(file_summary) if file_summary else 'No file changes'}\n\n"
                f"```diff\n{truncated}\n```\n"
            )
        sections.append("## Recent Commits\n\n" + "\n".join(commit_sections))
    else:
        sections.append("## Recent Commits\nNo commits found in repository.\n")

    return "\n".join(sections)
