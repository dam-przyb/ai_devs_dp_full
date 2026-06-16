# Task Summary: S03E03 - Reactor Navigation

## 1. 🎯 What Was Accomplished
The objective was to navigate a transport robot across a 7x5 reactor grid to install a cooling module, dodging moving reactor blocks via an API.
- **Goal:** Successfully route the robot to the goal location and receive the success flag `{FLG:...}`.
- **Deliverables:**
  - `s3e3_reactor.py`: The main navigation script containing the BFS solver and API client.
  - `s3e3_solver.py`: A scratch script used to develop the BFS logic.
  - `s3e3_test_blocks.py`: A scratch script used to reverse-engineer the block movement physics.
- **Scope skipped:** LangGraph and LLM chains were intentionally skipped for the navigation portion because the environment is deterministic and requires a discrete search algorithm (BFS) rather than probabilistic language generation.

---

## 2. 🏗️ How the Agent / Solution Was Constructed

### 2a. Architecture Overview
The solution is a Python script that acts as an autonomous client. It initializes the reactor state via a REST API, reverse-engineers the physics of the moving obstacles, and uses a Breadth-First Search (BFS) to compute a completely safe path from start to finish before executing it.

### 2b. Key Components

#### `send_command`
**Purpose:** Handles HTTP POST requests to the `/verify` endpoint and returns the parsed JSON state.
```python
def send_command(command):
    payload = {"apikey": API_KEY, "task": "reactor", "answer": {"command": command}}
    response = requests.post(URL, json=payload)
    return response.json()
```

#### `next_blocks`
**Purpose:** Deterministically simulates the position and direction of reactor blocks for the subsequent step, handling the "bounce" mechanics at the top and bottom of the grid.
```python
def next_blocks(blocks):
    # Simulator logic for advancing top_row, bottom_row, and direction
```

#### `solve_bfs`
**Purpose:** Searches the state space `(player_col, blocks_state)` to find a safe sequence of commands to reach the target column.
```python
def solve_bfs(start_col, start_blocks, goal_col):
    # Queue stores: (player_col, blocks, path_of_commands)
```

### 2c. Data & Control Flow
Input (Initial `start` command) → Extract `blocks`, `player_col`, `goal_col` → Compute sequence of safe moves via `solve_bfs` → Loop through moves, sending them to the API via `send_command` → Output (Retrieve the `{FLG:INSTALLED}` flag).

---

## 3. 🧱 Main Struggles & How They Were Resolved

- **Problem:** The API endpoint was undocumented in the prompt (only the path `/verify` was provided).
  - **Root Cause:** Missing context on the base URL for the interactive map API.
  - **Resolution:** I wrote a probe script (`s3e3_test.py`) that tested a list of common AI_Devs domain endpoints until `https://hub.ag3nts.org/verify` returned a 200 OK.
  - **Takeaway:** Automated probing is an effective fallback when documentation is incomplete.

- **Problem:** The initial greedy navigation algorithm crashed the robot.
  - **Root Cause:** A 1-step lookahead (greedy approach) drove the robot into a dead-end column where `wait`, `left`, and `right` would all result in being crushed on the *following* turn.
  - **Resolution:** I abandoned the greedy heuristic and implemented a full Breadth-First Search (BFS) that simulated the future states of the blocks across multiple turns.
  - **Takeaway:** For dynamic obstacle avoidance, state-space search is vastly superior to greedy heuristics.

- **Problem:** Predicting the exact movement of the blocks.
  - **Root Cause:** The blocks bounce at row 1 and row 5. The direction changes immediately at the boundaries, and the data schema needed to be observed.
  - **Resolution:** I created a dedicated script (`s3e3_test_blocks.py`) to sample two consecutive states from the API, mapping out the exact state transitions to ensure my local `next_blocks` simulator was 100% accurate.
  - **Takeaway:** Validate physics/environment assumptions with isolated tests before integrating them into a larger solver.

---

## 4. 🤝 User ↔ Coding Agent Interaction Assessment

### 4a. What the User Did Well
- Provided the exact flag format `{FLG:...}` to explicitly signal the victory condition.
- Allowed me to use my planning phase to map out the strategy before committing to code.

### 4b. What Could Be Improved (User Side)
- Providing the exact base URL for custom APIs saves time. If the domain is atypical (e.g., `hub.ag3nts.org` instead of `centrala.ag3nts.org`), explicitly stating it in the prompt is highly beneficial.

### 4c. What the Coding Agent Did Well
- Recognized the failure of the greedy algorithm immediately from the exception logs.
- Wrote diagnostic scripts (`s3e3_test.py`, `s3e3_test_blocks.py`) instead of blindly guessing API responses.
- Rapidly pivoted from a failed heuristic to a robust computer science algorithm (BFS) to solve the core puzzle.

### 4d. What the Coding Agent Could Improve
- I initially underestimated the puzzle complexity by trying to use a greedy algorithm, which cost an execution cycle.

### 4e. Recommended Prompting Patterns for Next Time
- "When introducing a custom API, please provide the exact Base URL or a sample `curl` command."
- "If the task involves a deterministic puzzle, explicitly suggest whether a standard search algorithm (like BFS/DFS) or an LLM-based agent is preferred."

---

## 5. 💡 Agentic Patterns Observed

- **Pattern name:** Tool Use / Environment Probing
  - **How it manifested:** Creating disposable scripts to probe the API for correct URLs and to map out the block physics before building the main agent.
  - **Assessment:** Highly successful. It prevented me from building a massive architecture on top of flawed assumptions.

- **Pattern name:** Lookahead Planning / Simulation
  - **How it manifested:** The agent used an internal simulator (`next_blocks`) and a search algorithm (`solve_bfs`) to predict the environment's future states and guarantee a safe path.
  - **Assessment:** Necessary and effective. Probabilistic LLM routing would have struggled with the strict spatial logic of this puzzle.

---

## 6. 🔁 What Would You Do Differently
If I were to redo this task, I would:
- Skip the greedy algorithm entirely. Recognizing that it's a dynamic obstacle course, I would immediately jump to building the `next_blocks` simulator and BFS pathfinder.
- Start by dumping the raw JSON of a 2-step API interaction immediately to capture the physics engine rules.

---

## 7. 🧠 Key Learnings

> **API Probing:** When an API base URL is missing, scripting a `requests` loop over known historical domains is much faster than guessing manually.
> **Greedy vs Search:** In environments with cyclical, moving obstacles, 1-step lookahead (greedy) is mathematically unsafe. Full state-space search (BFS/A*) is required to prevent dead ends.
> **Environment Simulation:** Re-implementing an API's state transition function locally enables powerful lookahead pathfinding without hammering the actual API with thousands of speculative requests.

---

## 8. 📦 Reusable Artifacts

| Artifact | Location | Why It's Reusable |
|----------|----------|-------------------|
| BFS Pathfinder | `s3/s3e3/s3e3_reactor.py` | The BFS queue and state-tuple pattern is easily adaptable to any 2D grid pathfinding problem with dynamic obstacles. |
| API Prober | `s3/s3e3/s3e3_test.py` | A quick array-based URL prober is highly reusable when dealing with undocumented endpoints. |

---

## 9. 📊 Session Snapshot

| Field | Value |
|-------|-------|
| Lesson / Task | `S03E03` |
| Date completed | `2026-06-10` |
| LangSmith project | `N/A` |
| Models used | `Gemini 3.1 Pro (High)` |
| Approx. number of agent turns | `6` |
| Hardest part (one line) | `Decoding the bouncing block physics and implementing the BFS state simulator.` |
| Overall complexity estimate | `Medium` |
