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
    print("Reset response:", json.dumps(reset_res, indent=2))

    print("\n--- 2. Creating Transporter with 3 passengers ---")
    create_res = send_action("create", type="transporter", passengers=3)
    print("Create response:", json.dumps(create_res, indent=2))
    
    transporter_id = create_res["object"]
    scout_id = create_res["crew"][0]["id"]
    print(f"Transporter ID: {transporter_id}")
    print(f"Scout ID: {scout_id}")

    print("\n--- 3. Moving Transporter to D6 ---")
    move_res = send_action("move", object=transporter_id, where="D6")
    print("Move response:", json.dumps(move_res, indent=2))

    print("\n--- 4. Dismounting 1 Scout ---")
    dismount_res = send_action("dismount", object=transporter_id, passengers=1)
    print("Dismount response:", json.dumps(dismount_res, indent=2))

    print("\n--- 5. Getting Objects ---")
    objects_res = send_action("getObjects")
    print("Objects:", json.dumps(objects_res, indent=2))

    # The dismounted scout should be on a free tile around D6. Let's find where the scout is from objects.
    scout_pos = None
    for obj in objects_res.get("objects", []):
        if obj["id"] == scout_id:
            scout_pos = obj["position"]
            break
    
    print(f"Scout position from getObjects: {scout_pos}")
    
    if scout_pos:
        # Let's inspect the tile the scout is on
        print(f"\n--- 6. Inspecting current tile {scout_pos} with Scout ---")
        inspect_res = send_action("inspect", object=scout_id)
        print("Inspect response:", json.dumps(inspect_res, indent=2))

        # Check logs
        print("\n--- 7. Getting Logs ---")
        logs_res = send_action("getLogs")
        print("Logs response:", json.dumps(logs_res, indent=2))

if __name__ == "__main__":
    main()
