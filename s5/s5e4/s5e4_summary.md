# AI_Devs4 Lesson Task Summary: S5E4 (goingthere)

## 1. 🎯 What Was Accomplished
We successfully built an autonomous agent that navigates a rocket through a 3x12 grid to reach a base in Grudziądz (column 12), dodging hidden rocks and disarming jamming radars along the way.
- **Deliverables:** `solve_goingthere.py` complete solution, run logs saving game trajectories, and `s5e4_summary.md`.
- **Goal:** Reach column 12 by predicting rock placements from distorted nautical hints and bypassing targeted jamming.

## 2. 🏗️ How the Agent / Solution Was Constructed

### 2a. Architecture Overview
The system is built as a stateful `while` loop wrapped in an automatic retry mechanism `run_until_success()`. It processes the game sequentially, handling radar scanning, hint decoding, movement calculation, and action execution column by column.

### 2b. Key Components
#### `check_and_disarm_radar`
**Purpose:** Queries the frequency scanner, uses regex to check for safety, and falls back to an LLM to extract distorted JSON fields to construct a SHA1 disarm payload.
```python
            disarm_str = f"{detection_code}disarm"
            disarm_hash = hashlib.sha1(disarm_str.encode("utf-8")).hexdigest()
```

#### `parse_hint_for_rock`
**Purpose:** Uses an LLM to interpret nautical/spatial hints (port, starboard, bow) into a strict `[1, 2, 3]` row array using a vehicle-relative directional table.
```python
    response = llm.invoke(prompt)
```

#### `Movement Candidate Filter`
**Purpose:** Filters out illegal moves: grid boundaries, rocks in the target column, and diagonal collisions with rocks in the current column.
```python
            step_log["safe_rows_after_filter"] = [r for r in [1, 2, 3] if r not in stone_rows and r != curr_stone]
```

### 2c. Data & Control Flow
Input state -> Radar check loop (decode & disarm if targeted) -> Hint request -> LLM/Cache hint translation to rock rows -> Candidate filtering & scoring -> Move execution -> State update -> Repeat.

## 3. 🧱 Main Struggles & How They Were Resolved

- **Problem:** Rocket repeatedly crashed randomly, despite the LLM correctly predicting the stone in the next column based on the hints.
- **Root Cause:** A subtle diagonal collision mechanic. If moving from row 2 to row 3, the ship could clip the rock in the *current* column if it was at row 3. The script attempted to account for this but had a critical state bug: `curr_stone` was assigned once from the initial `game_state` and never updated in the loop. It effectively thought every column had the rock layout of column 1.
- **Resolution:** Updated the loop to correctly assign `curr_stone = move_data["currentColumn"]["stoneRow"]` after every successful move.
- **Takeaway:** Always thoroughly audit stateful loops to ensure mutable game state is updated exactly in sync with every successful turn. Static initialization outside of `while` loops is a common trap in step-by-step game environments.

- **Problem:** API 429 Rate Limits and Random 502 / 400 errors.
- **Root Cause:** The AI_Devs API simulates atmospheric noise and is strictly rate-limited against fast LLM execution.
- **Resolution:** Wrapped `requests` calls in a robust retry loop with exponential backoff for 429s, and wrapped the main function in a 10-attempt `run_until_success()` loop to restart the game gracefully if the rocket crashed unpredictably.
- **Takeaway:** Expect the unexpected from external endpoints; treat 500s and 429s as normal control flow that must be mitigated.

## 4. 🤝 User ↔ Coding Agent Interaction Assessment

### 4a. What the User Did Well
The user provided highly detailed debug logs (`run_log.json`) and a thorough post-mortem (`2fail_summary.md`) that significantly accelerated root-cause analysis for the diagonal crash bug.

### 4b. What Could Be Improved (User Side)
Providing the complete code initially alongside the fail summary helps. In this instance, the user provided excellent context.

### 4c. What the Coding Agent Did Well
The agent quickly traced the logical disconnect between the implementation in `solve_goingthere.py` and the identified "diagonal crash" problem from the logs, pinpointing the un-updated `curr_stone` variable precisely.

### 4d. What the Coding Agent Could Improve
Could have caught the un-updated `curr_stone` state during initial code construction before it failed multiple times in production.

### 4e. Recommended Prompting Patterns for Next Time
> **State Loop Verification:** "Please review the while-loop and ensure every variable accessed is properly updated at the end of the tick. Ensure no stale data is carrying over."

## 5. 💡 Agentic Patterns Observed

- **Human-in-the-Loop Feedback:** Manifested when the user captured crash logs and fed them back to the AI agent to debug a deeply nested logical state error. It proved highly effective.
- **Subagent / LLM as Parser:** Manifested using the LLM explicitly to clean up purposely corrupted JSON strings from the radar API. It was extremely robust.

## 6. 🔁 What Would You Do Differently
If redoing the task, I would implement stricter unit tests mocking the exact `move_data` response dictionaries to simulate diagonal moves, which would have caught the un-updated `curr_stone` variable immediately without burning live API requests.

## 7. 🧠 Key Learnings
> **State Management:** Stale reads are the enemy of step-based execution loops. Always verify where every variable in a `while` loop gets its data from per tick.
> **Defensive API Calls:** Always wrap external game engines in retry blocks. Simulate noisy connections natively.
> **LLMs for Parsing:** LLMs are exceptional at recovering structured data from intentionally mangled JSON where regex would require hundreds of edge-case rules.

## 8. 📦 Reusable Artifacts
| Artifact | Location | Why It's Reusable |
|----------|----------|-------------------|
| `parse_distorted_scanner` | `solve_goingthere.py` | A robust pattern for using an LLM to decode deliberately obfuscated or broken JSON responses. |
| `make_request` | `solve_goingthere.py` | Excellent retry wrapper handling 429 backoffs and transient 500 errors gracefully. |

## 9. 📊 Session Snapshot
| Field | Value |
|-------|-------|
| Lesson / Task | S5E4 |
| Date completed | 2026-06-16 |
| LangSmith project | N/A |
| Models used | Claude Opus 4.6 (Thinking), Gemini 3.1 Pro (High) |
| Approx. number of agent turns | 5 |
| Hardest part (one line) | Debugging the stale state bug that caused phantom diagonal collisions. |
| Overall complexity estimate | High |
