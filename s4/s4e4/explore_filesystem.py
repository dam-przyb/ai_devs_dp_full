import os
import json
from pathlib import Path
import requests
from dotenv import load_dotenv

# Load environment variables from the project root .env
dotenv_path = Path(__file__).resolve().parents[2] / '.env'
load_dotenv(dotenv_path=dotenv_path)

AIDEVS_KEY = os.getenv("AIDEVSKEY")
VERIFY_URL = "https://hub.ag3nts.org/verify"

if not AIDEVS_KEY:
    raise ValueError("Missing AIDEVSKEY in environment variables.")

def main():
    payload = {
        "apikey": AIDEVS_KEY,
        "task": "filesystem",
        "answer": {
            "action": "help"
        }
    }
    
    print("Sending payload to /verify...")
    response = requests.post(VERIFY_URL, json=payload, timeout=30)
    res_json = response.json()
    
    print("\nResponse from server:")
    print(json.dumps(res_json, indent=2, ensure_ascii=False))
    
    # Save the output to run_log/explore_help.json
    log_dir = Path(__file__).resolve().parent / "run_log"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "explore_help.json"
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(res_json, f, indent=2, ensure_ascii=False)
    print(f"\nSaved response to {log_file}")

if __name__ == "__main__":
    main()
