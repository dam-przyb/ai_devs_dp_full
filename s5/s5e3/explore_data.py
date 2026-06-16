import os
import json
import requests
from dotenv import load_dotenv

# Load env from root directory
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, "..", "..", ".env")
load_dotenv(dotenv_path=env_path)

def main():
    api_key = os.getenv("AIDEVSKEY")
    if not api_key:
        print("Error: AIDEVSKEY not found in environment variables.")
        return

    url = "https://hub.ag3nts.org/verify"
    
    commands = {
        "head_locations": "head -n 20 /data/locations.json",
        "head_time_logs": "head -n 20 /data/time_logs.csv",
        "head_gps": "head -n 20 /data/gps.json",
        "grep_rafal_csv": "grep -rnwi 'rafal' /data/time_logs.csv || grep -ri 'rafal' /data/time_logs.csv || echo 'No rafal in time_logs.csv'",
        "grep_rafal_locations": "grep -rnwi 'rafal' /data/locations.json || grep -ri 'rafal' /data/locations.json || echo 'No rafal in locations.json'",
        "grep_rafal_gps": "grep -rnwi 'rafal' /data/gps.json || grep -ri 'rafal' /data/gps.json || echo 'No rafal in gps.json'"
    }

    results = {}
    for name, cmd in commands.items():
        payload = {
            "apikey": api_key,
            "task": "shellaccess",
            "answer": {
                "cmd": cmd
            }
        }
        print(f"Sending shell command '{cmd}' to {url}...")
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            results[name] = data
            print(f"Success for {name}")
        except Exception as e:
            print(f"Error for {name}: {e}")
            results[name] = {"error": str(e)}

    # Ensure run_log folder exists
    run_log_dir = os.path.join(script_dir, "run_log")
    os.makedirs(run_log_dir, exist_ok=True)
    
    output_path = os.path.join(run_log_dir, "explore_data.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)
        
    print(f"\nSaved exploration results to {output_path}")

if __name__ == "__main__":
    main()
