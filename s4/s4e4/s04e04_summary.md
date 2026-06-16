# AI_Devs4 Lesson S04E04 Task Summary — Filesystem

## 1. 🎯 What Was Accomplished

- **Goal**: Reconstruct a virtual filesystem based on Natan's notes and submit it to the `/verify` endpoint to receive the flag.
- **Deliverables**:
  - [explore_filesystem.py](file:///c:/zz_projects/ai_devs4_part2/s4/s4e4/explore_filesystem.py): Script querying the `/verify` endpoint for the `help` action.
  - [solve_filesystem.py](file:///c:/zz_projects/ai_devs4_part2/s4/s4e4/solve_filesystem.py): Main logic scripting batch filesystem operations (reset, directory creation, city demands JSON, manager profiles, and goods directories linking back to sellers) and executing the final `done` validation.
  - Run logs saved in `s4/s4e4/run_log/` containing API responses.
- **Scope Skipped/Deferred**: None. The task was completely solved and verified.

---

## 2. 🏗️ How the Agent / Solution Was Constructed

### 2a. Architecture Overview
The solution consists of:
1. **Exploration Phase**: Sent a single request via Python to retrieve API constraints.
2. **Parsing & Assembly Phase**: Defined the data model matching the requirements parsed from `ogłoszenia.txt`, `rozmowy.txt`, and `transakcje.txt`.
3. **Execution Phase**: Sequentially constructed a single large list of `batch_mode` actions to avoid network overhead, sent it to the server, and immediately triggered the `done` action to validate the state and retrieve the flag.

### 2b. Key Components

#### `solve_filesystem.py`
**Purpose:** Prepares directory structure and writes mapped metadata (JSON & Markdown) to remote filesystem in batch mode.
```python
def main():
    actions = []
    # Reset filesystem
    actions.append({"action": "reset"})
    # Create Directories
    actions.append({"action": "createDirectory", "path": "/miasta"})
    actions.append({"action": "createDirectory", "path": "/osoby"})
    actions.append({"action": "createDirectory", "path": "/towary"})
    # Create Files (Miasta, Osoby, Towary)
    # ...
    batch_res = send_actions(actions)
```

### 2c. Data & Control Flow
1. **Input**: Local text documents (`ogłoszenia.txt`, `rozmowy.txt`, `transakcje.txt`) containing unstructured details on managers, demands, and transactions.
2. **Processing**: Normalization of data (removing Polish chars, conversion of names/cities/goods to lowercase to match `^[a-z0-9_]+$`).
3. **Output**: An API post payload submitting a batch of filesystem mutation actions, followed by a post to validation.

---

## 3. 🧱 Main Struggles & How They Were Resolved

- **Problem**: Understanding name constraints and file reference order.
- **Root Cause**: The API endpoint enforces strict validation where Markdown links must point to *existing* files, and all basenames must match `^[a-z0-9_]+$`.
- **Resolution**: Ordered file creations so all target destinations (e.g., `/miasta/opalino`) are created *before* the files pointing to them (e.g., `/osoby/iga_kapecka`, `/towary/chleb`).
- **Takeaway**: Ordering batch executions is critical when reference validation happens dynamically.

---

## 4. 🤝 User ↔ Coding Agent Interaction Assessment

### 4a. What the User Did Well
- Requested running scripts using PowerShell snippets rather than executing commands directly. This conserved token space and kept logs clean.
- Guided the storage of runs in the `run_log` subdirectory.

### 4b. What Could Be Improved (User Side)
- The instructions were clear, concise, and structured. No adjustments needed here.

### 4c. What the Coding Agent Did Well
- Correctly parsed the global uniqueness constraint and regex name pattern from the help payload and applied lowercase transformations.
- Grouped multi-links (e.g., `/towary/chleb` pointing to multiple cities) correctly.

### 4d. What the Coding Agent Could Improve
- Nothing significant; the design was simple and executed smoothly without backtracking.

### 4e. Recommended Prompting Patterns for Next Time
```
Please write a short helper script `explore_<name>.py` to query help or schema from the endpoint `/verify` and output it to `run_log/explore.json` before coding the solution.
```

---

## 5. 💡 Agentic Patterns Observed

- **Reflection / Plan Validation**: Verified the validation schema via the `help` action before writing files.
- **Batch Processing**: Grouped all 33 commands into a single `batch_mode` call to optimize network utilization.

---

## 6. 🔁 What Would You Do Differently

- If doing this from scratch, we might write a lightweight regex script to automatically parse the raw text notes, though manual verification of names/transactions was faster and 100% accurate given the small dataset size (8 cities).

---

## 7. 🧠 Key Learnings

> **API Reference Checks**: When APIs check link validity, directory contents must be generated from leaves up or targets first, then references.
> **Batch Operations**: Grouping requests in `batch_mode` saves API quota and prevents intermediate inconsistent states.

---

## 8. 📦 Reusable Artifacts

| Artifact | Location | Why It's Reusable |
|----------|----------|-------------------|
| `send_actions` helper | [solve_filesystem.py](file:///c:/zz_projects/ai_devs4_part2/s4/s4e4/solve_filesystem.py) | Clean template for batch payloads in `verify`. |

---

## 9. 📊 Session Snapshot

| Field | Value |
|-------|-------|
| Lesson / Task | `S04E04` |
| Date completed | 2026-06-15 |
| LangSmith project | `ai_devs4` |
| Models used | `Gemini 3.5 Flash` |
| Approx. number of agent turns | 3 |
| Hardest part (one line) | Aligning link creation order and name rules (lowercase/no-polish) |
| Overall complexity estimate | Low |
