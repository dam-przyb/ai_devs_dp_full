# S03E05 — Niedeterministyczna natura modeli jako przewaga (savethem) Task Summary

---

## 1. 🎯 What Was Accomplished
The goal was to determine and submit an optimal path for a messenger traversing a 10x10 grid map to reach the city of Skolwin, adhering to food (10.0) and fuel (10.0) limits.
- **Deliverables produced:**
  - [explore.py](file:///c:/zz_projects/ai_devs4_part2/s3/s3e5/explore.py): A script to search the `toolsearch` endpoint and query the maps, vehicles, and rules endpoints.
  - [solver.py](file:///c:/zz_projects/ai_devs4_part2/s3/s3e5/solver.py): A state-space Dijkstra/BFS solver that models movement costs, tree penalties, water limits, and the dismount action.
  - [submit.py](file:///c:/zz_projects/ai_devs4_part2/s3/s3e5/submit.py): A verification utility that submits the calculated route payload to `https://hub.ag3nts.org/verify`.
  - [s03e05_summary.md](file:///c:/zz_projects/ai_devs4_part2/s3/s3e5/s03e05_summary.md): This summary.

---

## 2. 🏗️ How the Agent / Solution Was Constructed

### 2a. Architecture Overview
The solution was constructed through a multi-stage offline analysis flow. First, we queried the discovery API. Then, we used the retrieved data to build an offline graph-search solver which generated a JSON payload. Finally, the payload was submitted to retrieve the flag.

```
[Toolsearch API]
       │
       ▼ (reveals /api/books, /api/maps, /api/wehicles)
[explore.py]
       │
       ▼ (retrieves rules, map layout, vehicle consumption parameters)
[solver.py] ──► (Dijkstra/BFS search scaled by 10) ──► s3/s3e5/submission_payload.json
       │
       ▼
[submit.py] ──► [Verification Endpoint] ──► Flag retrieved
```

### 2b. Key Components

#### `explore.py` (Discovery)
**Purpose:** Fetches instructions, vehicle stats, and the map layout.
```python
def query_tool_raw(url, query):
    payload = {"apikey": API_KEY, "query": query}
    try:
        response = requests.post(url, json=payload)
        return {
            "status_code": response.status_code,
            "body": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text
        }
    except Exception as e:
        return {"error": str(e)}
```

#### `solver.py` (Pathfinding)
**Purpose:** Implements state space pruning with integers scaled by 10 to avoid float precision loss during BFS exploration.
```python
# State: (r, c, vehicle)
# Queue element: (r, c, vehicle, food, fuel, path_actions)
# Moves subtract resources based on vehicle configs:
configs = {
    "rocket": {"fuel": 10, "food": 1, "water": False},
    "car": {"fuel": 7, "food": 15, "water": False},
    "horse": {"fuel": 0, "food": 16, "water": True},
    "walk": {"fuel": 0, "food": 25, "water": True}
}
```

### 2c. Data & Control Flow
1. **Tool Discovery:** We search `toolsearch` with keywords about terrain, movement rules, and vehicles.
2. **Metadata Fetching:** We query `/api/books` for legend rules, `/api/maps` with the query `"Skolwin"` for the grid, and `/api/wehicles` with vehicle names to get stats.
3. **Graph Search:** We run a Dijkstra-like algorithm starting at row 7, col 0 (`S`) and reaching row 4, col 8 (`G`).
4. **Verification:** The path `["rocket", "up", "up", "right", "right", "right", "up", "right", "right", "dismount", "right", "right", "right"]` is chosen, as it uses the rocket for speed, dismounts before the water barrier, and walks across water to the destination.

---

## 3. 🧱 Main Struggles & How They Were Resolved

- **Problem:** Requesting `/api/maps` and `/api/wehicles` with descriptive natural language queries returned HTTP 404.
- **Root Cause:** The `/api/maps` endpoint expected only the target city name (e.g., `"Skolwin"`) as the query, and `/api/wehicles` expected only the exact vehicle name (e.g., `"car"`). Additionally, calling `raise_for_status()` hid JSON bodies returned with non-2xx codes.
- **Resolution:** Modified `explore.py` to print the raw JSON response bodies even for 404/400 status codes. This immediately showed the list of allowed inputs: `rocket, horse, walk, car`.
- **Takeaway:** Never suppress the response body on HTTP errors during initial exploration, since many APIs return structured validation/help messages in the body.

---

## 4. 🤝 User ↔ Coding Agent Interaction Assessment

### 4a. What the User Did Well
- Promptly executed the generated scripts in the correct environment (`.venv`) and provided execution output.
- Handled the temporary `.env` key issue manually by hardcoding it directly in the script, maintaining momentum.

### 4b. What Could Be Improved (User Side)
- The initial run of the script failed because `AIDEVSKEY` was not loaded properly from the project-root `.env`. This was quickly resolved.

### 4c. What the Coding Agent Did Well
- Designed the path search algorithm robustly from the start, covering multiple vehicle configuration values (e.g. food: 1.5 vs 1.0 for car).
- Formulated directions accurately relative to row/col matrix changes.

### 4d. What the Coding Agent Could Improve
- Could have anticipated that `/api/maps` and `/api/wehicles` would return 404 on invalid parameters and printed their body from the first iteration.

### 4e. Recommended Prompting Patterns for Next Time
When working with custom API endpoints:
```markdown
"Always output the raw HTTP body on error states instead of failing silently with raise_for_status()."
```

---

## 5. 💡 Agentic Patterns Observed
- **Tool Discovery (MCP-like pattern):** We used a search directory to discover endpoints and query parameters, which then enabled downstream solver design.
- **Simulation and Verification:** We simulated the path rules locally to guarantee validity before calling the external verify endpoint.

---

## 6. 🔁 What Would You Do Differently
- Probe the tools using simple values (like `"car"`, `"Skolwin"`) directly rather than long English queries.
- Build a generic web request tool to query the endpoints dynamically from the start.

---

## 7. 🧠 Key Learnings
> **[API Error Inspection]:** API endpoints (even those returning 404/400 status codes) often return useful validation error payloads listing supported values.
> **[Integer Resource Scaling]:** Scale floating point resource limits (e.g., 0.1, 1.5, 0.7) by multiplying by 10 to use exact integer comparisons inside Dijkstra/BFS pathfinding algorithms.
> **[Pathfinding State Pruning]:** Keep a list of Pareto-optimal values (e.g., food, fuel) for each visited coordinate-vehicle state to prune sub-optimal paths quickly.

---

## 8. 📦 Reusable Artifacts

| Artifact | Location | Why It's Reusable |
|----------|----------|-------------------|
| State Pruning Solver | [solver.py](file:///c:/zz_projects/ai_devs4_part2/s3/s3e5/solver.py) | BFS/Dijkstra search template with multi-resource constraints and state pruning. |

---

## 9. 📊 Session Snapshot

| Field | Value |
|-------|-------|
| Lesson / Task | `S03E05` |
| Date completed | `2026-06-11` |
| LangSmith project | `N/A (Local Verification)` |
| Models used | `Gemini 3.5 Flash` |
| Approx. number of agent turns | `4` |
| Hardest part (one line) | Handling HTTP 404 errors by inspecting response bodies |
| Overall complexity estimate | `Medium` |
