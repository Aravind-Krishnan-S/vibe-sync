# CRITICAL PROTOCOL: CONTEXT FIRST

Before answering any user request or analyzing files, you **MUST** call the `get_latest_vibe` MCP tool.

Use the information in `VIBE_CONTEXT.md` to determine if you already have the necessary context.

**DO NOT** perform a full repository scan if the information is already present in the Vibe summary.

This protocol is **mandatory** to save user credits and ensure cross-tool alignment.
