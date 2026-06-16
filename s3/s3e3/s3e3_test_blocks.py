import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("AIDEVSKEY")
URL = "https://hub.ag3nts.org/verify"

def send_command(command):
    payload = {
        "apikey": API_KEY,
        "task": "reactor",
        "answer": {
            "command": command
        }
    }
    response = requests.post(URL, json=payload)
    return response.json()

print("START:")
state0 = send_command("start")
print(json.dumps(state0['blocks'], indent=2))
print("RIGHT:")
state1 = send_command("right")
print(json.dumps(state1['blocks'], indent=2))
