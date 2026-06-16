import requests
import json

def main():
    url = "https://hub.ag3nts.org/encoder_deeper"
    payload = {"text": "AAAAAAA"}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://hub.ag3nts.org/deeper",
        "Origin": "https://hub.ag3nts.org",
        "Content-Type": "application/json"
    }
    print(f"Testing {url} with {payload}...")
    try:
        res = requests.post(url, json=payload, headers=headers)
        print("Status Code:", res.status_code)
        print("Headers:", res.headers)
        print("Response:", res.text)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    main()
