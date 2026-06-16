import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("AIDEVSKEY")
if not api_key:
    print("API key for Centrala not found in .env")
    exit(1)

# The user will run ngrok and we need to provide the public URL here
NGROK_URL = "https://agnostic-tables-vagueness.ngrok-free.dev" # Change this before running!

tool_url = f"{NGROK_URL}/api/find_item_cities"
description = (
    "Użyj tego narzędzia, aby znaleźć listę miast, w których dostępny jest dany przedmiot. "
    "W polu 'params' przekaż zapytanie o przedmiot w języku naturalnym (np. 'potrzebuję kabla długości 10 metrów'). "
    "Narzędzie zwróci listę miast (rozdzieloną przecinkami), w których ten przedmiot można kupić."
)

payload = {
    "apikey": api_key,
    "task": "negotiations",
    "answer": {
        "tools": [
            {
                "URL": tool_url,
                "description": description
            }
        ]
    }
}

response = requests.post("https://hub.ag3nts.org/verify", json=payload)
print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")
