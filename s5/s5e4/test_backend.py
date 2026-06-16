import os
import json
import requests
from dotenv import load_dotenv

script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, "..", "..", ".env")
load_dotenv(dotenv_path=env_path)

def main():
    api_key = os.getenv("AIDEVSKEY")
    url = "https://hub.ag3nts.org/goingthere_backend"
    payload = {
        "key": api_key,
        "after_event_id": "0"
    }
    print(f"Querying {url} with key={api_key[:8]}...")
    try:
        response = requests.post(url, data=payload)
        print("Status Code:", response.status_code)
        try:
            data = response.json()
            # Save to file
            output_path = os.path.join(script_dir, "run_log", "backend_events.json")
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print("Saved events to", output_path)
            
            # Print latest event summary if available
            events = data.get("events", [])
            if events:
                print(f"Total events: {len(events)}")
                latest = events[-1]
                print("Latest event type:", latest.get("type"))
                if "state" in latest:
                    state = latest["state"]
                    print("Crashed:", state.get("crashed"))
                    print("Crash Message:", state.get("crashMessage"))
                    print("Player pos:", state.get("player"))
            else:
                print("No events returned. Current state:", {k: v for k, v in data.items() if k != "events"})
        except Exception as e:
            print("Response text:", response.text[:500])
            print("Error parsing json:", e)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    main()
