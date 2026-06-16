import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("AIDEVSKEY")
if not api_key:
    print("API key for Centrala not found in .env")
    exit(1)

payload = {
    "apikey": api_key,
    "task": "negotiations",
    "answer": {
        "action": "check"
    }
}

response = requests.post("https://hub.ag3nts.org/verify", json=payload)
print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")
