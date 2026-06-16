import os
import json
import time
import requests
from dotenv import load_dotenv

# Load env from root directory
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, "..", "..", ".env")
load_dotenv(dotenv_path=env_path)

def test_warehouses():
    api_key = os.getenv("AIDEVSKEY")
    if not api_key:
        print("Error: AIDEVSKEY not found in environment variables.")
        return

    url = "https://hub.ag3nts.org/verify"
    
    # We will try warehousesCount from 0 to 100
    for count in range(0, 101):
        payload = {
            "apikey": api_key,
            "task": "radiomonitoring",
            "answer": {
                "action": "transmit",
                "cityName": "Skarszewy",
                "cityArea": "10.73",
                "warehousesCount": count,
                "phoneNumber": "644-122-092"
            }
        }
        
        print(f"Testing warehousesCount = {count}...")
        try:
            response = requests.post(url, json=payload)
            data = response.json()
            
            # If we succeed, or get a different error (e.g. phoneNumber), we stop
            message = data.get("message", "")
            code = data.get("code", 0)
            
            print(f"Response: {response.status_code} | Code: {code} | Message: {message}")
            
            # If it's not complaining about warehousesCount, we found the right count!
            if "warehousesCount" not in message:
                print(f"\nFound correct warehousesCount: {count}!")
                print("Full Response:")
                print(json.dumps(data, indent=2, ensure_ascii=False))
                break
                
        except Exception as e:
            print(f"Error testing count {count}: {e}")
            
        time.sleep(0.5) # small sleep to be gentle

if __name__ == "__main__":
    test_warehouses()
