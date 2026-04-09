# ANTIGRAVITY.md — Vibe-Sync Agent Rules

## 🪙 TOKEN CONSERVATION PROTOCOL

These rules are **mandatory** for every session. They exist to eliminate cold-start waste and preserve API credits.

### Rule 1: No Blind Exploration
**NEVER** perform a `ls -R`, `find .`, `tree`, or read the entire file tree upon startup. This is the single biggest source of wasted tokens.

### Rule 2: Read the Vibe First
**ALWAYS** run the `vibe-sync read` command (or call the MCP `read_vibe` tool) as your **very first action** in any session. This gives you full project context in a single, structured read.

### Rule 3: Trust the Vibe
Treat `VIBE_CONTEXT.md` as the **source of truth** for current progress, architecture, and known issues. If a file is not mentioned in the "Active Files" section of the Vibe, **do not read it** unless explicitly asked by the user. Do not speculatively explore the codebase.

### Rule 4: Save the Vibe on Exit
Before ending a session, you **MUST** run `vibe-sync sync` to summarize the work you performed. This saves context for the next agent and prevents the next session from wasting tokens on a "Cold Start" re-read of the entire project.

---

> **TL;DR:** Read the Vibe → Do your work → Save the Vibe. Never explore blindly.
