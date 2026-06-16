import os
import json
from pathlib import Path
import requests
from dotenv import load_dotenv

# Robustly load .env from the project root
dotenv_path = Path(__file__).resolve().parents[2] / '.env'
load_dotenv(dotenv_path=dotenv_path)

AIDEVS_KEY = os.getenv("AIDEVSKEY")
VERIFY_URL = "https://hub.ag3nts.org/verify"

if not AIDEVS_KEY:
    raise ValueError("Missing AIDEVSKEY in environment variables.")

def send_action(action, **kwargs):
    payload = {
        "apikey": AIDEVS_KEY,
        "task": "domatowo",
        "answer": {
            "action": action,
            **kwargs
        }
    }
    response = requests.post(VERIFY_URL, json=payload, timeout=30)
    return response.json()

def main():
    print("--- Fetching Action 'help' ---")
    help_res = send_action("help")
    print(json.dumps(help_res, indent=2, ensure_ascii=False))

    print("\n--- Fetching Action 'getMap' ---")
    map_res = send_action("getMap")
    print(json.dumps(map_res, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
