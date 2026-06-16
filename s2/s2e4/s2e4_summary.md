# S2E4 — Mailbox Task Summary

---

## 1. 🎯 What Was Accomplished

**Task goal:** Search a live email inbox via a custom `zmail` API, extract three pieces of intelligence (attack date, employee password, security ticket confirmation code), and submit them to the verification hub to receive the flag.

**Deliverables produced:**
- `s2/s2e4/solve_mailbox.py` — Single-file ReAct LangGraph agent with 6 tools and structured run logging
- `s2/s2e4/run_logs/run_20260604T100605Z.json` — Final successful run log
- This summary file

**Flag obtained:** `{FLG:TRAITOR}`

**Skipped/deferred:** No supervisor layer was built — a single ReAct agent was sufficient for this sequential extraction task. LangSmith tracing was not configured for this task (no `LANGCHAIN_TRACING_V2` env var set).

---

## 2. 🏗️ How the Agent / Solution Was Constructed

### 2a. Architecture Overview

```
User prompt
    │
    ▼
┌─────────────────────────────────────┐
│  ReAct Agent (create_react_agent)   │
│  Model: google/gemini-3-flash-preview│
│                                     │
│  Loop: Reason → Act → Observe       │
└──────────────┬──────────────────────┘
               │ tool calls
    ┌──────────┼──────────────┐
    ▼          ▼              ▼
zmail API   zmail API    hub verify
(search/    (getMessages/ (POST /verify
 inbox/      getThread)    with 3 values)
 help)
```

### 2b. Key Components

#### `zmail_help`
**Purpose:** Discovers all available API actions and their parameter names — called once at the start.
```python
@tool
def zmail_help(page: int = 1) -> str:
    result = _zmail_call({"action": "help", "page": page})
    return json.dumps(result, ensure_ascii=False)
```

#### `zmail_search`
**Purpose:** Gmail-like search across inbox metadata using `from:`, `subject:`, `OR`, `AND` operators.
```python
@tool
def zmail_search(query: str, page: int = 1) -> str:
    result = _zmail_call({"action": "search", "query": query, "page": page})
    return json.dumps(result, ensure_ascii=False)
```

#### `zmail_get_thread`
**Purpose:** Lists all rowIDs/messageIDs in a thread — needed to enumerate all messages in the SEC- ticket thread.
```python
@tool
def zmail_get_thread(thread_id: int) -> str:
    result = _zmail_call({"action": "getThread", "threadID": thread_id})
    return json.dumps(result, ensure_ascii=False)
```

#### `zmail_get_message`
**Purpose:** Fetches the full body of a message by rowID or messageID hash. Uses `action: "getMessages"` (plural) with `ids` param.
```python
@tool
def zmail_get_message(message_id: str) -> str:
    result = _zmail_call({"action": "getMessages", "ids": message_id})
    return json.dumps(result, ensure_ascii=False)
```

#### `hub_verify`
**Purpose:** Submits the three extracted values and reads hub feedback. Detects the flag via regex and logs it.
```python
@tool
def hub_verify(password: str, date: str, confirmation_code: str) -> str:
    payload = {"apikey": API_KEY, "task": TASK_NAME,
               "answer": {"password": password, "date": date,
                          "confirmation_code": confirmation_code}}
    ...
    flag_match = re.search(r"\{FLG:[^}]+\}", result_str)
    if flag_match:
        _log({"type": "flag_found", "flag": flag_match.group(), ...})
```

#### `_zmail_call` (HTTP helper)
**Purpose:** Central HTTP wrapper with rate limiting (5s between calls) and structured logging of every request/response.
```python
def _zmail_call(action_payload: dict[str, Any]) -> dict[str, Any]:
    global _last_call_time
    elapsed = time.monotonic() - _last_call_time
    if elapsed < _RATE_LIMIT_SECONDS:
        time.sleep(_RATE_LIMIT_SECONDS - elapsed)
    ...
```

#### `RunLogCallback`
**Purpose:** LangChain callback handler that captures LLM reasoning text and tool start/end events into the run log.

### 2c. Data & Control Flow

```
1. TASK_PROMPT injected as HumanMessage
2. Agent calls zmail_help → learns action names and params
3. Agent calls zmail_search("from:proton.me") → finds Wiktor's email rowID
4. Agent calls zmail_get_message(rowID) → reads full body → extracts date / password clue
5. Agent calls zmail_search("SEC-") → finds SEC ticket thread
6. Agent calls zmail_get_thread(threadID) → lists all message IDs in thread
7. Agent calls zmail_get_message on each → reads confirmation_code from body
8. Agent calls hub_verify(password, date, confirmation_code) → gets {FLG:TRAITOR}
```

---

## 3. 🧱 Main Struggles & How They Were Resolved

### Problem 1: `create_react_agent` — deprecated `state_modifier` kwarg

- **Problem:** First run crashed immediately with `TypeError: create_react_agent() got unexpected keyword arguments: {'state_modifier': ...}`
- **Root Cause:** LangGraph V1.0 renamed the parameter from `state_modifier` to `prompt`.
- **Resolution:** One-line fix: `state_modifier=SYSTEM_PROMPT` → `prompt=SYSTEM_PROMPT`.
- **Takeaway:** LangGraph is actively evolving; always check the installed version's API. The deprecation warning even points to `langchain.agents.create_agent` which is a different function entirely — don't follow it blindly.

### Problem 2: `zmail_get_message` silently returned the help page for every call

- **Problem:** Every call to `zmail_get_message` returned the full API help/description page instead of message content. The agent spent ~15 iterations trying the same broken tool with different IDs, getting the same wrong result.
- **Root Cause:** The API exposes `action: "getMessages"` (plural) with param `ids`, but the tool was sending `action: "getMessage"` (singular) with param `messageID`. The server silently fell back to returning the help page for any unrecognized action — no error code, status 200.
- **Resolution:** Fixed action name and parameter:
  ```python
  # Before (broken)
  _zmail_call({"action": "getMessage", "messageID": message_id})
  # After (correct)
  _zmail_call({"action": "getMessages", "ids": message_id})
  ```
  The correct action name was visible in the `zmail_help` response from the very first run — it just wasn't noticed until the logs were analyzed carefully.
- **Takeaway:** When an API returns HTTP 200 with a fallback/default response for invalid actions, it is indistinguishable from success at the HTTP layer. Always validate that the response shape matches what the action should return. The `zmail_help` response should have been read in full before implementing any tool.

### Problem 3: Missing `getThread` tool

- **Problem:** Search results expose `threadID` but the original toolset had no way to enumerate all messages in a thread. The SEC- ticket thread contained multiple messages that couldn't be systematically discovered without this tool.
- **Root Cause:** The initial tool design was based on the task description alone, not on the actual API help response.
- **Resolution:** Added `zmail_get_thread` tool using `action: "getThread"` + `threadID` param after reading the actual help output.
- **Takeaway:** Always discover the API's full surface (via `help` or docs) before designing tools. Missing a navigation primitive forces the agent into inefficient workarounds.

### Problem 4: Rate limiting warning

- **Problem:** The API started warning about too-frequent requests.
- **Root Cause:** Initial rate limit was 1.5s between calls — too aggressive for this API.
- **Resolution:** Bumped to 5.0s. The user caught this at runtime.
- **Takeaway:** For unknown APIs, start conservatively at 3–5s and tune down only if needed.

---

## 4. 🤝 User ↔ Coding Agent Interaction Assessment

### 4a. What the User Did Well
- **Interrupted early** when the agent was looping — saved significant time and tokens instead of waiting for a timeout
- **Provided the terminal output** for analysis, which made root cause identification much faster
- **Explicitly asked for a plan** before any code changes — caught missing context about the `getThread` tool
- **Changed the model** to the task-appropriate cheaper model (`gemini-3-flash-preview`) as suggested in the task description
- **Gave clear, scoped instructions**: "extend sleep to 5 sec", "give me the snippet" — no ambiguity

### 4b. What Could Be Improved (User Side)
- The first iteration would have been avoided if the user had asked to **run a quick manual API test** (`zmail_help` + one `getMessages` call) before writing the full agent, to verify the actual parameter names
- The `.env` file was shared late — initial analysis had to be done without knowing key names, causing an unnecessary round of clarifying questions

### 4c. What the Coding Agent Did Well
- **Correctly diagnosed the root cause** from logs: the silent HTTP 200 fallback-to-help pattern is subtle, and the agent identified it from the response shape rather than needing to be told
- **Proposed the minimal fix** — no rewrite, just the specific broken line and the missing tool
- **Read the help API response from the logs** to derive the correct action names rather than guessing
- **Kept the architecture appropriately simple** — correctly argued against a supervisor pattern for a sequential extraction task

### 4d. What the Coding Agent Could Improve
- **Should have run a manual API probe** before implementing all tools — a single `httpx.post` with `action: "help"` in the terminal would have revealed `getMessages`/`ids` before any tool was written
- The `getThread` tool was missing from the initial design despite `threadID` being visible in the task's example API responses — more thorough upfront API analysis needed
- Over-relied on preview log strings (600 char truncated). The actual `ids` param name was present in the tool_end output but the preview was truncated and the agent missed it

### 4e. Recommended Prompting Patterns for Next Time

1. **API discovery first:** "Before writing any tools, run a manual API probe in the terminal using `httpx` or `curl` to get the full `help` response and identify all action names and parameter names."

2. **Validate each tool independently:** "After writing each tool, test it with a direct function call in the terminal before wiring it into the agent."

3. **Probe API failure modes:** "Test what happens when you call the API with an invalid action — check whether it returns an error code or silently falls back to a default response. This affects how tools should validate their outputs."

4. **Rate limit conservatively first:** "Default to 5s between API calls on any unknown external API. Add a note in the tool docstring about the applied rate limit."

---

## 5. 💡 Agentic Patterns Observed

### ReAct (Reason + Act)
- **How it manifested:** The agent used `create_react_agent` from `langgraph.prebuilt`, interleaving LLM reasoning steps with tool calls in a loop. Each tool result was fed back as an observation for the next reasoning step.
- **Assessment:** Worked well for the sequential search-and-extract nature of this task. The agent did show a failure mode: when a tool consistently returns wrong output (the help page), the agent kept retrying the same broken tool rather than escalating or changing strategy, wasting ~15 iterations.

### Tool Use
- **How it manifested:** Six discrete tools encapsulated all external interactions. Each tool had a clear docstring that the LLM used for routing decisions.
- **Assessment:** Clean separation between agent logic and API calls. The critical lesson is that tool docstrings must accurately describe parameter names — misleading docs caused the agent to pass `messageID` instead of `ids`.

### Human-in-the-Loop (implicit)
- **How it manifested:** The user interrupted the running agent manually when it was looping, analyzed the logs, and approved a new plan before changes were made.
- **Assessment:** Essential here — without the interruption the agent would have burned through many more API calls and LLM tokens with no progress. A proper HITL checkpoint (e.g. LangGraph `interrupt_before`) would formalize this pattern.

### Iterative Verification
- **How it manifested:** The `hub_verify` tool returns structured feedback from the hub when answers are wrong, and the agent is instructed to use that feedback to refine its search.
- **Assessment:** Worked as designed in the final run. In earlier broken runs the agent couldn't even get to verification because it couldn't read message bodies.

---

## 6. 🔁 What Would You Do Differently

1. **Start with API exploration, not tool implementation.** Run `zmail_help` manually first, read the full response, map every action name and param before writing a single `@tool` decorator.
2. **Write a 10-line throwaway test script** that calls each API action with hardcoded IDs to verify behavior before wrapping in agent tools.
3. **Add response shape validation inside each tool** — if the API returns `"mode": "read_only"` at the top level, it's the help fallback, not a message. Return an error string to the agent immediately.
4. **Use `perPage: 20`** in `getInbox` calls to reduce the number of pagination calls needed.
5. **Skip `zmail_help` as an agent tool** — call it once in `main()` before the agent starts and inject the result into the system prompt as ground truth. The agent doesn't need to discover the API schema dynamically.

---

## 7. 🧠 Key Learnings

> **Silent API fallback:** When an API returns HTTP 200 with a default/help response for unknown actions, it is invisible to error handling. Always validate response shape, not just status code.

> **Tool parameter names must match API exactly:** A typo in the action name (`getMessage` vs `getMessages`) or param name (`id` vs `ids`) causes silent failure at the API level. Derive names from the actual `help` endpoint response, not from intuition.

> **`getThread` as a navigation primitive:** APIs that organize messages into threads require a thread-listing tool as well as a message-fetching tool. Missing this creates a blind spot for thread-heavy data.

> **LangGraph API churn:** `create_react_agent` parameters change between minor versions (`state_modifier` → `prompt`). Pin or check the installed version before coding.

> **Rate limits need to be discovered empirically:** Start at 5s for unknown APIs. The API in this task gave a warning rather than a hard error — easy to miss in log output.

> **Interrupt early, analyze logs:** When an agent loops on the same action > 3 times with no progress, it's cheaper to stop, read the logs, and find the root cause than to let it continue.

> **ReAct without loop-detection can waste many iterations:** The agent retried `zmail_get_message` 10+ times with identical inputs before trying something else. A simple "if I've called the same tool with the same args 3 times, stop and report the issue" guard would help.

---

## 8. 📦 Reusable Artifacts

| Artifact | Location | Why It's Reusable |
|----------|----------|-------------------|
| `_zmail_call` HTTP helper with rate limiting | `s2/s2e4/solve_mailbox.py:L143` | Pattern for any rate-limited external API call with structured request/response logging |
| `RunLogCallback` LangChain handler | `s2/s2e4/solve_mailbox.py:L100` | Drop-in callback for capturing LLM text + tool start/end into a structured run log |
| `main()` with run-log save in `finally` | `s2/s2e4/solve_mailbox.py:L352` | Guarantees log is saved even on crash — reusable pattern for any agent entrypoint |
| `hub_verify` tool with flag regex detection | `s2/s2e4/solve_mailbox.py:L250` | Pattern for any task that submits an answer and needs to detect the flag in the response |

---

## 9. 📊 Session Snapshot

| Field | Value |
|-------|-------|
| Lesson / Task | `S02E04` |
| Date completed | `2026-06-04` |
| LangSmith project | Not configured |
| Models used | `google/gemini-2.5-flash` (initial runs), `google/gemini-3-flash-preview` (final run) |
| Approx. number of agent turns | ~4 runs; final run ~15 LLM steps |
| Hardest part | `getMessages` vs `getMessage` silent API fallback causing 15-iteration loop |
| Overall complexity estimate | Medium |
