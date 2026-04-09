# Changelog

All notable changes to Vibe-Sync are documented here.

---

## [0.2.0] — 2026-04-08

### Added

**Core Context Engine (`vibe_core.py`)**
- `get_recent_changes(depth=5)` — configurable commit depth (was hardcoded to 1)
- `categorize_diff()` — parses git diffs and tags files as `[NEW]`, `[MODIFIED]`, or `[DELETED]`
- `stamp_context()` — writes the current UTC timestamp into `## 📅 Last Synced` after every commit
- `get_staleness_info()` — compares `VIBE_CONTEXT.md` mtime vs latest commit, returns stale count + warning
- `## 📅 Last Synced` section added to the default context template

**CLI Commands (`main.py`)**
- `vibe-sync undo` — rolls back `VIBE_CONTEXT.md` to the last local snapshot
- `vibe-sync diff` — shows a colored unified diff between current context and last snapshot
- `vibe-sync doctor` — full health check: git repo, context freshness, API keys, GCS config, FastMCP, Cloud Run URL
- `vibe-sync cloud-diff` — shows diff between local context and the version stored in GCS before push/pull
- `vibe-sync commit --dry-run` — prints proposed AI update without modifying any files
- `vibe-sync commit --depth N` — controls how many commits are analyzed (default 5)
- `vibe-sync commit --ci` — plain-text output for use in CI pipelines (no Rich spinners)
- `vibe-sync install-hooks --pre-commit` — installs a pre-commit hook that warns when context is 3+ commits stale
- `vibe-sync bundle --include py,ts` — filter bundle by file extension
- `vibe-sync bundle --exclude txt,md` — exclude extensions from bundle
- `vibe-sync bundle --max-tokens N` — hard token budget; files truncated to fit

**MCP Server (`server.py`)**
- `vibe_query(section)` — retrieve a specific named section from `VIBE_CONTEXT.md` without loading the full file (~70% token savings for targeted queries)
- `vibe_diff()` — shows delta between current context and last snapshot via the MCP protocol
- `MCP_API_KEY` auth middleware — set env var to require bearer token on all MCP tool calls
- Auth param added to `vibe_query` and `vibe_diff` tools

**Cloud (`cloud.py`)**
- `upload_context(versioned=True)` — saves a timestamped backup to `vibes/<project>/history/VIBE_CONTEXT_<ts>.md` before overwriting, preventing accidental data loss

**Git Hooks (`hooks.py`)**
- `install_pre_commit_hook()` — new function for pre-commit staleness warning

**Testing**
- `tests/test_vibe_core.py` — full pytest suite covering: context creation, gitignore handling, `stamp_context`, `get_staleness_info`, `categorize_diff`
- `tests/test_server_tools.py` — MCP tool tests: `vibe_query`, `vibe_diff`, `get_latest_vibe`, `read_vibe`, `search_archive`

**CI/CD**
- `.github/workflows/ci.yml` — GitHub Actions pipeline running pytest on Python 3.11 + 3.12, plus Docker build validation

**Snapshots**
- Local snapshots saved to `.vibe/snapshots/` before every `vibe-sync commit`, enabling `undo` and `diff`

---

## [0.1.0] — 2026-04-05 (initial hackathon submission)

### Added
- `vibe-sync init` — create `VIBE_CONTEXT.md` and `.vibe/config.json`
- `vibe-sync commit` — AI-powered context update via Gemini / Groq / NVIDIA NIM
- `vibe-sync status` — show project health and sync history
- `vibe-sync bundle` — bundle project source into a single markdown file
- `vibe-sync install-hooks` — post-commit hook for automatic context updates
- `vibe-sync push antigravity` — push context into Antigravity's persistent brain
- `vibe-sync cloud-init / cloud-push / cloud-pull` — Google Cloud Storage sync
- `vibe-sync deploy` — deploy MCP server to Google Cloud Run
- `vibe-sync mcp-test` — connectivity and tool registration test
- Custom MCP server (`server.py`) with `get_latest_vibe`, `read_vibe`, `vibe_init`, `vibe_commit`, `search_archive`, `vibe_bundle`, `vibe_status`, `vibe_push`
- Budget Mode in `get_latest_vibe` (returns only Hot Path + Active Goals, ~70% token savings)
- Multi-provider AI fallback chain: Gemini AI Studio → Groq → NVIDIA NIM
- Vertex AI enterprise mode via `USE_VERTEX_AI=true`
- Docker + Google Cloud Run deployment support
