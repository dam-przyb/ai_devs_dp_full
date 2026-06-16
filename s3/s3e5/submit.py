import json
import requests

VERIFY_URL = "https://hub.ag3nts.org/verify"

def main():
    try:
        with open("submission_payload.json", "r", encoding="utf-8") as f:
            payload = json.load(f)
    except FileNotFoundError:
        with open("s3/s3e5/submission_payload.json", "r", encoding="utf-8") as f:
            payload = json.load(f)

    print("Submitting payload to verification endpoint...")
    try:
        response = requests.post(VERIFY_URL, json=payload)
        response.raise_for_status()
        print("Success! Response from verification endpoint:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error submitting solution: {e}")
        if 'response' in locals() and response is not None:
            print(f"Response content: {response.text}")

if __name__ == "__main__":
    main()
