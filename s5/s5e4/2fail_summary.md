# Post-Mortem & Failure Summary: `goingthere` Navigation Task

This document summarizes the extremely subtle bugs, game mechanics, and traps we encountered while trying to solve the `goingthere` grid navigation task.

## 1. The Diagonal Collision Bug (The Hidden Mechanic)
**Symptom**: The rocket would successfully dodge the rock in the *next* column based on the hint, but still crash immediately upon moving.
**Root Cause**: When the rocket moves diagonally (e.g., from row 2 to row 3), the game engine simulates the ship physically turning through that space. If the rock in your *current* column happens to be at row 3, turning towards row 3 causes your wing to clip it and crash.
**Fix**: When calculating `valid_candidates` for the next move, you must filter out the rock in the next column AND the rock in the `currentColumn["stoneRow"]`. 

## 2. The Radar Obfuscation Trap
**Symptom**: The agent would assume the path was clear and move without disarming the radar, resulting in a generic 400 `Rocket crashed` error.
**Root Cause**: The API simulates jamming. When you are being targeted by a radar, the API is supposed to return JSON. However, the jamming can heavily obfuscate the JSON (missing brackets, weird casing, misspelled keys). A naive check like `if "{" not in response.text` will falsely assume the path is safe if the brackets are obfuscated.
**Fix**: The ONLY guarantee of a safe path is if the API explicitly returns a string containing some variation of "clear" (e.g., `"it'S  CLear!"` or `"IT's ClEeeEEaR!"`). We used the strict regex `bool(re.search(r"cl[e]+ar", text, re.IGNORECASE))` to verify safety. Anything that fails this regex is passed to the LLM to extract the `frequency` and `detectionCode`.

## 3. Vehicle-Relative Hints vs. Base Row
**Symptom**: The agent would crash when trying to guess whether "straight ahead" meant the pilot's current row or the target base's row.
**Root Cause**: We incorrectly assumed that hints might be referencing the base row if the pilot and base were unaligned. Through data mining, we definitively proved that **all hints are strictly vehicle-relative**. "Straight ahead" *always* means the pilot's current row. 
**Fix**: We stripped the complex ambiguity rule from the LLM prompt and explicitly instructed it to map "front/ahead" to the pilot's current row, "port" to `row - 1` (from the pilot's perspective), and "starboard" to `row + 1`.

## 4. API Instability & Rate Limiting (429 / 502)
**Symptom**: The script would fail randomly during the 12-step navigation with `502 Bad Gateway` or `429 Too Many Requests`.
**Root Cause**: The AI_Devs API is intentionally noisy and strictly rate-limited. Using fast models like `claude-haiku-4.5` or `gpt-oss-120b:free` triggers 429 errors because the moves are calculated too quickly. Furthermore, the API will occasionally return fatal 400 errors simulating random atmospheric/game noise.
**Fix**: 
- Added an exponential backoff specifically for `429` status codes.
- Added a `run_until_success()` while-loop wrapper around the entire game session. If a random unrecoverable crash occurs, it automatically restarts the game until the 12th column is successfully reached.
