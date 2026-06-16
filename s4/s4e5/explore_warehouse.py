import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    api_key = os.getenv("AIDEVSKEY")
    if not api_key:
        print("Error: AIDEVSKEY not found in environment variables.")
        return

    url = "https://hub.ag3nts.org/verify"
    payload = {
        "apikey": api_key,
        "task": "foodwarehouse",
        "answer": {
            "tool": "help"
        }
    }

    print(f"Sending request to {url}...")
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        
        # Ensure run_log folder exists
        os.makedirs("run_log", exist_ok=True)
        
        # Write response to run_log/explore.json
        output_path = os.path.join("run_log", "explore.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            
        print(f"Successfully saved help info to {output_path}")
        print("Response received:")
        print(json.dumps(data, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":
    main()
