# Lesson Summary — S05E03 (shellaccess)

Reflective technical summary on the completion of the `shellaccess` task.

---

## 1. 🎯 What Was Accomplished

- **Goal**: Perform remote shell-based analysis on logs from a remote server to identify when and where Rafał's body was found, and return a JSON payload with the date one day prior, city, and GPS coordinates to claim the flag.
- **Deliverables**:
  - [explore_shellaccess.py](file:///c:/zz_projects/ai_devs4_part2/s5/s5e3/explore_shellaccess.py): Probed the remote API structure.
  - [explore_rafal.py](file:///c:/zz_projects/ai_devs4_part2/s5/s5e3/explore_rafal.py): Searched the logs using synonyms due to API-level filtering.
  - [explore_city.py](file:///c:/zz_projects/ai_devs4_part2/s5/s5e3/explore_city.py): Mapped the location ID to city name using a safe `grep` bypass.
  - [solve_shellaccess.py](file:///c:/zz_projects/ai_devs4_part2/s5/s5e3/solve_shellaccess.py): Sent the final echo command and retrieved the flag.
  - [explore.json](file:///c:/zz_projects/ai_devs4_part2/s5/s5e3/run_log/explore.json), [explore_data.json](file:///c:/zz_projects/ai_devs4_part2/s5/s5e3/run_log/explore_data.json), [explore_rafal.json](file:///c:/zz_projects/ai_devs4_part2/s5/s5e3/run_log/explore_rafal.json), [explore_city.json](file:///c:/zz_projects/ai_devs4_part2/s5/s5e3/run_log/explore_city.json), [solve.json](file:///c:/zz_projects/ai_devs4_part2/s5/s5e3/run_log/solve.json): Run log artifacts showing execution outputs.

---

## 2. 🏗️ How the Agent / Solution Was Constructed

### 2a. Architecture Overview
A set of modular exploration and solving scripts executed in sequence via PowerShell, using the `verify` API endpoint acting as a gateway to execution on the remote system:
```
[User runs script] --> [python script] --> [POST /verify] --> [Remote Server executes cmd] --> [Response with stdout]
```

### 2b. Key Components

#### `explore_rafal.py`
**Purpose:** Searches remote CSV logs for synonyms related to Rafał's body discovery to bypass WAF filters blocking the name "rafa".
```python
    commands = {
        "grep_cialo": "grep -i 'ciało' /data/time_logs.csv || echo 'no ciało'",
        "grep_znaleziono": "grep -i 'znaleziono' /data/time_logs.csv || echo 'no znaleziono'",
        "grep_zwloki": "grep -i 'zwłoki' /data/time_logs.csv || echo 'no zwłoki'",
        "grep_szczatki": "grep -i 'szczątki' /data/time_logs.csv || echo 'no szczątki'"
    }
```

#### `explore_city.py`
**Purpose:** Matches location ID to city names using bypass greps when standard queries containing `"location_id"` or `"location"` are blocked.
```python
    commands = {
        "grep_safe_2": "grep -C 2 '219' /data/locations.json",
    }
```

### 2c. Data & Control Flow
1. Probed the file system structure (`locations.json`, `gps.json`, `time_logs.csv`).
2. Discovered that keywords like "rafa", "rafał" and syntax like `jq ... | select(...)` trigger WAF blocks (400 Bad Request).
3. Used Polish synonyms (`ciało`, `znaleziono`) to locate the relevant event in `time_logs.csv` and get location ID `219` and place ID `954634`.
4. Extracted GPS coordinates for ID `954634` from `gps.json` using context-grep.
5. Extracted the city name `Grudziądz` for ID `219` using context-grep.
6. Subtracted one day from the discovery date and executed the target `echo` command to receive the flag.

---

## 3. 🧱 Main Struggles & How They Were Resolved

- **Problem:** Commands containing `rafa`, `rafał`, `select`, `location_id`, and `|` (pipe) triggered `400 Client Error: Bad Request`.
- **Root Cause:** A Web Application Firewall (WAF) or validation filter on the verification server restricted input patterns.
- **Resolution:**
  - Substituted the word "rafał" with synonyms "ciało" (body) and "znaleziono" (found).
  - Swapped `jq` filtering for simple `grep` with context lines (`grep -C 2 '219'` and `grep -B 4 '954634'`) to bypass command parsing rules.
- **Takeaway:** When facing input sanitization or WAF limitations on remote API endpoints, avoid complex command chaining or targeted keywords. Use broad greps or alternative synonyms instead.

---

## 4. 🤝 User ↔ Coding Agent Interaction Assessment

### 4a. What the User Did Well
- Provided prompt runs of local scripts and immediately shared the output logs.
- Instructed to use specific helper scripts (`explore_*.py`) that kept the API-based environment isolated from the workspace, avoiding token clutter.
- Highlighted the hint from the task description early.

### 4b. What Could Be Improved (User Side)
- The interaction went exceptionally well; requirements were clear and the execution loop was fast.

### 4c. What the Coding Agent Did Well
- Successfully deduced that a WAF filter was blocking queries, pivoted to synonym lookups, and used context greps instead of throwing errors.
- Correctly adjusted the target date (one day prior to finding the body) and used the exact Polish spelling for the city.

### 4d. What the Coding Agent Could Improve
- Could have anticipated that complex jq patterns and pipes might trigger validation errors, testing simpler commands first.

### 4e. Recommended Prompting Patterns for Next Time
```markdown
Run exploration commands sequentially using simple scripts to avoid token clutter in the chat window.
```

---

## 5. 💡 Agentic Patterns Observed

- **ReAct (Reasoning and Acting)**: Interpreting 400 Bad Request errors, concluding that filter rules were in place, planning workarounds, and implementing different queries.
- **Bypass/Robustness Loop**: Using shell command alternatives (grep instead of jq) to circumvent server restrictions.

---

## 6. 🔁 What Would You Do Differently

- Avoid writing `jq` commands altogether, preferring simple `grep` lines immediately to save round-trips.
- Keep a library of basic bash extraction patterns handy for REST/Shell APIs that have minimal tools installed.

---

## 7. 🧠 Key Learnings

> **WAF Bypass:** In restricted remote shell environments, keep command structures flat (avoid pipes `|` and complex redirection) to reduce the risk of triggering security filters.
> **Synonym Search:** When searching for text that might be restricted or obfuscated, use nearby keywords (e.g., date formats, associated actions like "found", "occurred") to locate the records.
> **Polish diacritics:** Ensure inputs sent to Polish systems correctly preserve character sets like `ą`, `ł`, etc.

---

## 8. 📦 Reusable Artifacts

| Artifact | Location | Why It's Reusable |
|----------|----------|-------------------|
| `verify shell command sender` | [solve_shellaccess.py](file:///c:/zz_projects/ai_devs4_part2/s5/s5e3/solve_shellaccess.py) | Clean template for sending shell commands via POST payloads to AI_Devs tasks. |

---

## 9. 📊 Session Snapshot

| Field | Value |
|-------|-------|
| Lesson / Task | `S05E03` |
| Date completed | `2026-06-15` |
| LangSmith project | `shellaccess` |
| Models used | `Gemini 3.5 Flash` |
| Approx. number of agent turns | `5` |
| Hardest part (one line) | Bypassing WAF rules blocking queries containing 'rafał' and 'location_id' |
| Overall complexity estimate | `Medium` |
