import os
import json
import time
from datetime import datetime
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

# Create run_log directory if it doesn't exist
run_log_dir = Path(__file__).parent / 'run_log'
run_log_dir.mkdir(parents=True, exist_ok=True)

# Define the coordinates for block3 tiles (the highest blocks)
GROUP_1 = ["F2", "G2", "F1", "G1"]  # Top group
GROUP_2 = ["B10", "A10", "A11", "B11", "C11", "C10"]  # Bottom-left group
GROUP_3 = ["H10", "I10", "I11", "H11"]  # Bottom-right group

class RunLogger:
    def __init__(self):
        self.steps = []
        self.timestamp = datetime.now().isoformat()
    
    def log_step(self, action, params, response):
        self.steps.append({
            "action": action,
            "params": params,
            "response": response,
            "timestamp": datetime.now().isoformat()
        })
    
    def save(self):
        filename = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = run_log_dir / filename
        data = {
            "timestamp": self.timestamp,
            "steps": self.steps
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"\nSaved execution log to {filepath}")

logger = RunLogger()

def send_action(action, **kwargs):
    payload = {
        "apikey": AIDEVS_KEY,
        "task": "domatowo",
        "answer": {
            "action": action,
            **kwargs
        }
    }
    print(f"Sending action '{action}' with params: {kwargs}")
    response = requests.post(VERIFY_URL, json=payload, timeout=30)
    res_data = response.json()
    print(f"Response (code {res_data.get('code')}): {res_data.get('message')}")
    logger.log_step(action, kwargs, res_data)
    return res_data

def check_log_for_partisan(log_entry):
    msg = log_entry.get("msg", "").lower()
    # Let's search for keywords indicating finding a person or not being empty
    # Default empty is: "Tu pusto. Tylko pudła po amunicji i pajęczyny."
    if "pusto" in msg and "amunicji" in msg and "pajęczyny" in msg:
        return False
    # If the message is different, or contains keywords
    keywords = ["człowiek", "ranny", "partyzant", "pomocy", "pomoc", "żyje", "jest", "znalazłem", "znalazłam", "znaleziono", "sygnał"]
    for kw in keywords:
        if kw in msg:
            return True
    # If it is any other message that doesn't look like the default empty one
    if len(msg) > 0 and "pusto" not in msg:
        return True
    return False

def main():
    try:
        # 1. Reset board
        print("\n=== Resetting board state ===")
        send_action("reset")

        # 2. Spawn Transporter with 3 scouts
        print("\n=== Spawning Transporter + 3 Scouts ===")
        create_res = send_action("create", type="transporter", passengers=3)
        if create_res.get("code") != 10:
            print("Failed to create transporter unit!")
            return
        
        transporter_id = create_res["object"]
        scouts = create_res["crew"]
        print(f"Transporter ID: {transporter_id}")
        for idx, s in enumerate(scouts):
            print(f"Scout {idx+1} ID: {s['id']}")

        # We will keep track of all inspected fields and their messages
        inspected_fields = {}
        partisan_field = None

        # --- GROUP 1 (Top) ---
        print("\n=== Phase 1: Exploring Group 1 (Top Block3s) ===")
        # Move transporter to E2
        move_res = send_action("move", object=transporter_id, where="E2")
        # Dismount Scout 1
        dismount_res = send_action("dismount", object=transporter_id, passengers=1)
        scout1_id = scouts[0]["id"]
        
        if "spawned" in dismount_res and len(dismount_res["spawned"]) > 0:
            current_pos = dismount_res["spawned"][0]["where"]
            print(f"Scout 1 spawned at {current_pos}")
            
            for field in GROUP_1:
                # If we already found the partisan, stop
                if partisan_field:
                    break
                
                # Move Scout 1 to field
                print(f"\nMoving Scout 1 to {field}...")
                send_action("move", object=scout1_id, where=field)
                
                # Inspect
                inspect_res = send_action("inspect", object=scout1_id)
                
                # Get logs
                logs_res = send_action("getLogs")
                # Find the log for this field
                field_log = None
                for log in logs_res.get("logs", []):
                    if log["field"] == field:
                        field_log = log
                        break
                
                if field_log:
                    msg = field_log["msg"]
                    inspected_fields[field] = msg
                    print(f"Log for {field}: {msg}")
                    if check_log_for_partisan(field_log):
                        print(f"⭐ FOUND PARTISAN AT {field}! Msg: {msg}")
                        partisan_field = field
                else:
                    print(f"Warning: No log found for field {field}")

        # --- GROUP 2 (Bottom-Left) ---
        if not partisan_field:
            print("\n=== Phase 2: Exploring Group 2 (Bottom-Left Block3s) ===")
            # Move transporter to B9
            send_action("move", object=transporter_id, where="B9")
            # Dismount Scout 2
            dismount_res = send_action("dismount", object=transporter_id, passengers=1)
            scout2_id = scouts[1]["id"]
            
            if "spawned" in dismount_res and len(dismount_res["spawned"]) > 0:
                current_pos = dismount_res["spawned"][0]["where"]
                print(f"Scout 2 spawned at {current_pos}")
                
                for field in GROUP_2:
                    if partisan_field:
                        break
                    
                    print(f"\nMoving Scout 2 to {field}...")
                    send_action("move", object=scout2_id, where=field)
                    
                    send_action("inspect", object=scout2_id)
                    logs_res = send_action("getLogs")
                    
                    field_log = None
                    for log in logs_res.get("logs", []):
                        if log["field"] == field:
                            field_log = log
                            break
                    
                    if field_log:
                        msg = field_log["msg"]
                        inspected_fields[field] = msg
                        print(f"Log for {field}: {msg}")
                        if check_log_for_partisan(field_log):
                            print(f"⭐ FOUND PARTISAN AT {field}! Msg: {msg}")
                            partisan_field = field
                    else:
                        print(f"Warning: No log found for field {field}")

        # --- GROUP 3 (Bottom-Right) ---
        if not partisan_field:
            print("\n=== Phase 3: Exploring Group 3 (Bottom-Right Block3s) ===")
            # Move transporter to H9
            send_action("move", object=transporter_id, where="H9")
            # Dismount Scout 3
            dismount_res = send_action("dismount", object=transporter_id, passengers=1)
            scout3_id = scouts[2]["id"]
            
            if "spawned" in dismount_res and len(dismount_res["spawned"]) > 0:
                current_pos = dismount_res["spawned"][0]["where"]
                print(f"Scout 3 spawned at {current_pos}")
                
                for field in GROUP_3:
                    if partisan_field:
                        break
                    
                    print(f"\nMoving Scout 3 to {field}...")
                    send_action("move", object=scout3_id, where=field)
                    
                    send_action("inspect", object=scout3_id)
                    logs_res = send_action("getLogs")
                    
                    field_log = None
                    for log in logs_res.get("logs", []):
                        if log["field"] == field:
                            field_log = log
                            break
                    
                    if field_log:
                        msg = field_log["msg"]
                        inspected_fields[field] = msg
                        print(f"Log for {field}: {msg}")
                        if check_log_for_partisan(field_log):
                            print(f"⭐ FOUND PARTISAN AT {field}! Msg: {msg}")
                            partisan_field = field
                    else:
                        print(f"Warning: No log found for field {field}")

        # 3. Call Helicopter
        if partisan_field:
            print(f"\n=== Calling Helicopter to {partisan_field} ===")
            heli_res = send_action("callHelicopter", destination=partisan_field)
            print("\n=== Helicopter Call Response ===")
            print(json.dumps(heli_res, indent=2, ensure_ascii=False))
        else:
            print("\n❌ Could not find partisan in any of the block3 tiles!")
            print("Inspected fields log messages:")
            for f, m in inspected_fields.items():
                print(f" - {f}: {m}")
            
            # Let's inspect expenses just in case
            print("\n=== Expenses history ===")
            expenses_res = send_action("expenses")
            print(json.dumps(expenses_res, indent=2, ensure_ascii=False))

    finally:
        # Save run log
        logger.save()

if __name__ == "__main__":
    main()
