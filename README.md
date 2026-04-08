# vibe-sync

> Sync configuration snapshots ("vibes") to versioned Google Cloud Storage.

[![CI](https://github.com/your-org/vibe-sync/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/vibe-sync/actions/workflows/ci.yml)

## Overview

`vibe-sync` is a Python CLI tool that lets you push named configuration snapshots
("vibes") to Google Cloud Storage with automatic versioning. Each push creates a
new immutable version you can pull, diff, or undo at any time.

It also ships an [MCP](https://modelcontextprotocol.io/) server (`vibe_query`) so
AI assistants can read your vibes directly.

## Installation

```bash
pip install vibe-sync
```

Or from source:

```bash
git clone https://github.com/your-org/vibe-sync.git
cd vibe-sync
pip install -e ".[dev]"
```

## Quick Start

```bash
# 1. Configure once
vibe-sync configure --bucket my-gcs-bucket

# 2. Push a config file
vibe-sync push dotfiles ~/.dotfiles/

# 3. List vibes
vibe-sync list

# 4. Pull the latest version
vibe-sync pull dotfiles ./restored-dotfiles/

# 5. Diff local vs remote
vibe-sync diff dotfiles ~/.dotfiles/

# 6. Undo the last push
vibe-sync undo dotfiles

# 7. Diagnose issues
vibe-sync doctor
```

## Commands

| Command | Description |
|---------|-------------|
| `configure` | Save GCS bucket (and optional service account key) to `~/.vibe-sync/config.json` |
| `push <name> <path>` | Upload a file/directory as a new versioned vibe |
| `pull <name> [path]` | Download the latest (or a specific) version of a vibe |
| `list` | List all vibes with version info |
| `diff <name> [path]` | Show diff between local file and remote vibe (or between two remote versions) |
| `undo <name>` | Revert a vibe to its previous version |
| `doctor` | Diagnose auth/config/connectivity issues |
| `mcp` | Start the MCP stdio server |

## Authentication

`vibe-sync` supports two authentication modes:

1. **Application Default Credentials (ADC)** – Uses `GOOGLE_APPLICATION_CREDENTIALS` or
   `gcloud auth application-default login`. Recommended for local development.

2. **Service account key** – Pass `--key-path /path/to/key.json` to `configure`.

## MCP Server

Start the MCP server for AI assistant integration:

```bash
vibe-sync mcp
```

The server exposes one tool: **`vibe_query`**

- `vibe_query()` — lists all vibes
- `vibe_query(name="dotfiles")` — returns content + metadata for the latest version
- `vibe_query(name="dotfiles", version=2)` — returns a specific version

## Development

```bash
pip install -e ".[dev]"
ruff check vibe_sync tests   # lint
pytest tests/ -v             # test
```

## License

MIT
