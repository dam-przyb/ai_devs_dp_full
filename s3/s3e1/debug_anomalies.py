"""Debug script to inspect all flagged anomalies."""
import json
from pathlib import Path

SENSORS_DIR = Path(__file__).parent / "sensors"
CACHE_FILE = Path(__file__).parent / "run_logs" / "note_classification_cache.json"

SENSOR_FIELDS = {
    "temperature": ("temperature_K", 553.0, 873.0),
    "pressure": ("pressure_bar", 60.0, 160.0),
    "water": ("water_level_meters", 5.0, 15.0),
    "voltage": ("voltage_supply_v", 229.0, 231.0),
    "humidity": ("humidity_percent", 40.0, 80.0),
}

# Load all files
data_anomalies = {}
clean_files = {}
for path in sorted(SENSORS_DIR.glob("*.json")):
    data = json.loads(path.read_text(encoding="utf-8"))
    fid = path.stem
    active = set(data["sensor_type"].lower().split("/"))
    reasons = []
    for sname, (field, mn, mx) in SENSOR_FIELDS.items():
        v = data.get(field, 0)
        if sname in active:
            if not (mn <= v <= mx):
                reasons.append(f"{field}={v} out of range [{mn},{mx}]")
        else:
            if v != 0:
                reasons.append(f"{field}={v} SHOULD_BE_0 (inactive)")
    if reasons:
        data_anomalies[fid] = {"reasons": reasons, "data": data}
    else:
        clean_files[fid] = data

print(f"Data anomalies: {len(data_anomalies)}")
for fid, info in data_anomalies.items():
    d = info["data"]
    print(f"  {fid} [{d['sensor_type']}]: {info['reasons']}")
    print(f"       Note: {d['operator_notes'][:100]}")

# Load cache and find bad-note clean files
cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
bad_note_ids = []
for fid, data in clean_files.items():
    note = data["operator_notes"]
    if cache.get(note) == "PROBLEM":
        bad_note_ids.append(fid)
        print(f"\nBAD NOTE (data clean): {fid} [{data['sensor_type']}]")
        print(f"  Note: {data['operator_notes']}")
        print(f"  Data: temp={data['temperature_K']} press={data['pressure_bar']} "
              f"water={data['water_level_meters']} volt={data['voltage_supply_v']} "
              f"hum={data['humidity_percent']}")

print(f"\nBad note IDs: {sorted(bad_note_ids)}")
print(f"Total: {len(data_anomalies) + len(bad_note_ids)}")
