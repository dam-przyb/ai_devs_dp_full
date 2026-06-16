# S2E1 Task Summary

## 1. 🎯 What Was Accomplished

**Task goal (one sentence):** Build a minimal, automated solver for task `categorize` that repeatedly resets, fetches fresh CSV data, classifies 10 items under strict token/budget constraints (including forced reactor override), and obtains the final flag.

**Deliverables produced:**
- `s2/s2e1/solve_categorize.py` - end-to-end auto-retry solver.
- `s2/s2e1/flag.json` - persisted accepted result with flag and hub debug payload.

**Scope intentionally skipped/deferred:**
- No LangGraph/agent framework was added because the user explicitly requested a minimal script.
- No external tokenizer integration (e.g., tiktoken) was added; prompt compactness was handled empirically via short prompt variants and hub feedback.

---

## 2. 🏗️ How the Agent / Solution Was Constructed

### 2a. Architecture Overview

The solution is a single Python script with an iterative control loop:

```text
load key -> loop(attempt):
  reset budget -> fetch fresh CSV -> classify all 10 items -> scan for flag
  if flag: save flag.json and exit
  else: switch prompt variant and retry
```

This is a deterministic tool-using automation script (HTTP + CSV parsing + retry policy), not a multi-node graph.

### 2b. Key Components

#### `PROMPT_VARIANTS`
**Purpose:** Keep prompts short and cache-friendly while forcing reactor-related items to `NEU`.

```python
PROMPT_VARIANTS = [
    (
        "Reply DNG or NEU only. "
        "If item is reactor/fuel/cassette/thorium/nuclear related -> NEU always. "
        "Else weapon/explosive/radioactive/toxic/hazard -> DNG, otherwise NEU. "
        "Item: {id} | {description}"
    ),
    (
        "Output only DNG or NEU. "
        "Reactor parts and fuel cassettes are ALWAYS NEU. "
        "Otherwise: firearms, explosives, toxic or radioactive things are DNG; the rest NEU. "
        "Data: {id}; {description}"
    ),
]
```

#### `load_api_key`
**Purpose:** Resolve API key from environment variables and `.env` files (walking up parent directories).

```python
def load_api_key(work_dir: Path) -> str:
    preferred_names = [
        "AG3NTS_API_KEY", "AIDEVS_API_KEY", "AIDEV_API_KEY", "CENTRALA_API_KEY", "API_KEY",
    ]
    for name in preferred_names:
        value = os.environ.get(name, "").strip()
        if value:
            return value

    merged: dict[str, str] = {}
    for env_file in _find_env_files(work_dir):
        merged.update(_parse_env_file(env_file))

    for name in preferred_names:
        value = merged.get(name, "").strip()
        if value:
            return value
    raise RuntimeError("API key not found in env vars or .env files.")
```

#### `fetch_fresh_csv`
**Purpose:** Download the current CSV snapshot before each attempt, then parse items for classification.

```python
def fetch_fresh_csv(api_key: str, work_dir: Path) -> list[Item]:
    csv_url = f"https://hub.ag3nts.org/data/{urllib.parse.quote(api_key)}/{CSV_NAME}"
    with urllib.request.urlopen(csv_url, timeout=30) as response:
        content = response.read().decode("utf-8", errors="replace")

    reader = csv.DictReader(content.splitlines())
    rows: list[Item] = []
    for row in reader:
        item_id = (row.get("code") or "").strip()
        description = (row.get("description") or "").strip()
        if item_id and description:
            rows.append(Item(item_id=item_id, description=description))
    return rows
```

#### `main` retry loop
**Purpose:** Execute the full cycle until a flag appears; rotate prompt variants on failure.

```python
attempt = 0
while True:
    attempt += 1
    prompt_template = PROMPT_VARIANTS[(attempt - 1) % len(PROMPT_VARIANTS)]
    reset_budget(api_key)
    items = fetch_fresh_csv(api_key=api_key, work_dir=work_dir)
    flag, response = run_attempt(api_key=api_key, items=items, prompt_template=prompt_template)
    if flag:
        save_flag(work_dir=work_dir, flag=flag, response=response)
        return 0
```

### 2c. Data & Control Flow

1. Load API key from environment/`.env`.
2. Send `reset` prompt to hub.
3. Fetch latest `categorize.csv` from per-key URL.
4. For each row, format compact classification prompt with `{id}` and `{description}`.
5. POST prompt to `/verify`; inspect response for `{FLG:...}`.
6. If not found after 10 items, switch prompt variant and retry.
7. On success, persist flag and response metadata to `flag.json`.

---

## 3. 🧱 Main Struggles & How They Were Resolved

### Struggle 1
- **Problem:** First full attempt returned HTTP `406 Not Acceptable`.
- **Root Cause:** Hub-side validation/rejection can occur transiently (request formatting/attempt state/timing sensitivity).
- **Resolution:** The solver catches `HTTPError`, logs, waits briefly, and continues with a fresh reset-and-run cycle.
- **Takeaway:** For these challenge APIs, retries with full state reset are mandatory, not optional.

### Struggle 2
- **Problem:** Prompt had to fit a tiny context window while implementing a non-obvious policy override (reactor-related items forced to `NEU`).
- **Root Cause:** Competing constraints: brevity, correctness, and exception logic.
- **Resolution:** Use compact English prompts with explicit override first, then coarse danger heuristic second.
- **Takeaway:** In constrained prompts, place exceptions early and keep static prefix stable for cache benefit.

### Struggle 3
- **Problem:** The script needed to work with local key setup without user micromanagement.
- **Root Cause:** Key variable names differ across environments.
- **Resolution:** Implemented multi-name key lookup plus `.env` discovery in parent directories.
- **Takeaway:** Robust secret resolution reduces setup friction and failed runs.

---

## 4. 🤝 User ↔ Coding Agent Interaction Assessment

### 4a. What the User Did Well
- Specified execution constraints clearly: stay in task folder, use `.env`, automate retries, keep solution minimal.
- Confirmed expected output artifact: save flag as a separate `flag.json` file.
- Gave explicit permission to proceed from analysis to implementation.

### 4b. What Could Be Improved (User Side)
- Providing the exact API key variable name upfront would remove fallback guessing logic.
- Stating preferred summary filename convention earlier (e.g., `s2e1_summary.md` vs `s02e01_summary.md`) would eliminate naming ambiguity.

### 4c. What the Coding Agent Did Well
- Converted the requirement into a fully automated loop instead of manual one-off requests.
- Added resilience for transient API failures (`406`, network issues).
- Persisted full accepted response payload, not only the raw flag, enabling auditability.

### 4d. What the Coding Agent Could Improve
- CSV parsing currently expects `code` field; adding fallback to `id` would better match task text and future schema drift.
- Could add a max-attempt safety cap with explicit fail report to avoid infinite loops in pathological cases.

### 4e. Recommended Prompting Patterns for Next Time

Use these snippets directly:

```text
Before coding: summarize task constraints, list assumptions, then wait for my approval.
```

```text
Implement a minimal script first, then only add complexity if runtime evidence justifies it.
```

```text
For external APIs: include retry logic, structured error handling, and persisted run artifacts from the start.
```

```text
When a task says "fresh data each run", always re-download input at the beginning of every attempt.
```

---

## 5. 💡 Agentic Patterns Observed

1. **Pattern name:** Tool Use
   - **How it manifested:** Programmatic use of HTTP endpoints (`/verify`, CSV download URL) and local filesystem persistence.
   - **Assessment:** Worked well; low overhead and easy to debug.

2. **Pattern name:** Reflection via Iterative Retry
   - **How it manifested:** Rotating prompt variants after unsuccessful attempts.
   - **Assessment:** Effective enough for this task; limited because adaptation was predefined, not dynamically generated from detailed hub diagnostics.

3. **Pattern name:** Human-in-the-Loop Gating
   - **How it manifested:** User requested plan-first and explicit approval before coding.
   - **Assessment:** Improved alignment and prevented over-engineering.

4. **Pattern name:** Cache-Aware Prompt Design
   - **How it manifested:** Stable prefix + variable item data at the end of prompt.
   - **Assessment:** Confirmed beneficial by debug metrics (cached tokens reported).

---

## 6. 🔁 What Would You Do Differently

- Add schema fallback (`code` or `id`) immediately to harden against CSV format changes.
- Add optional `--max-attempts` and `--sleep` CLI params for safer long-running behavior.
- Capture per-item classification telemetry in a run log to support faster prompt tuning.
- Prototype a tiny local rule-checker for obvious reactor override validation before consuming paid API budget.

---

## 7. 🧠 Key Learnings

> **Constrained prompting:** In ultra-short prompts, put non-negotiable exception logic first, then general heuristics.

> **Challenge API reliability:** Treat first-pass HTTP failures as expected operational noise; design retry paths from day one.

> **Cost-aware structure:** Keeping static prompt prefixes stable materially improves cache utilization and budget efficiency.

> **Fresh-data tasks:** If source data is volatile, re-fetching each attempt is critical for reproducibility and correctness.

> **Artifact discipline:** Saving full accepted API payloads (not just final token) makes later audits and summaries much easier.

---

## 8. 📦 Reusable Artifacts

| Artifact | Location | Why It's Reusable |
|----------|----------|-------------------|
| Auto-retry verifier loop | `s2/s2e1/solve_categorize.py` | General pattern for reset -> fetch -> evaluate -> retry challenge tasks |
| Multi-source API key loader | `s2/s2e1/solve_categorize.py` | Reusable in tasks where key naming/environment differs |
| Compact override-first prompt templates | `s2/s2e1/solve_categorize.py` | Reusable strategy for tiny-context classifiers with hard exceptions |
| Flag persistence schema | `s2/s2e1/flag.json` | Standard output artifact for result traceability |

---

## 9. 📊 Session Snapshot

| Field | Value |
|-------|-------|
| Lesson / Task | `S02E01` |
| Date completed | `2026-05-27` |
| LangSmith project | `Not used in this task` |
| Models used | `GPT-5.3-Codex (coding agent), hub internal classifier model` |
| Approx. number of agent turns | `~6` |
| Hardest part (one line) | `Balancing strict token budget with forced reactor->NEU exception and robust retries` |
| Overall complexity estimate | `Medium` |
