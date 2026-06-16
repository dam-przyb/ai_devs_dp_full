# S3E2 Task Summary — Firmware / Shell API Agent

---

## 1. 🎯 What Was Accomplished

**Task goal:** Interact with a restricted Linux VM via a custom shell API to configure, unlock, and run `/opt/firmware/cooler/cooler.bin`, extract an ECCS code, and submit it to `/verify` to obtain the flag.

**Deliverables produced:**
- `s3/s3e2/solve_firmware.py` — LangGraph ReAct agent with `shell_cmd` and `submit_answer` tools

**Flag obtained:** `{FLG:CANTTOUCHTHIS}`

**Deferred / skipped:**
- The agent never autonomously completed the full task end-to-end. The final steps (reading `/home/operator/notes/pass.txt`, fixing `test_mode=false`, and running the binary) were executed manually via one-shot Python scripts after the agent was killed.

---

## 2. 🏗️ How the Agent / Solution Was Constructed

### 2a. Architecture Overview

```
User prompt
    │
    ▼
LangGraph ReAct Agent (create_react_agent)
    │
    ├── shell_cmd(cmd) ──► POST https://hub.ag3nts.org/api/shell
    │                          {"apikey": ..., "cmd": "..."}
    │                          ◄── full JSON response
    │
    └── submit_answer(code) ──► POST https://hub.ag3nts.org/verify
                                    {"apikey": ..., "task": "firmware", "answer": {...}}
                                    ◄── {"code": 0, "message": "{FLG:...}"}
```

### 2b. Key Components

#### `shell_cmd` tool
**Purpose:** Executes a single shell command on the remote VM via HTTP POST, with auto-retry on 429/503 and auto-wait on 403 (temporary ban).

```python
@tool
def shell_cmd(cmd: str) -> str:
    payload = {"apikey": API_KEY, "cmd": cmd}
    for attempt in range(max_retries):
        response = httpx.post(SHELL_URL, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            result = json.dumps(data)
            if len(result) > 4000:
                result = result[:4000] + "\n... [TRUNCATED]"
            return result
        elif response.status_code == 403:
            ban_info = response.json().get("ban", {})
            seconds_left = int(ban_info.get("seconds_left", 30))
            time.sleep(seconds_left + 2)
            continue
        elif response.status_code in (429, 503):
            time.sleep(5 * (attempt + 1))
            continue
```

#### `submit_answer` tool
**Purpose:** POSTs the discovered ECCS code to `/verify` and returns the flag from the response.

```python
@tool
def submit_answer(code: str) -> str:
    payload = {"apikey": API_KEY, "task": "firmware", "answer": {"confirmation": code}}
    response = httpx.post(VERIFY_URL, json=payload, timeout=30)
    return response.text
```

#### System Prompt (SYSTEM_PROMPT)
**Purpose:** Enforces a phased, disciplined workflow: read `.gitignore` first, then `settings.ini`, fix line-by-line with verification, find the password via `ls`, then run the binary.

### 2c. Data & Control Flow

```
Agent reads .gitignore → knows forbidden files (.env, storage.cfg, logs/)
    ↓
Reads settings.ini → identifies 3 issues:
    - Line 2: #SAFETY_CHECK=pass (commented) → needs uncomment
    - Line 6: test_mode enabled=true → needs false
    - Line 10: cooling enabled=false → needs true
    ↓
editline calls (one per line) + cat verification after each
    ↓
ls /tmp → finds aidevs4.txt (YouTube URL hint)
ls /home/operator/notes → finds pass.txt → password: "admin1"
    ↓
rm cooler-is-blocked.lock
    ↓
/opt/firmware/cooler/cooler.bin admin1
    → "ECCS-6af4873cdf194e0f3d13a93835a68a5e8c273d8e"
    ↓
POST /verify → {FLG:CANTTOUCHTHIS}
```

---

## 3. 🧱 Main Struggles & How They Were Resolved

### Problem 1: API returns generic descriptions, not actual content
- **Root Cause:** Initial `shell_cmd` implementation only returned `data["message"]` (e.g. "Directory listing.") instead of `data["data"]` which held the actual content.
- **Resolution:** Rewrote the tool to return `json.dumps(data)` (full raw JSON), letting the agent parse the `"data"` field itself. Added 4000-character truncation to prevent context overflow.
- **Takeaway:** When wrapping an unfamiliar API in a tool, always return the full response — never pre-process it unless you've validated the schema.

### Problem 2: Context overflow from `cat cooler.bin`
- **Root Cause:** Claude Sonnet 4.6 attempted to `cat` the binary file (as instructed to "try all ways to find hints"). The binary was ~2M tokens.
- **Resolution:** Added explicit system prompt rule "NEVER cat .bin files" and 4000-char truncation in the tool. Switched to Haiku model for the final successful run (faster, cheaper, and smaller context window forces the agent to be more selective).
- **Takeaway:** Always explicitly forbid obvious failure modes in the system prompt. Truncation in the tool is a safety net, not a substitute.

### Problem 3: Agent hallucinated settings.ini content and line numbers (first Sonnet run)
- **Root Cause:** The initial system prompt said "likely issues are..." — the agent interpreted this as ground truth, skipped the `cat` step, and immediately called `editline` with guessed line numbers. This created duplicate and corrupted entries.
- **Resolution:** Rewrote the system prompt with a "MANDATORY WORKFLOW" structure, labelled each phase explicitly, and added the rule: "NEVER guess line numbers — always read first. After each editline, ALWAYS verify with cat." The VM was rebooted to restore clean state.
- **Takeaway:** "Likely X" in a system prompt is treated as fact by the model. Use conditional language only when you want the agent to explore. Use imperative language ("FIRST do X, THEN do Y") when order is critical.

### Problem 4: `find` command not working
- **Root Cause:** The custom shell API did not support `find` with flags like `-type f` or path arguments that didn't exist — it returned 404 for all `find` invocations attempted. Only `ls <dir>` worked for directory browsing.
- **Resolution:** Discovered manually via direct API calls that `ls /tmp` reveals `aidevs4.txt` and `ls /home/operator/notes` reveals `pass.txt`. Updated the system prompt to use `ls` for navigation instead of `find`.
- **Takeaway:** Never assume standard Linux command flags work in custom/sandboxed shells. The `help` command (or trial-and-error with simple commands) should be the first step.

### Problem 5: Password guessing loop (Haiku run)
- **Root Cause:** The agent found a hint in `.git` directory listing (`🍕+🍌=❤️`) and spent ~15 tool calls guessing emoji-inspired passwords, instead of continuing to explore `ls /tmp` and `ls /home/operator`.
- **Resolution:** Killed the agent and ran manual exploration. The password was in `/home/operator/notes/pass.txt` = `admin1`.
- **Takeaway:** Agents anchor strongly on the first "interesting" clue they find. The system prompt should explicitly instruct: "Do not guess passwords. Explore all readable locations first, then use the actual value found."

### Problem 6: `test_mode enabled=true` still active when binary was first attempted
- **Root Cause:** The previous agent run (Sonnet) had set `cooling enabled=true` but left `test_mode enabled=true`. The binary correctly rejected this with: "Configuration check failed: test mode must be disabled."
- **Resolution:** Read the current `settings.ini`, identified line 6, used `editline` to set `enabled=false`, verified, then re-ran the binary successfully.
- **Takeaway:** After a failed/interrupted agent run, always read the current state of modified files before continuing — don't assume the state matches the last known-good state.

---

## 4. 🤝 User ↔ Coding Agent Interaction Assessment

### 4a. What the User Did Well
- Provided clear security constraints upfront ("respect .gitignore, no /etc, /root, /proc") which were accurately reflected in the system prompt.
- Shared the song lyrics directly when asked, without just saying "look it up yourself" — this unblocked the password hunt quickly (though the actual password was elsewhere).
- Quickly confirmed when to proceed and when to kill a stuck run, keeping the session from spinning out of control indefinitely.
- The Haiku model switch was a good instinct — it reduced hallucination of multi-step plans and produced more disciplined sequential behavior.

### 4b. What Could Be Improved (User Side)
- **"find" command guidance was missing early.** The task description hints that the password is in "several places in the system." Telling the agent to use `ls` for navigation (since `find` doesn't work) earlier would have saved many wasted calls.
- **The YouTube URL hint was a mislead.** Sharing the song lyrics implied the password was song-related. The agent (and human) spent time on this. The real password (`admin1`) was in `notes/pass.txt` which could have been found earlier by simply `ls /home/operator/notes`.
- **No explicit instruction about `.git` directory.** The `.git` directory existed and was explorable, but contained a misleading emoji hint. A note like "ignore .git internals unless you find a real credential file" would have helped.

### 4c. What the Coding Agent Did Well
- **Haiku correctly followed the phased workflow** when the system prompt was structured imperatively (Phase 1 / Phase 2 / Phase 3). It read `.gitignore` first, then `settings.ini`, then edited line-by-line with verification — exactly as instructed.
- **The 403 ban auto-wait logic** worked perfectly: when the first Sonnet run hit the ban for reading `.env`, subsequent tool calls correctly waited out the TTL.
- **The agent correctly identified the `.git` emoji hint** as a potential password source — it was a reasonable inference, just the wrong answer.
- **Context truncation** (4000 chars) prevented the context overflow issue after it was introduced.

### 4d. What the Coding Agent Could Improve
- **Sonnet hallucinated settings.ini content** despite being instructed to "read first." The instruction was not strong enough to override the model's tendency to skip ahead based on "likely" hints in the prompt.
- **Both models over-indexed on the first interesting clue** (emoji in `.git`, YouTube URL) and failed to continue systematic exploration of other directories.
- **`find` command failures were retried many times** before the agent gave up, instead of immediately switching to `ls`-based navigation after the first failure.
- **Password guessing** is a failure mode that a well-designed agent should never enter without exhausting all filesystem search options first.

### 4e. Recommended Prompting Patterns for Next Time

**Pattern 1 — Explicit tool failure fallback:**
```
If a command returns HTTP 404 or "File not found", do NOT retry it with minor variations.
Instead, switch immediately to an alternative approach (e.g. if find fails, use ls).
```

**Pattern 2 — Forbid guessing explicitly:**
```
NEVER guess passwords, file paths, or configuration values.
Only use values you have actually read from the filesystem in this session.
If you cannot find a value, list more directories before making any attempt.
```

**Pattern 3 — Structured exploration checklist:**
```
Before running any binary that requires a password, confirm you have checked ALL of:
- ls /tmp
- ls /home/<user>
- ls /home/<user>/notes (or similar subdirs)
- ls /opt (excluding forbidden dirs)
Only proceed when you have found a credential file or exhausted all options.
```

**Pattern 4 — State verification before continuation:**
```
At the start of each run, read the current state of all files you will modify
(e.g. cat settings.ini) before making any changes. Never assume prior state.
```

---

## 5. 💡 Agentic Patterns Observed

### ReAct (Reasoning + Acting)
- **Manifestation:** The LangGraph `create_react_agent` loop drove the entire agent: think → pick a tool → observe result → think again.
- **Assessment:** Worked well structurally. The main limitation was model quality: Sonnet reasoned better but hallucinated more confidently; Haiku reasoned less but followed explicit workflow steps more faithfully.

### Tool Use
- **Manifestation:** `shell_cmd` (remote shell execution) and `submit_answer` (HTTP POST to /verify). Each shell command was one tool call = one HTTP request, exactly as the task described.
- **Assessment:** Effective. The key design choice of returning raw JSON (instead of pre-processed output) was critical — without it, the agent could not distinguish between success and placeholder messages.

### Human-in-the-Loop (implicit)
- **Manifestation:** The user killed stuck agent runs, manually executed diagnostic commands, and injected discovered knowledge (password location, settings state) back into the next run via updated system prompt and direct scripts.
- **Assessment:** This was necessary and appropriate given the agent's failure modes. The task is complex enough that a fully autonomous run requires a more robust agent design (e.g. explicit "exploration complete" checkpoints before attempting passwords).

### Reflection / Self-Correction
- **Manifestation:** Haiku correctly identified when `settings.ini` edits were getting corrupted (first Sonnet run) and attempted to "rewrite the entire file" — though this failed because `editline` only supports single-line replacement.
- **Assessment:** Partial. The model correctly diagnosed the problem but chose an unavailable tool to fix it. Better tool documentation in the system prompt would have helped.

---

## 6. 🔁 What Would You Do Differently

1. **Start with a pure exploration phase before any editing.** Before touching anything, the agent should `ls` every readable directory at all levels and `cat` every non-binary, non-forbidden file. Present a complete map to the model before Phase 2.

2. **Add an explicit `ls_tree` helper tool** that recursively lists all readable directories (skipping forbidden ones), returning a clean JSON tree. This replaces the broken `find` command and prevents the exploration loop.

3. **Read the binary's `--help` output first** (the API returns usage instructions for unknown args). The usage message `cooler.bin <pass>` would have been found on the first try, not buried in bash history.

4. **Use the `history` command at the start** — the `.bash_history` file revealed everything: the password (`admin1`), the fact that `flaga.txt` was deleted, and all the previous operator's failed attempts. This alone would have solved the task in ~5 tool calls.

5. **Never put "likely X" in the system prompt.** Describe only verified facts or instruct exploration. Hypotheses belong in the agent's reasoning, not in the prompt.

---

## 7. 🧠 Key Learnings

> **[Custom shell APIs]:** Standard Linux commands (`find -type f`, `ls -la`, shell pipes `|`) may not be supported. Always run `help` first and fall back to simple `ls <dir>` for navigation when `find` fails.

> **[System prompt discipline]:** "NEVER guess X" and "ALWAYS read before editing" must be stated as hard rules, not soft recommendations. Models will skip steps they consider "obvious" unless explicitly forbidden from doing so.

> **[Tool output design]:** Return the full raw JSON from any API in your tools. Let the LLM parse it. Pre-processing the output (e.g. extracting one field) hides error structure and makes debugging much harder.

> **[Context overflow protection]:** Binary files can be catastrophically large. Always truncate tool output to a safe limit (e.g. 4000 chars) and explicitly forbid `cat` on `.bin` files in the system prompt.

> **[bash_history is gold]:** In any system where you have access to a user's shell history, read it immediately. It often reveals the exact commands (including passwords) that a human operator tried — even if they failed.

> **[Model selection for structured tasks]:** Smaller, faster models (Haiku) follow explicit step-by-step workflows better than larger models (Sonnet) when the prompt is well-structured. Sonnet's stronger reasoning can work against you when it "decides" a step is unnecessary.

> **[State continuity between runs]:** After killing a failed agent run, the VM state (file edits, deleted files) persists. Always read current state at the start of the next run — don't carry over assumptions from the previous session.

---

## 8. 📦 Reusable Artifacts

| Artifact | Location | Why It's Reusable |
|----------|----------|-------------------|
| `shell_cmd` tool with ban/rate-limit auto-retry | `s3/s3e2/solve_firmware.py` | Any task involving a remote shell API with temporary bans and rate limits |
| `submit_answer` tool pattern | `s3/s3e2/solve_firmware.py` | Standard AI Devs `/verify` submission — same pattern in every task |
| Phased system prompt template (Read → Fix → Find → Run → Submit) | `s3/s3e2/solve_firmware.py` SYSTEM_PROMPT | Applicable to any agent that must modify configuration files before executing a program |
| Ban TTL auto-wait logic | `s3/s3e2/solve_firmware.py` `shell_cmd()` | Reusable for any API that returns `{"ban": {"seconds_left": N}}` on 403 |

---

## 9. 📊 Session Snapshot

| Field | Value |
|-------|-------|
| Lesson / Task | `S3E2` |
| Date completed | `2026-06-10` |
| LangSmith project | Not configured for this task |
| Models used | `anthropic/claude-sonnet-4-6` (initial runs, failed), `anthropic/claude-haiku-4.5` (final agent run, partial), manual Python scripts (final completion) |
| Approx. number of agent turns | ~60 total tool calls across all runs |
| Hardest part | Getting the agent to read files before editing them, and finding the password in `notes/pass.txt` instead of guessing |
| Overall complexity estimate | Medium |
