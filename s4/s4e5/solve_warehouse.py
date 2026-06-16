import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def send_payload(payload_answer: dict, api_key: str) -> dict:
    url = "https://hub.ag3nts.org/verify"
    payload = {
        "apikey": api_key,
        "task": "foodwarehouse",
        "answer": payload_answer
    }
    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json()

def main():
    api_key = os.getenv("AIDEVSKEY")
    if not api_key:
        print("Error: AIDEVSKEY not found in environment variables.")
        return

    # 1. Load city demands
    script_dir = os.path.dirname(os.path.abspath(__file__))
    demands_path = os.path.join(script_dir, "content", "food4cities.json")
    with open(demands_path, "r", encoding="utf-8") as f:
        demands = json.load(f)
    
    cities = list(demands.keys())
    print(f"Loaded demands for {len(cities)} cities: {cities}")

    # 2. Query destinations from SQLite database via API
    # We query lower(name) in cities to get all destination IDs in a single query
    city_names_sql = ", ".join([f"'{c.lower()}'" for c in cities])
    query = f"SELECT destination_id, name FROM destinations WHERE lower(name) IN ({city_names_sql})"
    
    print(f"Executing query: {query}")
    db_res = send_payload({"tool": "database", "query": query}, api_key)
    
    # Check query response
    print("Database response:")
    print(json.dumps(db_res, indent=2, ensure_ascii=False))
    
    reply_rows = db_res.get("reply", [])
    if not reply_rows:
        # Sometimes query results are in another key like 'rows' if db_res structure differs
        reply_rows = db_res.get("rows", [])
        
    destination_map = {}
    for row in reply_rows:
        dest_id = row.get("destination_id")
        name = row.get("name")
        destination_map[name.lower()] = dest_id

    print("Destination mapping:")
    print(json.dumps(destination_map, indent=2))
    
    # Verify we found all 8 cities
    missing = [c for c in cities if c not in destination_map]
    if missing:
        print(f"Warning: Missing destination IDs for: {missing}")
        return

    # 3. Reset order status to clean up state
    print("Resetting warehouse orders state...")
    reset_res = send_payload({"tool": "reset"}, api_key)
    print("Reset response:", reset_res.get("message"))

    # Creator details (tgajewski, user_id: 2, birthday: 1991-04-06)
    creator_id = 2
    creator_login = "tgajewski"
    creator_birthday = "1991-04-06"

    # 4. Create orders and append items
    for city in cities:
        dest_id = destination_map[city]
        items_needed = demands[city]
        print(f"\n--- Processing city: {city} (Destination ID: {dest_id}) ---")
        
        # A. Generate signature
        print(f"Generating signature for {city}...")
        sig_res = send_payload({
            "tool": "signatureGenerator",
            "action": "generate",
            "login": creator_login,
            "birthday": creator_birthday,
            "destination": dest_id
        }, api_key)
        
        # Typically the signature is in a field named 'hash', 'signature', or in the response message/reply
        signature = sig_res.get("hash") or sig_res.get("signature") or sig_res.get("reply")
        if not signature:
            # Let's inspect signature response
            print("Signature response details:")
            print(json.dumps(sig_res, indent=2))
            # Fallback check if it's nested
            if isinstance(sig_res, dict) and "message" in sig_res and len(sig_res["message"]) == 40:
                # If message itself is the 40-character sha1 hash
                signature = sig_res["message"]
            else:
                print("Error: Could not retrieve signature.")
                return
        
        print(f"Signature generated: {signature}")

        # B. Create order
        print(f"Creating order for {city}...")
        order_res = send_payload({
            "tool": "orders",
            "action": "create",
            "title": f"Delivery for {city.capitalize()}",
            "creatorID": creator_id,
            "destination": dest_id,
            "signature": signature
        }, api_key)
        
        print("Create response:")
        print(json.dumps(order_res, indent=2))
        
        # Extract order ID from response. Let's look for 'id' or check structure.
        order_id = order_res.get("id") or order_res.get("reply", {}).get("id")
        if not order_id and "message" in order_res:
            # Maybe the order ID is returned in some other field or we need to extract it
            # e.g., if there's a list or dictionary.
            pass
            
        if not order_id:
            # If we couldn't find order_id directly, let's check keys
            # Let's try to extract if order_res has 'order' key
            if "order" in order_res and isinstance(order_res["order"], dict):
                order_id = order_res["order"].get("id")
            elif isinstance(order_res.get("reply"), dict):
                order_id = order_res["reply"].get("id")
            elif isinstance(order_res.get("reply"), str):
                order_id = order_res["reply"]
                
        if not order_id:
            print("Error: Could not retrieve order ID.")
            return
            
        print(f"Order created successfully. Order ID: {order_id}")

        # C. Append items in batch mode
        print(f"Appending items for {city}: {items_needed}")
        append_res = send_payload({
            "tool": "orders",
            "action": "append",
            "id": order_id,
            "items": items_needed
        }, api_key)
        
        print("Append response:", append_res.get("message", "Success"))

    # 5. Call 'done' to verify all orders
    print("\nAll orders created and populated. Verifying completion...")
    done_res = send_payload({"tool": "done"}, api_key)
    print("Done response:")
    print(json.dumps(done_res, indent=2, ensure_ascii=False))

    # Save done response to run_log/flag.json
    output_dir = os.path.join(script_dir, "run_log")
    os.makedirs(output_dir, exist_ok=True)
    flag_path = os.path.join(output_dir, "flag.json")
    with open(flag_path, "w", encoding="utf-8") as f:
        json.dump(done_res, f, indent=4, ensure_ascii=False)
        
    print(f"Results saved to {flag_path}")

if __name__ == "__main__":
    main()
