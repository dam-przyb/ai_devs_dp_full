"""Quick test to verify drone API response structure."""

import json
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("AIDEVSKEY")
BASE_URL = "https://hub.ag3nts.org"


def call_drone_api(instructions: list[str]) -> dict:
    """Send instructions to the drone API and return parsed response."""
    payload = {
        "apikey": API_KEY,
        "task": "drone",
        "answer": {
            "instructions": instructions,
        },
    }
    response = httpx.post(f"{BASE_URL}/verify", json=payload, timeout=30)
    print(f"Status code: {response.status_code}")
    print(f"Raw response text:\n{response.text}")
    try:
        return response.json()
    except Exception:
        return {"raw": response.text}


if __name__ == "__main__":
    print("=== Drone API Quick Test ===")
    print(f"API Key: {API_KEY[:8]}...{API_KEY[-4:] if API_KEY else 'NOT SET'}")
    print()

    print("--- Test 1: selfCheck ---")
    result = call_drone_api(["selfCheck"])
    print(f"Parsed JSON:\n{json.dumps(result, indent=2, ensure_ascii=False)}")
    print()

    print("--- Test 2: getConfig ---")
    result2 = call_drone_api(["getConfig"])
    print(f"Parsed JSON:\n{json.dumps(result2, indent=2, ensure_ascii=False)}")
