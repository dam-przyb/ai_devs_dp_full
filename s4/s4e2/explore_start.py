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
    # 1. Start the service window
    print("--- Starting service window ---")
    start_res = send_action("start")
    print("Start response:", start_res)

    # 2. Queue the three reports
    print("\n--- Queuing reports ---")
    weather_res = send_action("get", param="weather")
    print("Queue weather response:", weather_res)
    
    turbine_res = send_action("get", param="turbinecheck")
    print("Queue turbinecheck response:", turbine_res)
    
    powerplant_res = send_action("get", param="powerplantcheck")
    print("Queue powerplantcheck response:", powerplant_res)

    # 3. Poll getResult to collect the responses
    print("\n--- Polling getResult ---")
    collected_results = {}
    
    # We expect 3 results: weather, turbinecheck, powerplantcheck
    # Let's poll up to 60 times with 0.5s delay (up to 30 seconds total)
    for attempt in range(1, 61):
        time.sleep(0.5)
        res = send_action("getResult")
        
        if isinstance(res, dict):
            source = res.get("sourceFunction")
            if source:
                collected_results[source] = res
                print(f"Poll #{attempt}: Collected report from {source}!")
            else:
                # Print status if it's not a collected report
                msg = res.get("message", "")
                if "No completed queued response" not in msg:
                    print(f"Poll #{attempt} response: {res}")
        
        if len(collected_results) >= 3:
            print("\nAll 3 reports collected!")
            break
    
    print("\n--- Summary of collected reports ---")
    for src, data in collected_results.items():
        print(f"\n================ SOURCE: {src} ================")
        import json
        print(json.dumps(data, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
