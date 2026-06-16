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
        "grep_location": "grep -C 2 '\"location_id\": 219' /data/locations.json",
        "grep_gps": "grep -B 4 '\"entry_id\": 954634' /data/gps.json"
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
    
    output_path = os.path.join(run_log_dir, "explore_grep.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)
        
    print(f"\nSaved grep exploration results to {output_path}")

if __name__ == "__main__":
    main()
