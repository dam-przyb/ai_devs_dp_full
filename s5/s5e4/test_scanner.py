import os
import requests
from dotenv import load_dotenv

script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, "..", "..", ".env")
load_dotenv(dotenv_path=env_path)

def main():
    api_key = os.getenv("AIDEVSKEY")
    url = f"https://hub.ag3nts.org/api/frequencyScanner?key={api_key}"
    print(f"Querying {url}...")
    try:
        response = requests.get(url)
        print("Status Code:", response.status_code)
        print("Raw Content:", response.text)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    main()
