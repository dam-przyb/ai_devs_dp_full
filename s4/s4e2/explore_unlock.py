import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

AIDEVS_KEY = os.getenv("AIDEVSKEY")
VERIFY_URL = "https://hub.ag3nts.org/verify"

if not AIDEVS_KEY:
    raise ValueError("Missing AIDEVSKEY in environment variables.")

def send_action(action, **kwargs):
    payload = {
        "apikey": AIDEVS_KEY,
        "task": "windpower",
        "answer": {
            "action": action,
            **kwargs
        }
    }
    response = requests.post(VERIFY_URL, json=payload, timeout=30)
    return response.json()

def main():
    print("--- Starting service window ---")
    start_res = send_action("start")
    print("Start response:", start_res)

    print("\n--- Requesting unlock code ---")
    unlock_res = send_action(
        "unlockCodeGenerator",
        startDate="2026-06-16",
        startHour="18:00:00",
        windMs=25,
        pitchAngle=90
    )
    print("Request response:", unlock_res)

    print("\n--- Polling getResult ---")
    for attempt in range(1, 41):
        time.sleep(0.5)
        res = send_action("getResult")
        
        if isinstance(res, dict):
            source = res.get("sourceFunction")
            if source == "unlockCodeGenerator":
                print(f"\nPoll #{attempt}: Collected unlockCodeGenerator response!")
                import json
                print(json.dumps(res, indent=2, ensure_ascii=False))
                break
            else:
                msg = res.get("message", "")
                if "No completed queued response" not in msg:
                    print(f"Poll #{attempt} response: {res}")

if __name__ == "__main__":
    main()
