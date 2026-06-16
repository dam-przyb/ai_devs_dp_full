"""Mine all run_log JSON files and extract confirmed hint→actual_stone_row pairs."""
import json
import os
import glob
from collections import defaultdict

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_log")

records = []

for fpath in sorted(glob.glob(os.path.join(LOG_DIR, "2*.json"))):
    with open(fpath, encoding="utf-8") as f:
        data = json.load(f)

    steps = data.get("steps", [])
    base_row = data.get("start_response", {}).get("base", {}).get("row")

    for i, step in enumerate(steps):
        hint = step.get("hint_raw")
        predicted_rows = step.get("stone_rows")

        # The prediction was for column current_col+1.
        # After the move the API tells us stoneRow of the column we entered (current_col+1),
        # so move_response.currentColumn.stoneRow IS the actual stone row for this hint.
        actual_stone_row = None
        move_resp = step.get("move_response")
        if move_resp and "currentColumn" in move_resp:
            actual_stone_row = move_resp["currentColumn"].get("stoneRow")

        if hint and actual_stone_row is not None:
            rec = {
                "file": os.path.basename(fpath),
                "step": step.get("step_number"),
                "pilot_row": step.get("current_row"),
                "base_row": base_row,
                "hint": hint,
                "predicted": predicted_rows,
                "actual_stone_row": actual_stone_row,
                "correct": actual_stone_row in (predicted_rows or []),
            }
            records.append(rec)

print(f"Total confirmed hint->stone_row pairs: {len(records)}\n")

# Print mismatches
errors = [r for r in records if not r["correct"]]
print(f"MISMATCHES ({len(errors)}):")
for r in errors:
    print(f"  [{r['file']} step {r['step']}] pilot={r['pilot_row']} base={r['base_row']}")
    print(f"    hint: \"{r['hint']}\"")
    print(f"    predicted: {r['predicted']}  actual: {r['actual_stone_row']}")
    print()

# Print all records grouped by hint text
by_hint: dict = defaultdict(list)
for r in records:
    by_hint[r["hint"]].append(r)

print("\n=== ALL HINTS AND THEIR ACTUAL STONE ROWS ===")
for hint, recs in sorted(by_hint.items()):
    print(f"\nHINT: \"{hint}\"")
    for r in recs:
        status = "OK" if r["correct"] else "XX"
        print(f"  {status} pilot={r['pilot_row']} base={r['base_row']} -> actual={r['actual_stone_row']} (predicted={r['predicted']})")
