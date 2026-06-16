import os
import json
from pathlib import Path
import requests
from dotenv import load_dotenv

# Load .env
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
    print("--- 1. Resetting Board ---")
    reset_res = send_action("reset")
    print(json.dumps(reset_res, indent=2, ensure_ascii=False))

    print("\n--- 2. Creating Transporter with 3 passengers ---")
    create_res = send_action("create", type="transporter", passengers=3)
    print(json.dumps(create_res, indent=2, ensure_ascii=False))

    print("\n--- 3. Getting Objects ---")
    objects_res = send_action("getObjects")
    print(json.dumps(objects_res, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
