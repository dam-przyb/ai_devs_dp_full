import os
import json
import requests
from dotenv import load_dotenv

# Load env from root directory
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, "..", "..", ".env")
load_dotenv(dotenv_path=env_path)

def submit(city_name, city_area, warehouses_count, phone_number):
    api_key = os.getenv("AIDEVSKEY")
    if not api_key:
        print("Error: AIDEVSKEY not found in environment variables.")
        return

    url = "https://hub.ag3nts.org/verify"
    
    payload = {
        "apikey": api_key,
        "task": "radiomonitoring",
        "answer": {
            "action": "transmit",
            "cityName": city_name,
            "cityArea": str(city_area),
            "warehousesCount": int(warehouses_count),
            "phoneNumber": str(phone_number)
        }
    }
    
    print(f"\nSubmitting answer:")
    print(json.dumps(payload, indent=2))
    
    try:
        response = requests.post(url, json=payload)
        print(f"Status Code: {response.status_code}")
        print("Response:")
        print(response.text)
        return response.json()
    except Exception as e:
        print(f"Error submitting: {e}")
        return None

def main():
    # Let's run a test submission with:
    # cityName: Skarszewy
    # cityArea: 10.73
    # warehousesCount: 12
    # phoneNumber: 644-122-092
    submit(
        city_name="Skarszewy",
        city_area="10.73",
        warehouses_count=12,
        phone_number="644-122-092"
    )

if __name__ == "__main__":
    main()
