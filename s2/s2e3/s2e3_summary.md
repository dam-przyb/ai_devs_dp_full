# S2E3 — Task Summary: `failure` (Log Compression Agent)

---

## 1. 🎯 What Was Accomplished

**Task goal:** Download a massive power plant failure log (2137 lines), compress only the relevant events to ≤1500 tokens, submit to a verification API, and iterate on technician feedback until a flag is returned.

**Deliverables produced:**
- [`s2/s2e3/solve_failure.py`](solve_failure.py) — complete single-file LangGraph agent solving the task
- [`s2/s2e3/run_logs/run_20260602T182700Z.json`](run_logs/run_20260602T182700Z.json) — full run log with all iteration details
- `failure.log` was provided pre-downloaded by the user; the task did not require building a download step

**Flag obtained:** `{FLG:SQUASHIT}` in 2 submission iterations (3 total LLM compress calls).

**Intentionally skipped:** No LangSmith tracing was configured (the `.env` does not include `LANGCHAIN_TRACING_V2`). This was a deliberate omission — the task was simple enough that the JSON run log served as sufficient observability.

---

## 2. 🏗️ How the Agent / Solution Was Constructed

### 2a. Architecture Overview

```
pre_filter
    │
    ▼
llm_compress ◄────────────────────────────────────────┐
    │                                                   │
    ▼                                                   │
token_check                                             │
    │                                                   │
    ├──(token_count > 1500)──► llm_compress (Case 2)   │
    │                                                   │
    └──(token_count ≤ 1500)──►  submit                 │
                                    │                   │
                                    ├──(flag found)──► save_log ──► END
                                    │
                                    └──(feedback, no flag)─────────┘
                                         (Case 3 compress)
```

The graph is a `StateGraph` with 5 nodes. Two conditional edges drive routing: one off `token_check` (shorten vs. submit) and one off `submit` (done vs. adjust).

### 2b. Key Components

#### `node_pre_filter`
**Purpose:** Rule-based filter reading `failure.log` and retaining only `WARN`, `ERRO`, and `CRIT` lines — no LLM cost.

```python
raw_lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
filtered = [ln for ln in raw_lines if re.search(r"\[(WARN|ERRO|CRIT)\]", ln)]
# 2137 total lines → 890 WARN/ERRO/CRIT kept
```

#### `node_llm_compress`
**Purpose:** Three-case LLM compression logic dispatching different prompts based on where in the workflow we are.

```python
if iteration > 0 and feedback:
    # Case 3: post-submission — incorporate technician feedback
elif compress_attempts > 0 and current_compressed:
    # Case 2: token-limit overshoot — shorten existing output, target 85% of limit
else:
    # Case 1: initial pass — compress 890 pre-filtered lines to ~1200 tokens
```

Post-processing always re-sorts output lines by timestamp to guarantee chronological order:

```python
_ts_pat = re.compile(r"(\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2})")
lines.sort(key=lambda ln: (m := _ts_pat.search(ln)) and m.group(1) or "")
```

#### `node_token_check`
**Purpose:** Exact token counting with `tiktoken` (`cl100k_base` encoding), routing to submit or re-compress.

```python
enc = tiktoken.get_encoding("cl100k_base")
return len(enc.encode(text))
```

#### `node_submit`
**Purpose:** POST to `hub.ag3nts.org/verify`, extract flag via regex, extract technician feedback message.

```python
flag_match = re.search(r"\{FLG:[^}]+\}", resp_text)
feedback = resp_json.get("message") or resp_json.get("hint") or resp_json.get("error")
```

#### `node_save_log`
**Purpose:** Serialize entire run state (all iterations, responses, final compressed log, flag) to a timestamped JSON file in `run_logs/`.

### 2c. Data & Control Flow

1. **Input:** `failure.log` (2137 lines, 250 KB) on disk
2. **pre_filter:** → 890 WARN/ERRO/CRIT lines (list of strings in state)
3. **llm_compress (Case 1):** 890 lines → LLM → raw output → sorted → 1558 tokens (too long)
4. **llm_compress (Case 2):** 1558-token output → LLM shorten → sorted → 1103 tokens (ok)
5. **submit (iter 1):** POST → `code: -948`, feedback: FIRMWARE device unclear
6. **llm_compress (Case 3):** current log + FIRMWARE feedback + source → LLM → sorted → 1166 tokens
7. **submit (iter 2):** POST → `code: 0`, `{FLG:SQUASHIT}`
8. **save_log:** JSON written to `run_logs/run_20260602T182700Z.json`

---

## 3. 🧱 Main Struggles & How They Were Resolved

### Struggle 1: Chronological ordering

- **Problem:** First submission returned `code: -944` — "You did not send the information in chronological order. First offending log line: `2026-06-01 06:30 [WARN] ECCS8 ...`"
- **Root Cause:** The LLM reorganized log entries by component instead of timestamp when producing the compressed output. No sorting was enforced in code.
- **Resolution:** Added a mandatory post-processing step after every LLM call that sorts all output lines by extracted timestamp using a regex `(\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2})`. Sorting is now code-enforced, not prompt-dependent.
- **Takeaway:** Never trust the LLM to maintain strict ordering for structured outputs. Enforce order in code after generation, especially when the output format has a canonical sort key (timestamp, ID, line number, etc.).

### Struggle 2: Infinite re-compress loop

- **Problem:** When the first compression produced 2191 tokens (over limit), the graph routed back to `llm_compress`. But `iteration` was still 0 and `last_feedback` was empty, so the node fell into Case 1 — re-sending the exact same 890 lines with `temperature=0`. The LLM produced identical output. The loop never exited.
- **Root Cause:** The state did not distinguish between "first-time compression" and "over-limit re-compression". Both had `iteration == 0` and no feedback. Case routing in `node_llm_compress` was binary (first vs. feedback), missing the third case.
- **Resolution:** Added `compress_attempts: int` field to `FailureState`. When `compress_attempts > 0` and there is already a `compressed_log`, the node uses Case 2 — it sends only the too-long output and asks specifically for shortening, targeting 85% of the limit for safety margin. `compress_attempts` is reset to 0 after each submission.
- **Takeaway:** When a LangGraph node has different behavior modes, always encode those modes explicitly in state. Do not rely on a single integer counter (`iteration`) to distinguish all cases — add a dedicated field for each dimension of state.

---

## 4. 🤝 User ↔ Coding Agent Interaction Assessment

### 4a. What the User Did Well
- Pre-downloaded `failure.log` independently, eliminating a network-download node from the agent and keeping the graph simpler.
- Gave clear, decisive answers to clarifying questions ("simpler and cheaper is better"), which prevented over-engineering.
- Correctly understood that logging enables restart from the same point, which shaped the run log design.
- Approved the plan without scope creep and let implementation proceed quickly.

### 4b. What Could Be Improved (User Side)
- The task description file (`s2e3taskdescription.txt`) was empty — the agent had to mine the task requirements from the lesson text. Keeping the task description populated would save agent exploration time on future tasks.
- The initial request asked to "re-analyze the first instruction" without clarifying that the task was now specifically the `failure` task (vs. the general lesson topic). This required the agent to re-read and re-parse context that had already been established.

### 4c. What the Coding Agent Did Well
- Recognized immediately that the `s2e3taskdescription.txt` was empty and proactively extracted task requirements from the lesson text.
- Spotted the infinite-loop bug on the second failed run and correctly diagnosed it as a state-routing design flaw (not a prompt issue), then fixed it structurally by adding a new state dimension.
- Enforced chronological ordering in code rather than relying on the prompt after the first rejection — a correct instinct that prevented future rejections on this axis.
- Kept the solution in a single file (`solve_failure.py`) as appropriate for task complexity, resisting the urge to create helper modules.

### 4d. What the Coding Agent Could Improve
- The initial prompt for Case 1 (first compression) asked to target `≤1500 tokens` but the LLM produced 1558, requiring a second LLM call. Asking for ~1200 as a target on the first pass would have avoided this. The fix was applied after the fact — it should have been in the initial design.
- Did not include a safeguard against `compress_attempts` growing unbounded. If the LLM consistently failed to get under the limit, the graph would loop indefinitely. A max compress attempts check should be added.

### 4e. Recommended Prompting Patterns for Next Time

```
# 1. Specify structural ordering constraints explicitly in the architecture discussion
"If the output has a natural sort order (timestamp, ID, sequence number), 
enforce sorting in code post-generation — do not rely on the LLM to maintain it."

# 2. Ask for multi-dimensional state upfront
"When a node behaves differently based on its position in the workflow, 
design a dedicated state field per behavioral dimension rather than 
reusing a single counter."

# 3. Target 80-85% of hard limits in prompts
"When asking an LLM to fit within a hard token/char limit, instruct it to 
target 80-85% of that limit (e.g. 'aim for 1200 tokens, max 1500'). 
This avoids overshoot and costly re-generation."

# 4. Specify what 'feedback' looks like before building the loop
"Before building a submit→feedback→adjust loop, confirm how the API 
surfaces feedback (field name, format). Plan the extraction logic 
(which JSON key, what regex) before writing node_submit."
```

---

## 5. 💡 Agentic Patterns Observed

### Reflection / Feedback Loop
**How it manifested:** After each submission to `hub.ag3nts.org/verify`, the technician feedback (e.g. "unable to determine what happened to device FIRMWARE") was fed back into the compression prompt as explicit guidance for the next iteration.  
**Assessment:** Worked well in practice — the API gave precise, actionable feedback ("device X is unclear"), making the reflection step straightforward. In real-world tasks where feedback is vague, this pattern degrades quickly and needs a structured reflection node to parse and prioritize feedback.

### Map-Reduce (implicit)
**How it manifested:** The pre-filter step (rule-based reduction from 2137 → 890 lines) acts as a cheap "map" filter before the expensive LLM "reduce" step. This is a classic map-reduce split for cost control.  
**Assessment:** Highly effective for cost and speed. The LLM only processed ~17K tokens instead of ~45K. This pattern should be the default for any task involving large text corpora.

### Human-in-the-Loop (via API proxy)
**How it manifested:** The `hub.ag3nts.org/verify` endpoint acts as a human-in-the-loop proxy — technicians review submissions and return structured feedback. The agent uses this as its correction signal.  
**Assessment:** The API-mediated feedback loop is a convenient proxy for true human review. Its precision (naming specific component IDs) made it unusually effective. Real human feedback is rarely this structured.

### Iterative Refinement
**How it manifested:** The agent ran 2 submission iterations with 3 LLM calls total (initial compress → shorten → feedback-adjust). Each iteration improved the output based on concrete rejection signals.  
**Assessment:** Converged fast (2 iterations) because the task space was constrained: a fixed token budget, exact component IDs in feedback, and deterministic validation. For more open-ended tasks, this pattern needs an exit condition beyond just "max iterations."

---

## 6. 🔁 What Would You Do Differently

1. **Target 1200 tokens on first pass** — the initial prompt should say "aim for 1200 tokens" rather than "under 1500". This would avoid the first re-compress call entirely and save one LLM round-trip.

2. **Add `max_compress_attempts` guard** — the shorten loop (Case 2) has no upper bound. A guard (`if compress_attempts >= 5: truncate lines deterministically`) would prevent a potential infinite loop if the LLM refuses to shorten below the limit.

3. **Pre-filter by component ID, not just severity** — the initial filter keeps all WARN/ERRO/CRIT regardless of component. A second pass filtering to known plant components (`ECCS8`, `WTRPMP`, `WTANK07`, `STMTURB12`, `FIRMWARE`, `PWR01`, `WSTPOOL2`) would reduce the LLM input further and produce a more focused first compression.

4. **Parse feedback for component IDs in code** — instead of passing raw feedback text to the LLM and hoping it extracts the component name, use a regex to extract mentioned component IDs and append relevant source lines explicitly. This would be more robust than relying on LLM interpretation.

---

## 7. 🧠 Key Learnings

> **[LangGraph state design]:** When a node has multiple behavioral modes (first run vs. re-run after rejection vs. re-run to shorten), each mode needs a dedicated state field. Reusing `iteration == 0` for multiple meanings causes bugs that are hard to detect from the outside.

> **[LLM output ordering]:** An LLM will reorder structured data (log lines, list items, table rows) without warning, even when prompted to keep it sorted. Always sort outputs with a natural key in code immediately after generation.

> **[Token budget targeting]:** When the hard limit is N tokens, prompt the LLM to target 80–85% of N. At `temperature=0`, the model tends to fill the budget; asking for less headroom consistently leads to overshoot.

> **[Pre-filter before LLM]:** For large-corpus tasks, a cheap rule-based filter (regex severity match, keyword match) before an LLM pass is almost always worth doing. It cuts cost, reduces latency, and produces better compression results by giving the LLM a focused input.

> **[API feedback as reflection signal]:** Structured API feedback (naming exact failing components) is a high-quality reflection signal. Design feedback-loop agents around the assumption that feedback will be structured — build parsers for it rather than feeding raw text back verbatim.

> **[LangGraph `compress_attempts` reset]:** State fields used as local loop counters must be explicitly reset at the right transition points. `compress_attempts` must be reset to 0 after every successful submission — otherwise the next feedback cycle starts in the wrong behavioral mode.

> **[Chronological validation is strict]:** The verification API checks log ordering strictly and rejects on the first out-of-order line. This kind of strict structural validation is common in real-world data pipelines and should be handled at the data-processing layer, not in prompts.

---

## 8. 📦 Reusable Artifacts

| Artifact | Location | Why It's Reusable |
|----------|----------|-------------------|
| `node_pre_filter` (severity regex filter) | `s2/s2e3/solve_failure.py:L96–L109` | Generic pattern for reducing any text log file to significant lines before LLM processing |
| `_count_tokens` utility | `s2/s2e3/solve_failure.py:L66–L69` | Drop-in token counter using `tiktoken` `cl100k_base`; works for GPT-4 family models |
| Three-case LLM compress node | `s2/s2e3/solve_failure.py:L115–L222` | Template for any "compress to budget" + "iterate on feedback" agentic pattern |
| Chronological sort post-processor | `s2/s2e3/solve_failure.py:L205–L214` | One-liner for enforcing timestamp-based line order after any LLM text generation |
| `node_submit` + flag/feedback extraction | `s2/s2e3/solve_failure.py:L225–L274` | Reusable submit-and-parse node pattern for any AI_Devs hub task with feedback loops |
| JSON run log pattern | `s2/s2e3/solve_failure.py:L277–L295` | Per-run timestamped artifact logging; useful for debugging multi-iteration agents |

---

## 9. 📊 Session Snapshot

| Field | Value |
|-------|-------|
| Lesson / Task | `S2E3` — `failure` |
| Date completed | `2026-06-02` |
| LangSmith project | Not configured for this task |
| Models used | `openai/gpt-5-mini` via OpenRouter |
| Approx. LLM calls | 3 (initial compress, shorten, feedback-adjust) |
| Submission iterations | 2 |
| Hardest part | Diagnosing and fixing the infinite re-compress loop caused by ambiguous state case routing |
| Overall complexity estimate | Medium |
