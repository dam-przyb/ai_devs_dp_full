# Handover & Debugging Summary: 'goingthere' Solver (S5E4)

This document serves as a handover starting point for the next agent to resume solving the **goingthere** navigation challenge.

---

## 1. Project Context
* **Task Goal:** Navigate a rocket safely on a $3 \times 12$ grid from Column 1 (always starts at row 2) to Column 12 (the target base row is randomized per game session, e.g., row 1 or row 3).
* **Game Rules:**
  * Move commands: `go` (straight ahead), `left` (row - 1), `right` (row + 1). All move commands advance the rocket by exactly 1 column.
  * You crash if you hit a rock (1 rock per column), fly out of bounds (rows are 1, 2, 3), or move into a column with an active radar trap without disarming it first.
  * **Radars:** Skaner GET/POST endpoint `/api/frequencyScanner` is polled before every move. If targeted, repair/decode the noisy JSON using LLM, compute `SHA1(detectionCode + "disarm")`, and POST it back.
  * **Hints:** endpoint `/api/getmessage` returns a text hint in English/nautical terms describing the position of the rock in the *next* column.

---

## 2. The Core Problem: Frame of Reference Mismatch

The game's hints dynamically switch between two coordinate frames of reference:
1. **Vehicle-Relative (centered at `current_row`):** Triggered when the hint explicitly mentions the vehicle or physical parts (e.g., `"cockpit"`, `"nose"`, `"hull"`, `"wing"`, `"wings"`, `"trajectory"`, `"bow"`).
2. **Base-Relative (centered at `base_row`):** Triggered when the hint uses general grid path descriptors (e.g., `"line of travel"`, `"flight line"`, `"route"`, `"path"`, `"lanes"`, `"in front"`, `"straight ahead"`, `"ahead"`, `"center"`, `"centered"`, `"heading"`).

### The Inconsistency / Conflict Found:
In our latest runs, we encountered a direct contradiction for the exact same hint text:
* **Hint:** `"The craft is not being crowded from either side. The problem is sitting straight ahead."`
* **Observation A (from `20260616_161545.json` step 8):**
  * `current_row: 2`, `base_row: 1`
  * **Actual Rock Row:** `[2]` (matching `current_row`, suggesting a **Vehicle-Relative** interpretation because of the word `"craft"`).
* **Observation B (from `20260616_162655.json` step 7):**
  * `current_row: 2`, `base_row: 3`
  * **Actual Rock Row:** `[3]` (matching `base_row` / destination, suggesting a **Base-Relative** interpretation because of the phrase `"straight ahead"`).

Because we few-shotted the LLM to map this hint to row `2` when `current_row=2`, it predicted `[2]` in Observation B, chose row `3` (starboard), and crashed into the rock at row `3`.

---

## 3. Current Implementation Details
* **Main Script:** [solve_goingthere.py](file:///c:/zz_projects/ai_devs4_part2/s5/s5e4/solve_goingthere.py)
* **Model Configured:** Currently set to `anthropic/claude-haiku-4.5` (via OpenRouter base URL).
* **Few-Shot Prompt:** We modified `parse_hint_for_rock` to use a 13-example ground truth few-shot dataset compiled from historical logs.
* **Logs Directory:** [run_log](file:///c:/zz_projects/ai_devs4_part2/s5/s5e4/run_log/) contains step-by-step logs for all runs (e.g. `20260616_162655.json`, `timestamp.json` and visualizer outputs).
* **Test Utility:** [test_backend.py](file:///c:/zz_projects/ai_devs4_part2/s5/s5e4/test_backend.py) queries the visualizer backend event log `/goingthere_backend` and saves it to `run_log/backend_events.json`.

---

## 4. Suggested Steps for the Next Agent

1. **Re-evaluate Hint Framing:**
   * Is `"straight ahead"` or `"heading"` always relative to the *vector* pointing from `current_row` to `base_row`?
   * If `current_row = 2` and `base_row = 3`, the rocket needs to go down. Is "straight ahead" in that context actually row 3?
   * Consider writing a diagnostic script to start a game, query hints, make moves to all rows, and map out the entire board map to build a 100% accurate parser schema.
2. **Review Ground Truth Mapping:**
   * Run the scratch parser script [parse_hints.py](file:///C:/Users/damia/.gemini/antigravity-ide/brain/17e72844-6b24-47f6-b734-753702822e40/scratch/parse_hints.py) to inspect the 34 instances of hint-to-rock-row mappings.
3. **Execution Commands:**
   * Run the solver: `python s5/s5e4/solve_goingthere.py`
   * Poll backend events after crashes: `python s5/s5e4/test_backend.py`
