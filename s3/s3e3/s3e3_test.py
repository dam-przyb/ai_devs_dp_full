import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("AIDEVSKEY")

urls_to_test = [
    "https://centrala.ag3nts.org/api/verify",
    "https://centrala.ag3nts.org/verify",
    "https://hub.ag3nts.org/verify",
    "https://ag3nts.org/verify",
    "https://centrala.ag3nts.org/report"
]

payload = {
    "apikey": API_KEY,
    "task": "reactor",
    "answer": {
        "command": "start"
    }
}

for url in urls_to_test:
    try:
        response = requests.post(url, json=payload, timeout=5)
        print(f"URL: {url}")
        print(f"Status: {response.status_code}")
        try:
            print(f"JSON: {response.json()}")
        except:
            print(f"Text: {response.text}")
        print("-" * 40)
    except Exception as e:
        print(f"URL: {url} failed with {e}")

