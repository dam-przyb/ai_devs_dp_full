import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

AIDEVS_KEY = os.getenv("AIDEVSKEY")
VERIFY_URL = "https://hub.ag3nts.org/verify"

if not AIDEVS_KEY:
    raise ValueError("Missing AIDEVSKEY in environment variables.")

def explore_help():
    payload = {
        "apikey": AIDEVS_KEY,
        "task": "windpower",
        "answer": {
            "action": "get",
            "param": "documentation"
        }
    }
    print("Sending get documentation action to Central API...")
    response = requests.post(VERIFY_URL, json=payload, timeout=30)
    print("Status Code:", response.status_code)
    try:
        data = response.json()
        print("Response data:")
        import json
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception as e:
        print("Error parsing JSON response:", e)
        print("Raw response:", response.text)

if __name__ == "__main__":
    explore_help()
