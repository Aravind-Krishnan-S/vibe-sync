# 🧠 Vibe-Sync: Step-by-Step Guide & Architecture

Vibe-Sync is an AI context preservation engine designed to maintain a unified, living memory wrapper (`VIBE_CONTEXT.md`) for your projects. 

Instead of an AI assistant having to read a massive file tree and piece together disparate commit messages every time it reboots, Vibe-Sync ensures the AI agent understands exactly what was last made, what is currently being worked on, and where the project needs to go next—all dynamically managed and optimized for token budget.

---

## ⚙️ How It Works (Step-by-Step)

### 1. Initialization and Baseline Creation
* **Command:** `vibe-sync init`
* **Action:** Bootstraps a new `VIBE_CONTEXT.md` file in the root of your project directory. 
* **State:** This file establishes barebone headers like *Architecture & Stack*, *Current Progress*, *Known Issues*, and *The Next Move*.

### 2. Auto-Updating Context via AI (The Commit)
* **Command:** `vibe-sync commit -m "added login"` (or implicitly via the git `post-commit` hook)
* **Action:** 
    1. Vibe-Sync calculates all immediate `git diff` outputs (staged, unstaged, and the last commit).
    2. It sends your existing `VIBE_CONTEXT.md` alongside these pure code changes to **Gemini**.
    3. The AI actively reads the changes and rewrites the `Current Progress` and `The Next Move` sections, accurately reflecting milestones achieved without requiring manual documentation.

### 3. Smart Fallback Mechanism
* **Action:** While rewriting the context, Vibe-Sync attempts to use Google Cloud **Vertex AI** for enterprise performance.
* **Fallback:** If a `403` auth block, billing error, or quota error is encountered, the tool silently catches the exception and falls back to **Core AI Studio** (using the `.env` API key). The developer experiences zero interruptions.

### 4. Background History Compression (Trimmer)
* **Action:** Over time, the `VIBE_CONTEXT.md` will naturally bloat as progress lists grow. Every sync checks the token limits using `tiktoken`.
* **The Threshold:** If the context file crosses **2,000 tokens**.
* **Pruning:** The `trimmer.py` targets the ballooned detailed logs and routes them explicitly to **Gemini 1.5 Flash**. The AI compresses ~20 granular development steps into 5 distinct, high-level **Architectural Milestones**.
* **Storage:** The `VIBE_CONTEXT.md` is updated to replace the massive list with the minimal Milestones. The *raw, original detailed logs* are safely archived into a hidden `.vibe/history_log.json` for backup.

### 5. Efficient Agent Retrieval (MCP Budget Mode)
* **Action:** A new AI agent (like Antigravity or Cursor) attaches to your workspace and invokes the MCP server.
* **Budget Read:** Using `get_latest_vibe`, the MCP Server enforces **Budget Mode**. It purposefully hides the bloated technical debt, known bugs, or old history that isn't immediately relevant. It exclusively returns the **🔥 Hot Path** (latest progress) and **🎯 Active Goals**. You save ~70% on standard context framing tokens.
* **Archive Fallback:** If the agent discovers it is missing crucial historical context during reasoning, it realizes it can call `search_archive("query")` to explicitly parse through the hidden JSON logs to regain its footing—retrieving only what it needs, on-demand.

---

## 📖 Real-World Use Case Example

**The Problem:** You’re spending a week building an exhaustive E-Commerce platform. Every time you open a new AI editor window, you have to spend 150,000 tokens passing in every repository file just so the AI realizes you are working on the Stripe Webhook bug, not the front-end layout. 

**Vibe-Sync in Action:**

**Day 1: Setup & Code**
1. You run `vibe-sync init`. 
2. You build out the database and user authentication.
3. You commit your code natively using `git commit -m "added postgres schema and JWT auth"`. 
4. **Behind the scenes:** The Vibe-Sync `post-commit` hook captures the SQL and Python diffs, sends them to Gemini, and updates `VIBE_CONTEXT.md`. The context now notes that *User Auth* is completed, and *Payment Processing* is the Next Move.

**Day 4: Context Bloat & Compression**
5. You've made 30 more commits. The `VIBE_CONTEXT.md` is loaded with granular details like *"fixed CSS padding on login button"* and *"refactored User table index"*. 
6. On the next commit, the `trimmer.py` catches the file surpassing 2,000 tokens. 
7. Gemini Flash quietly transforms those 30 granular bullet points into 3 high-level milestones: *"1. Core Auth Backend Deployed. 2. Frontend Component Library Formed. 3. Stripe Logic scaffolded"*. The file size massively shrinks while your raw logs are funneled into `.vibe/history_log.json`.

**Day 5: Re-engaging the AI (Budget Mode)**
8. You close your laptop, open a fresh AI agent, and say: *"Help me solve the pending task."*
9. The AI calls the MCP tool `get_latest_vibe`. 
10. **Result:** The MCP server feeds the AI *only* the Hot Path and the Active Goal (*"Configure Stripe Webhooks"*). The AI immediately says *"Let's look at your Stripe implementation,"* completely bypassing the need to read your UI folder.
11. If the AI suddenly needs to know what CSS framework was used on Day 1, it calls `search_archive("CSS")` and silently fetches that specific detail from the history JSON. 

**Conclusion:** You preserved perfect context over multiple days, never had to manually write an update document, and saved hundreds of thousands of tokens by restricting the AI to load only active, relevant goals on boot.
