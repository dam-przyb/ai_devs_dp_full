# S3E1 — Sensor Anomaly Detection — Session Summary

## Task Overview

- **Task name:** `evaluation`
- **Endpoint:** `POST https://hub.ag3nts.org/verify`
- **API key env var:** `AIDEVSKEY`
- **Data:** 9,999 JSON files in `s3/s3e1/sensors/`, already downloaded and unzipped
- **Goal:** Submit IDs of all files containing anomalies in `answer.recheck` array

### Anomaly definitions (from task description)
1. Sensor measurement value outside valid range
2. Inactive sensor field has a non-zero value (field should be 0)
3. Operator note says OK, but data is bad
4. Operator note reports a problem, but data is actually fine

### Valid ranges for active sensors
| Field | Min | Max |
|---|---|---|
| temperature_K | 553 | 873 |
| pressure_bar | 60 | 160 |
| water_level_meters | 5.0 | 15.0 |
| voltage_supply_v | 229.0 | 231.0 |
| humidity_percent | 40.0 | 80.0 |

---

## What We Built

### `solve_sensors.py`
Main script with three steps:
1. **Programmatic checks** — parse `sensor_type` (e.g. `"humidity/pressure/water"`), determine active fields, flag out-of-range values and inactive fields with non-zero values
2. **LLM note classification** — collect unique `operator_notes` from clean-data files, filter with keyword pre-scan, batch into LLM (gpt-4o-mini via OpenRouter), classify as `OK` or `PROBLEM`, cache results to disk
3. **Submit** — POST to `/verify`

### `debug_anomalies.py` / `debug_cache.py`
Diagnostic scripts used during debugging.

### `run_logs/note_classification_cache.json`
Cached LLM classification of 617 unique notes (all keyword-matched). **Do not delete** — avoids re-running costly LLM calls.

---

## Key Data Facts

- **9,999** sensor files total
- **25** unique `sensor_type` combinations (e.g. `temperature`, `humidity/pressure/water`, etc.)
- **2,032** unique `operator_notes` across all files (many notes repeat ~5–13 times)
- **1,993** unique notes in clean-data files
- **617** notes passed keyword filter → sent to LLM
- All sensor type tokens: `humidity`, `pressure`, `temperature`, `voltage`, `water`
- No active sensors return 0 (that edge case does not exist in this dataset)

---

## Results So Far

| Anomaly source | Count | IDs (sample) |
|---|---|---|
| Programmatic (out-of-range) | ~22 | 0307, 0567, 0753, 1053, 1819, 2175... |
| Programmatic (inactive field non-zero) | ~24 | 0158, 0516, 1632, 1678, 2958, 3123... |
| LLM (problem note, clean data) | 4 | 5000, 7266, 8369, 9614 |
| **Total submitted** | **50** | — |

---

## Failures & Error Codes

| Submission | Response |
|---|---|
| 2 IDs (test) | `-960`: "too few, our technicians found way more" |
| 46 data-anomaly IDs only | `-940`: "incorrect" |
| 50 total IDs (data + LLM) | `-940`: "incorrect" |
| 10 clearly out-of-range IDs | `-940`: "incorrect" |

**Error -960** = too few anomalies submitted  
**Error -940** = list is incorrect (contains wrong IDs, or is missing IDs, or both)

The `-940` error on even 10 obviously anomalous IDs suggests either:
- Some of those 10 are false positives (data is actually OK by the server's rules), OR
- The server requires a minimum correct set before it accepts the answer

---

## Hypotheses for the Failure (not yet investigated)

1. **Range boundaries are inclusive on one side only** — e.g. maybe the task ranges use strict inequality (`<` not `<=`) for one bound. Recheck whether `553` and `873` are valid or invalid for `temperature_K`.

2. **`voltage_supply_v=229.0` is edge case** — the lower bound is exactly 229.0. File `0567` has `224.4` which is clearly below. But double-check files near the boundary.

3. **Some of the "inactive field non-zero" flags may be wrong** — the task says sensors can be "2–3 task" integrated sensors. Re-read the original Polish task carefully: maybe a combined sensor is NOT required to zero out the other fields, and only pure single-type sensors should be checked for leakage.

4. **LLM false positives** — the 4 PROBLEM-noted clean-data files may not actually be anomalies if the server uses a different rule for notes.

5. **Missing anomalies in the 1,376 uncached "clearly OK" notes** — these were filtered out by the keyword pre-scan and never sent to LLM. They all looked very obviously OK in manual sampling, but there may be subtle cases.

6. **Operator note anomaly definition is stricter** — maybe anomaly type 3 (OK note + bad data) is the only note anomaly, and anomaly type 4 (problem note + clean data) is NOT included. The data-bad files already have correct operator notes (operator noticed the problem), so those are NOT anomalies — only the 4 files where operator says problem but data is clean are flagged.

---

## Suggested Next Approach for New Agent

### Priority 1: Fix the programmatic check
- Carefully re-read task: "sensor that returns data it shouldn't" — does this apply to ALL sensors or only single-type sensors?
- Consider whether integrated multi-sensors (`pressure/temperature/water`) can legitimately have non-zero values for non-listed fields (answer: NO — the task says inactive fields should be 0)
- Try submitting ONLY the most extreme, unambiguous out-of-range IDs (e.g. `temperature_K=1101`, `pressure_bar=249`, `voltage_supply_v=304`) with NO edge cases to get a `-960` instead of `-940` — that would confirm those are correct

### Priority 2: Verify LLM note anomaly definition
- Re-examine whether "problem note + clean data" is truly an anomaly per the task, or if the task only means "OK note + bad data"
- The 4 LLM-flagged files (5000, 7266, 8369, 9614) — check manually if their notes are truly expressing a fault or just ambiguous language

### Priority 3: Binary search on clean IDs
- If -940 persists on obvious IDs, do binary subdivision: submit first 5, then second 5, etc., to isolate which specific IDs the server rejects — this pinpoints false positives

### Cost note
- LLM cache is already built at `run_logs/note_classification_cache.json`
- Note classification step is essentially free now (no new LLM calls needed unless expanding scope)
- Use `openai/gpt-4o-mini` via OpenRouter (`OPENROUTERKEY` env var) if re-running LLM steps

---

## File Map

```
s3/s3e1/
├── sensors/               ← 9999 JSON sensor files (already downloaded)
├── solve_sensors.py       ← Main solution script
├── debug_anomalies.py     ← Prints all flagged files with details
├── debug_cache.py         ← Inspects LLM note classification cache
├── summary.md             ← This file
└── run_logs/
    └── note_classification_cache.json  ← 617 classified notes, keep this!
```
