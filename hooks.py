import os
import stat
import sys

from rich.console import Console

console = Console()

# Cross-platform post-commit hook templates
POSIX_HOOK = """\
#!/bin/sh
# Auto-Vibe: updates VIBE_CONTEXT.md after every commit
COMMIT_MSG=$(git log -1 --pretty=%B)
vibe-sync commit --message "$COMMIT_MSG"
"""

WINDOWS_HOOK = """\
#!/bin/sh
# Auto-Vibe: updates VIBE_CONTEXT.md after every commit
# (Git for Windows runs hooks via its bundled sh, so shell syntax works)
COMMIT_MSG=$(git log -1 --pretty=%B)
python {main_path} commit --message "$COMMIT_MSG"
"""


def _find_git_hooks_dir() -> str:
    """Walk up from cwd to locate the .git/hooks directory."""
    current = os.getcwd()
    while True:
        git_dir = os.path.join(current, ".git")
        if os.path.isdir(git_dir):
            hooks_dir = os.path.join(git_dir, "hooks")
            os.makedirs(hooks_dir, exist_ok=True)
            return hooks_dir
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    raise FileNotFoundError(
        "Could not find a .git directory. Is this a Git repository?"
    )


def install_hooks() -> None:
    """Create (or overwrite) the .git/hooks/post-commit hook."""
    try:
        hooks_dir = _find_git_hooks_dir()
    except FileNotFoundError as e:
        console.print(f"[bold red]❌ {e}[/bold red]")
        return

    hook_path = os.path.join(hooks_dir, "post-commit")

    # Choose the right template
    if sys.platform == "win32":
        main_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "main.py")
        )
        hook_content = WINDOWS_HOOK.format(main_path=main_path)
    else:
        hook_content = POSIX_HOOK

    # Write the hook
    with open(hook_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(hook_content)

    # Make executable (important on macOS/Linux; harmless on Windows)
    st = os.stat(hook_path)
    os.chmod(hook_path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    console.print(f"[bold green]✅ post-commit hook installed at:[/bold green] {hook_path}")
    console.print(
        "[dim]Every future [bold]git commit[/bold] will automatically "
        "update VIBE_CONTEXT.md via the AI Oracle.[/dim]"
    )


PRE_COMMIT_HOOK = """\
#!/bin/sh
# Vibe-Sync pre-commit: warns if VIBE_CONTEXT.md is stale
python -c "
from vibe_core import get_staleness_info
info = get_staleness_info()
if info['is_stale'] and info['commits_since_sync'] >= 3:
    print('⚠️  [vibe-sync] Context is stale (' + str(info['commits_since_sync']) + ' commits behind). Run: vibe-sync commit')
"
exit 0
"""


def install_pre_commit_hook() -> None:
    """Create (or overwrite) the .git/hooks/pre-commit hook."""
    try:
        hooks_dir = _find_git_hooks_dir()
    except FileNotFoundError as e:
        console.print(f"[bold red]❌ {e}[/bold red]")
        return

    hook_path = os.path.join(hooks_dir, "pre-commit")

    with open(hook_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(PRE_COMMIT_HOOK)

    st = os.stat(hook_path)
    os.chmod(hook_path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    console.print(f"[bold green]✅ pre-commit hook installed at:[/bold green] {hook_path}")
    console.print("[dim]Warns when context is 3+ commits stale before every commit.[/dim]")
