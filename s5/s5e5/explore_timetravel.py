import os
import json
import httpx
from dotenv import load_dotenv

# Load env from parent directory
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
load_dotenv(dotenv_path)

API_KEY = os.getenv("AIDEVSKEY")
URL = "https://hub.ag3nts.org/verify"

def main():
    if not API_KEY:
        print("Error: AIDEVSKEY is missing from environment variables.")
        return

    payload = {
        "apikey": API_KEY,
        "task": "timetravel",
        "answer": {
            "action": "help"
        }
    }

    print(f"Sending 'help' request to {URL}...")
    try:
        response = httpx.post(URL, json=payload, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        print("Success! Response received.")
    except Exception as e:
        print(f"Error querying verify endpoint: {e}")
        if 'response' in locals() and response is not None:
            print(f"Response status: {response.status_code}")
            print(f"Response text: {response.text}")
        return

    # Ensure run_log directory exists
    log_dir = os.path.join(os.path.dirname(__file__), "run_log")
    os.makedirs(log_dir, exist_ok=True)

    log_path = os.path.join(log_dir, "explore.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Result saved to: {log_path}")

if __name__ == "__main__":
    main()
