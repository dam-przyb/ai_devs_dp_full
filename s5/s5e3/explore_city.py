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
        "grep_safe_1": "grep -C 2 ': 219' /data/locations.json",
        "grep_safe_2": "grep -C 2 '219' /data/locations.json",
        "python_safe": "python3 -c \"import json; d=json.load(open('/data/locations.json')); print([x for x in d if list(x.values())[0] == 219])\" || python -c \"import json; d=json.load(open('/data/locations.json')); print([x for x in d if list(x.values())[0] == 219])\""
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
    
    output_path = os.path.join(run_log_dir, "explore_city.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)
        
    print(f"\nSaved city exploration results to {output_path}")

if __name__ == "__main__":
    main()
