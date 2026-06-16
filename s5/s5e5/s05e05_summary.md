# AI_Devs4 — S05E05 Task Summary

## 1. 🎯 What Was Accomplished
The goal of this task was to configure and operate the Chronos-P1 time machine via its API and Web UI to perform a multi-hop travel sequence: jump to 2238 to get batteries, return to the present (2026), and open a time tunnel to 12 November 2024 to find Rafał.

### Deliverables:
- [explore_timetravel.py](file:///c:/zz_projects/ai_devs4_part2/s5/s5e5/explore_timetravel.py): Queries the `/verify` endpoint for the help schema.
- [run_log/explore.json](file:///c:/zz_projects/ai_devs4_part2/s5/s5e5/run_log/explore.json): Saved JSON schema output of the help action.
- [timetravel_assistant.py](file:///c:/zz_projects/ai_devs4_part2/s5/s5e5/timetravel_assistant.py): Interactive CLI coordinator instructing the user on GUI settings and managing API coordinate configuration, stabilization detection, and `internalMode` monitoring.

---

## 2. 🏗️ How the Agent / Solution Was Constructed

### 2a. Architecture Overview
We implemented a human-in-the-loop CLI assistant. The script runs computations (such as the sync ratio and parsing stabilization offsets), handles API actions (sending target dates), and monitors the live device status. It prompts the user via stdin to make adjustments in the Web GUI (PT-A/PT-B switches, PWR level slider, active/standby toggles) and reports when it is safe to click the activation sphere.

```
       +----------------------------+
       |   timetravel_assistant.py   |
       +-----+----------------+------+
             |                |
         API Calls      User Interaction
             v                v
       +-----+------+   +-----+------+
       |   /verify  |   |   Web UI   |
       +------------+   +------------+
```

### 2b. Key Components

#### `calculate_sync_ratio`
**Purpose:** Computes the temporal sync ratio based on the target date using the documentation formula: `(day * 8 + month * 12 + year * 7) % 101` as a float between `0.00` and `1.00`.
```python
def calculate_sync_ratio(day: int, month: int, year: int) -> float:
    val = (day * 8 + month * 12 + year * 7) % 101
    return round(val / 100, 2)
```

#### `monitor_internal_mode`
**Purpose:** Polls the `/verify` endpoint to check when the dynamic `internalMode` matches the target year's range, and when the flux density reaches 100%, notifying the operator to trigger the jump.
```python
def monitor_internal_mode(target_mode: int, target_year: int):
    # Loop continuously fetching config and verifying state keys...
    # Alerts user with: *** READY FOR TRAVEL! ***
```

#### `setup_date`
**Purpose:** Sequences the coordinate setup, guides the user on required GUI switches/slider settings, handles the API payload delivery, reads the stabilization hints, and initiates the active monitoring cycle.

### 2c. Data & Control Flow
1. Target date inputs are configured in `setup_date`.
2. Sync ratio is computed and printed to the operator.
3. The operator is prompted to set the device to `standby` in the GUI.
4. Once in standby, the API configures `day`, `month`, `year`, and `syncRatio`.
5. The API response returns a textual Polish message containing the `stabilization` hint.
6. The operator types in the decoded stabilization value (e.g. `189`, `58`, `995`), which the script sends to the API.
7. The operator is asked to toggle the device to `active` in the Web UI.
8. The script starts a live loop monitoring `internalMode` and `fluxDensity`.
9. The operator clicks the pulsing sphere when the script signals ready, executing the jump.

---

## 3. 🧱 Main Struggles & How They Were Resolved

- **Problem:** API calls returned `400 Bad Request` during coordinate configuration.
  - **Root Cause:** The device was toggled to `active` mode in the Web UI. The documentation specifies API config changes are only accepted in `standby` mode.
  - **Resolution:** Instructed the user to toggle the mode to standby in the UI before hitting Enter in the assistant CLI, which resolved the error.
- **Problem:** Dynamic monitoring returned `None` for all machine parameters.
  - **Root Cause:** The outer JSON dictionary returned by `getConfig` nested the parameters under a `"config"` key. The script was reading keys directly from the outer dict.
  - **Resolution:** Modified key lookups to correctly access the inner `config = raw_config.get("config", {})` dictionary.
- **Problem:** The stabilization hints contained Polish number-words (e.g., `dziewięćset`, `siedemset jedenaście`) instead of digits.
  - **Root Cause:** A simple digit-matching regex failed to capture the value.
  - **Resolution:** Implemented an input fallback. The script displays the raw Polish message to the user, allowing them to calculate the offset and manually input the digit value (e.g. `900 - 711 = 189`).

---

## 4. 🤝 User ↔ Coding Agent Interaction Assessment

### 4a. What the User Did Well
- The user provided clean terminal output captures and confirmed screen states (e.g. "i see im in 2238").
- Executed script tasks accurately without requesting code modifications or local execution, which conserved context resources.

### 4b. What Could Be Improved (User Side)
- No significant improvements needed. The coordination was smooth.

### 4c. What the Coding Agent Did Well
- Swiftly adjusted the coordinator script's nesting lookups when the API dictionary structure mismatch was identified.
- Designed a step-by-step assistant that is resilient to regex failures by enabling user-input fallbacks.

### 4d. What the Coding Agent Could Improve
- Verify the exact nested dictionary structure of API outputs before writing parsing loops.

### 4e. Recommended Prompting Patterns for Next Time
```
# For multi-step coordination tasks involving web GUI actions:
"Please write a CLI script that acts as an interactive assistant. It should instruct me on what actions to take on the web GUI at each step, wait for my confirmation, and poll the API config in the background."
```

---

## 5. 💡 Agentic Patterns Observed

- **Human-in-the-Loop (HITL):** Crucial to the task's success. The agent automated parameter calculation, API requests, and live polling, while relying on the user for physical browser interactions (toggling switches, sliders, and buttons). This division of labor worked exceptionally well.

---

## 6. 🔁 What Would You Do Differently

- We would prototype a quick JSON dumper script first to view a complete response of `getConfig` and target coordinate requests to map the nested payload structures early.
- We would add a simple dictionary mapper for common Polish number words (e.g., *sześćset*, *dwa*, *dziewięćset*) to further automate the stabilization configuration.

---

## 7. 🧠 Key Learnings

> **[State Constraints]:** External APIs may reject updates if the device state (e.g. active vs standby) is incorrect. Identifying these state requirements early prevents redundant troubleshooting.
> **[Nested API Fields]:** Do not assume API endpoints return flat dictionaries. Inspect raw payloads to map keys like `"config"` or `"message"` accurately.
> **[Interactive Backups]:** When building automation scripts, always implement user fallbacks (e.g. asking for manual input when auto-parsing fails) to keep the pipeline moving.

---

## 8. 📦 Reusable Artifacts

| Artifact | Location | Why It's Reusable |
|----------|----------|-------------------|
| `timetravel_assistant.py` | `s5/s5e5/timetravel_assistant.py` | A template for coordination CLI tools that manage API calls alongside manual operator steps. |

---

## 9. 📊 Session Snapshot

| Field | Value |
|-------|-------|
| Lesson / Task | `S05E05 / timetravel` |
| Date completed | `2026-06-16` |
| Models used | `Gemini 3.5 Flash (High)` |
| Approx. number of agent turns | `6` |
| Hardest part (one line) | Coordinating standby/active states with API requests and monitoring `internalMode` updates. |
| Overall complexity estimate | `Medium` |
