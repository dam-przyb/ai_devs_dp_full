import json
from pathlib import Path

cache = json.loads(Path("s3/s3e1/run_logs/note_classification_cache.json").read_text())

strong_keywords = ["unstable", "irregulari", "root-cause", "deeper diagnostic", "cannot be treated as normal"]
count = 0
for note, verdict in cache.items():
    if verdict == "OK" and any(kw in note.lower() for kw in strong_keywords):
        print(f"[OK] {note}\n")
        count += 1
print(f"Total OK with strong keywords: {count}")

# Also show all PROBLEM notes
print("\n--- ALL PROBLEM notes ---")
for note, verdict in cache.items():
    if verdict == "PROBLEM":
        print(f"[PROBLEM] {note}\n")
