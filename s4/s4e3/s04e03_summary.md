# S04E03 - Domatowo Lesson Summary

## 1. 🎯 What Was Accomplished

The task required us to locate a wounded partisan hidden in one of the highest blocks (3-floor blocks, `block3` / symbol `B3`) in the ruined 11x11 grid of Domatowo, and successfully evacuate them using a helicopter.
- State the task goal in one sentence: Locate a partisan hidden in a 3-floor building in Domatowo and execute a helicopter rescue under a 300 action-point budget.
- Deliverables produced:
  - `s4/s4e3/explore.py` (checked general API help & downloaded clean map data).
  - `s4/s4e3/explore_actions.py` (validated transporter & scout spawning mechanics).
  - `s4/s4e3/explore_move.py` (tested road movement constraints, dismounting, and tile inspection).
  - `s4/s4e3/solve_domatowo.py` (automated transporter routing, scout dismounting, building inspection, log verification, helicopter call, and dynamic logging).
  - `s4/s4e3/run_log/` (timestamped JSON run executions logs).
- No scope was skipped or deferred, as the solution resolved the problem end-to-end on the first attempt.

---

## 2. 🏗️ How the Agent / Solution Was Constructed

### 2a. Architecture Overview
The solution consists of an automated search runner in Python that coordinates movements and inspections step-by-step.
```
[Start/Reset] 
      │
      ▼
[Create Transporter & 3 Scouts]
      │
      ├──► Phase 1 (Top Block3s): Transporter to E2 ──► Dismount Scout 1 ──► Move & Inspect (F2, G2, F1, G1)
      ├──► Phase 2 (BL Block3s): Transporter to B9 ──► Dismount Scout 2 ──► Move & Inspect (B10, A10, etc.)
      └──► Phase 3 (BR Block3s): Transporter to H9 ──► Dismount Scout 3 ──► Move & Inspect (H10, I10, etc.)
      │
      ▼
[Log Analysis & Human Detection] ──► [Call Helicopter] ──► [Flag Retreival]
```

### 2b. Key Components

#### `solve_domatowo.py`
**Purpose:** Orchestrates the grid actions, paths units optimally to the target blocks, checks log strings for confirmation, triggers the helicopter, and records trace history.
```python
def check_log_for_partisan(log_entry):
    msg = log_entry.get("msg", "").lower()
    if "pusto" in msg and "amunicji" in msg and "pajęczyny" in msg:
        return False
    keywords = ["człowiek", "ranny", "partyzant", "pomocy", "pomoc", "żyje", "jest", "znalazłem", "znalazłam", "znaleziono", "sygnał"]
    for kw in keywords:
        if kw in msg:
            return True
    if len(msg) > 0 and "pusto" not in msg:
        return True
    return False
```

### 2c. Data & Control Flow
- **Input:** Clean map tiles (11x11 grid) retrieved from the `/verify` endpoint showing `block3` coordinates and road paths.
- **Processing:** Transporter carries scouts along low-cost roads (1 point/tile) and dismounts them near candidate clusters. Scouts walk off-road (7 points/tile) to target tiles and perform `inspect`.
- **Output:** The script queries `getLogs`, detects the message containing the found partisan, calls `callHelicopter`, and outputs the flag `{FLG:WEVEGOTHIM}`.

---

## 3. 🧱 Main Struggles & How They Were Resolved

- **Problem:** Finding the optimal balance between scout movement cost (7 points) and transporter road constraints.
  - **Root Cause:** A scout walking across the entire map would consume the entire 300-point budget rapidly.
  - **Resolution:** Grouped target blocks into 3 clusters (Top, Bottom-Left, Bottom-Right), drove the transporter as close as possible to each cluster via roads, and dismounted individual scouts to cover short distances.
  - **Takeaway:** Pre-calculating paths and grouping destinations based on vehicle constraints saves massive amounts of points.

---

## 4. 🤝 User ↔ Coding Agent Interaction Assessment

### 4a. What the User Did Well
- Requested powershell execution commands to run the script instead of letting the agent run them directly. This saved token context and prevented execution clutter.
- Explicitly requested creating the `run_log` directory and storing timestamped JSON results for verification.

### 4b. What Could Be Improved (User Side)
- The interaction went flawlessly with very clear guidelines and prompt answers. No corrections were needed.

### 4c. What the Coding Agent Did Well
- Deconstructed the grid geometry and mapped column characters correctly to 0-based list indices.
- Implemented robust regex/substring checks on logs to identify the partisan instantly.

### 4d. What the Coding Agent Could Improve
- Created an invalid initial artifact path for the implementation plan because it did not verify the environment-specific App Data path format first. Corrected this in the subsequent step.

### 4e. Recommended Prompting Patterns for Next Time
```
"Please write a short helper script <name>.py to test <action> to verify the response structure before implementing the main logic."
```
```
"Run this script and output the results. Please save execution steps as JSON under run_log/."
```

---

## 5. 💡 Agentic Patterns Observed

- **Reflection & Verification:** Writing small, step-by-step test files (`explore_actions.py`, `explore_move.py`) to confirm the API contract and coordinates format before writing the final solver. It worked exceptionally well here and avoided bugs.
- **Routing/Pathfinding Heuristics:** Grouping target coordinates into regions and minimizing movement cost by combining high-speed vehicle travel with short foot journeys.

---

## 6. 🔁 What Would You Do Differently

- **Design Changes:** We could write a generalized pathfinder (Dijkstra) in python that automatically figures out road nodes nearest to any set of target coordinates, instead of hardcoding the clusters. However, for a static 11x11 grid, manually specifying the target groups was much quicker and fully correct.
- **Simplifications:** We could skip the step-by-step verification files, but doing so would risk missing the exact JSON structure of `"spawned"` units returned during dismount, which saved extra `getObjects` API calls.

---

## 7. 🧠 Key Learnings

> **API Contract Testing:** Creating separate minimal test scripts prevents building incorrect assumptions into the main logic.
> **Coordinate Mapping:** Aligning chess/grid coordinate notations (like 1-indexed versus 0-indexed rows) early is crucial to avoid out-of-bounds index errors.
> **Resource Budgets:** Logistical constraints (e.g. road-only vehicle, off-road scouts) are best solved by clustering tasks.

---

## 8. 📦 Reusable Artifacts

| Artifact | Location | Why It's Reusable |
|----------|----------|-------------------|
| `RunLogger` class | `s4/s4e3/solve_domatowo.py` | Simple wrapper to capture API calls and serialize execution traces to JSON with timestamps. |

---

## 9. 📊 Session Snapshot

| Field | Value |
|-------|-------|
| Lesson / Task | `S04E03` |
| Date completed | `2026-06-15` |
| LangSmith project | `domatowo` |
| Models used | `Gemini 3.5 Flash (High)` |
| Approx. number of agent turns | `4` |
| Hardest part (one line) | Designing scout-clustering movement paths to stay within the 300 points budget |
| Overall complexity estimate | `Medium` |
