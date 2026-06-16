import os
import json
import requests
from dotenv import load_dotenv

# Load env from root directory
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, "..", "..", ".env")
load_dotenv(dotenv_path=env_path)

def main():
    api_key = os.getenv("AIDEVSKEY")
    if not api_key:
        print("Error: AIDEVSKEY not found in environment variables.")
        return

    url = "https://hub.ag3nts.org/verify"
    
    # Target date: one day before 2024-11-13 (Rafał's body discovery date) -> 2024-11-12
    # Coordinates of entry 954634: latitude 53.432303, longitude 18.968774
    # City of location 219: Grudziądz
    
    payload_json = {
        "date": "2024-11-12",
        "city": "Grudziądz",
        "longitude": 18.968774,
        "latitude": 53.432303
    }
    
    json_str = json.dumps(payload_json, ensure_ascii=False)
    # Escape single quotes if any exist (none here, but good practice)
    json_str_escaped = json_str.replace("'", "'\\''")
    cmd = f"echo '{json_str_escaped}'"
    
    payload = {
        "apikey": api_key,
        "task": "shellaccess",
        "answer": {
            "cmd": cmd
        }
    }
    
    print(f"Sending shell command: {cmd}")
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        print(f"Server response:\n{json.dumps(data, indent=2, ensure_ascii=False)}")
        
        # Ensure run_log folder exists
        run_log_dir = os.path.join(script_dir, "run_log")
        os.makedirs(run_log_dir, exist_ok=True)
        
        output_path = os.path.join(run_log_dir, "solve.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            
        print(f"\nSaved solver results to {output_path}")
        
    except Exception as e:
        print(f"Error executing command: {e}")

if __name__ == "__main__":
    main()
