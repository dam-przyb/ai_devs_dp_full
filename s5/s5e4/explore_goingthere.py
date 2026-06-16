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
    
    # Try different ways to query help/schema or start the task
    payloads = {
        "help_string": {
            "apikey": api_key,
            "task": "goingthere",
            "answer": "help"
        },
        "help_dict": {
            "apikey": api_key,
            "task": "goingthere",
            "answer": {"command": "help"}
        },
        "start_game": {
            "apikey": api_key,
            "task": "goingthere",
            "answer": {
                "command": "start"
            }
        }
    }

    results = {}
    for name, payload in payloads.items():
        print(f"Sending request for {name} to {url}...")
        try:
            response = requests.post(url, json=payload)
            try:
                data = response.json()
            except ValueError:
                data = {"text": response.text}
            results[name] = {
                "status_code": response.status_code,
                "data": data
            }
            print(f"Response for {name}: {response.status_code}")
        except Exception as e:
            print(f"Error for {name}: {e}")
            results[name] = {"error": str(e)}

    # Ensure run_log folder exists
    run_log_dir = os.path.join(script_dir, "run_log")
    os.makedirs(run_log_dir, exist_ok=True)
    
    output_path = os.path.join(run_log_dir, "explore.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)
        
    print(f"\nSaved exploration results to {output_path}")

if __name__ == "__main__":
    main()
