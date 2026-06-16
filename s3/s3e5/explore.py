import os
import json
import requests
from dotenv import load_dotenv

# Load env from root
load_dotenv(dotenv_path="../../.env")

API_KEY = os.getenv("AIDEVSKEY") or "9b2b37d3-dfab-42e0-a4b2-d84454981394"
BOOKS_URL = "https://hub.ag3nts.org/api/books"

def query_tool_raw(url, query):
    payload = {
        "apikey": API_KEY,
        "query": query
    }
    try:
        response = requests.post(url, json=payload)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def main():
    print("--- Querying Books for Water Rules ---")
    queries = ["water", "river", "swim", "dismount", "cross water"]
    for q in queries:
        res = query_tool_raw(BOOKS_URL, q)
        print(f"Query '{q}':")
        if res and "notes" in res:
            for note in res["notes"]:
                print(f"  [{note['id']}] {note['title']}: {note['content']}\n")
        else:
            print(f"  No notes found or error: {res}\n")

if __name__ == "__main__":
    main()
