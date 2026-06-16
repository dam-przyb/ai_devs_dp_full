import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def send_query(query: str, api_key: str) -> dict:
    url = "https://hub.ag3nts.org/verify"
    payload = {
        "apikey": api_key,
        "task": "foodwarehouse",
        "answer": {
            "tool": "database",
            "query": query
        }
    }
    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json()

def main():
    api_key = os.getenv("AIDEVSKEY")
    if not api_key:
        print("Error: AIDEVSKEY not found in environment variables.")
        return

    print("Querying database tables...")
    try:
        # Step 1: Show tables
        tables_res = send_query("show tables", api_key)
        
        # The API returns tables under the "tables" key
        tables = tables_res.get("tables", [])
        print("Found tables:", tables)
        
        db_dump = {
            "tables": tables,
            "schemas": {},
            "samples": {}
        }
        
        for table_name in tables:
            print(f"Querying table: {table_name}")
            # Query schema
            try:
                schema_res = send_query(f"select sql from sqlite_master where type='table' and name='{table_name}'", api_key)
                # Let's see if the schema query returns columns/results
                # If the database returns the query results in 'reply', let's print schema_res to be sure.
                db_dump["schemas"][table_name] = schema_res.get("reply", schema_res)
            except Exception as ex:
                print(f"Could not get schema for {table_name}: {ex}")
            
            # Query sample records
            try:
                sample_res = send_query(f"select * from {table_name} limit 50", api_key)
                db_dump["samples"][table_name] = sample_res.get("reply", sample_res)
            except Exception as ex:
                print(f"Could not get samples for {table_name}: {ex}")

        # Save specifically in s4/s4e5/run_log relative to the script directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(script_dir, "run_log")
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = os.path.join(output_dir, "db_info.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(db_dump, f, indent=4, ensure_ascii=False)
            
        print(f"Successfully saved database info to {output_path}")

    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":
    main()
