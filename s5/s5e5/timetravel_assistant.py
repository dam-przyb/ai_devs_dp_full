import os
import re
import time
import httpx
from dotenv import load_dotenv

# Load env from parent directory
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
load_dotenv(dotenv_path)

API_KEY = os.getenv("AIDEVSKEY")
URL = "https://hub.ag3nts.org/verify"

# Table of protections from the documentation (extracted for relevant years)
PROTECTION_TABLE = {
    2238: 91,
    2024: 19,
    2026: 28,  # Supposed present year, we will verify from config
}

def calculate_sync_ratio(day: int, month: int, year: int) -> float:
    val = (day * 8 + month * 12 + year * 7) % 101
    return round(val / 100, 2)

def send_action(action: str, param: str = None, value = None) -> dict:
    if not API_KEY:
        raise ValueError("AIDEVSKEY is missing from environment variables.")

    answer = {"action": action}
    if param is not None:
        answer["param"] = param
    if value is not None:
        answer["value"] = value

    payload = {
        "apikey": API_KEY,
        "task": "timetravel",
        "answer": answer
    }

    response = httpx.post(URL, json=payload, timeout=10.0)
    response.raise_for_status()
    return response.json()

def get_config() -> dict:
    try:
        return send_action("getConfig")
    except Exception as e:
        print(f"Error fetching config: {e}")
        return {}

def reset_device() -> dict:
    try:
        print("Resetting device...")
        res = send_action("reset")
        print("Device reset successfully.")
        return res
    except Exception as e:
        print(f"Error resetting device: {e}")
        return {}

def configure_param(param: str, value) -> dict:
    try:
        print(f"Configuring {param} to {value}...")
        res = send_action("configure", param, value)
        return res
    except Exception as e:
        print(f"Error configuring {param}: {e}")
        return {}

def parse_stabilization_hint(message: str) -> int:
    """Try to extract a number or clue about stabilization from the message."""
    # Look for patterns like "stabilization: X" or "stabilization to X" or "stabilization = X" or just numbers
    match = re.search(r"(?:stabilization|stabilizacji|ustaw|wartość)\D*(\d+)", message, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None

def run_stabilization_detection() -> int:
    """Fetch current config and extract stabilization hint from it."""
    raw_config = get_config()
    print("\n--- Current Configuration ---")
    for k, v in raw_config.items():
        if k == 'config':
            print("  Config parameters:")
            for ck, cv in v.items():
                print(f"    {ck}: {cv}")
        else:
            print(f"  {k}: {v}")
    
    msg = raw_config.get("message", "")
    print(f"API message: {msg}")
    
    hint = parse_stabilization_hint(msg)
    if hint is not None:
        print(f"Parsed stabilization hint from message: {hint}")
        return hint
    return None

def monitor_internal_mode(target_mode: int, target_year: int):
    print(f"\n--- Monitoring internalMode for target year {target_year} ---")
    print(f"We need internalMode = {target_mode}.")
    print("Device must be ACTIVE. Press Ctrl+C to stop monitoring.")
    
    last_mode = None
    try:
        while True:
            raw_config = get_config()
            if not raw_config:
                time.sleep(2)
                continue
            
            config = raw_config.get("config", {})
            mode = config.get("internalMode")
            flux = config.get("fluxDensity")
            status = config.get("mode")
            power = config.get("PWR")
            condition = config.get("condition")
            
            if mode != last_mode or True: # Print every check to show progress/live
                print(f"[{time.strftime('%H:%M:%S')}] Mode: {mode} (Need {target_mode}) | Flux Density: {flux}% | Status: {status} | Condition: {condition} | Power: {power}")
                last_mode = mode
                
            if mode == target_mode and flux == 100 and status == "active" and condition == "stable":
                print("\n" + "*"*60)
                print("*** READY FOR TRAVEL! ***")
                print("All systems optimal, flux density is 100%, mode matches!")
                print("Go to the Web UI: https://hub.ag3nts.org/timetravel_preview")
                print("CLICK the green pulsing sphere to perform the jump/tunnel now!")
                print("*"*60 + "\n")
            
            time.sleep(1.5)
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")

def get_target_mode(year: int) -> int:
    if year < 2000:
        return 1
    elif 2000 <= year <= 2150:
        return 2
    elif 2151 <= year <= 2300:
        return 3
    else:
        return 4

def setup_date(day: int, month: int, year: int):
    print(f"\n=== Setup Destination: {day:02d}-{month:02d}-{year} ===")
    
    # Calculate sync ratio
    sync = calculate_sync_ratio(day, month, year)
    print(f"Calculated sync ratio: {sync}")
    
    # Check if device is standby
    raw_config = get_config()
    config = raw_config.get("config", {})
    device_state = config.get("mode")
    print(f"Current device status: {device_state}")
    
    # Instruct user
    print("\n--- ACTION REQUIRED ---")
    print("1. Go to Web UI: https://hub.ag3nts.org/timetravel_preview")
    print("2. Ensure device is set to STANDBY.")
    pwr = PROTECTION_TABLE.get(year, "Check doc table")
    print(f"3. Set PWR to: {pwr}")
    if year == 2024:
        print("4. Ensure BOTH PT-A and PT-B are turned ON (Time Tunnel mode).")
    elif year == 2238:
        print("4. Ensure PT-A is OFF and PT-B is ON (Future Jump mode).")
    else:
        print(f"4. Ensure PT-A/PT-B are configured for year {year} (PT-A for past, PT-B for future relative to present).")
    
    input("\nConfirm Web UI is in STANDBY and configured as above, then press Enter to send API configuration...")
    
    # Send date parameters to API
    configure_param("day", day)
    configure_param("month", month)
    configure_param("year", year)
    res_sync = configure_param("syncRatio", sync)
    
    # Check stabilization hint
    print("\nDetecting stabilization hint from API...")
    hint = parse_stabilization_hint(res_sync.get("message", ""))
    if hint is None:
        hint = run_stabilization_detection()
        
    if hint is not None:
        print(f"Found stabilization hint: {hint}")
        val = input(f"Configure stabilization to {hint}? (Press Enter for Yes, or type value): ")
        if val.strip() == "":
            configure_param("stabilization", hint)
        else:
            configure_param("stabilization", int(val))
    else:
        val = input("Could not auto-detect stabilization value. Please check the above message and enter stabilization value manually: ")
        if val.strip():
            configure_param("stabilization", int(val))
            
    # Verify configuration
    final_raw_config = get_config()
    final_config = final_raw_config.get("config", {})
    print("\n--- Final Config before activation ---")
    for k, v in final_config.items():
        print(f"  {k}: {v}")
    print(f"API Message: {final_raw_config.get('message')}")
    
    print("\n--- ACTION REQUIRED ---")
    print("1. In Web UI, toggle device to ACTIVE.")
    print("2. The script will start monitoring internalMode.")
    input("Press Enter to start monitoring internalMode...")
    
    target_mode = get_target_mode(year)
    monitor_internal_mode(target_mode, year)

def main_menu():
    # Store present date once we get it
    present_date = None
    
    while True:
        print("\n" + "="*40)
        print(" CHRONOS-P1 TIME TRAVEL ASSISTANT ")
        print("="*40)
        print("1. Get Current Config (getConfig)")
        print("2. Reset Device (reset)")
        print("3. Prepare Step 1: Jump to 5 Nov 2238 (Future)")
        print("4. Prepare Step 2: Return to Present Date")
        print("5. Prepare Step 3: Tunnel to 12 Nov 2024 (Tunnel)")
        print("6. Run Custom Date Setup")
        print("7. Live Monitor Mode")
        print("8. Exit")
        
        choice = input("\nEnter choice (1-8): ").strip()
        
        if choice == "1":
            raw_config = get_config()
            print("\n--- Current Configuration ---")
            for k, v in raw_config.items():
                if k == 'config':
                    print("  Config parameters:")
                    for ck, cv in v.items():
                        print(f"    {ck}: {cv}")
                else:
                    print(f"  {k}: {v}")
            # Try to save present date from initial config
            config = raw_config.get("config", {})
            if config:
                y = config.get("year")
                m = config.get("month")
                d = config.get("day")
                if y and m and d and y < 2200: # Ensure it's not the future year we set
                    present_date = (d, m, y)
                    print(f"--> Saved Present Date: {d:02d}-{m:02d}-{y}")
        
        elif choice == "2":
            reset_device()
            
        elif choice == "3":
            setup_date(5, 11, 2238)
            
        elif choice == "4":
            if present_date is None:
                # Prompt user or read from config after reset
                print("No present date stored. Let's reset the device to check the present date.")
                reset_device()
                raw_config = get_config()
                config = raw_config.get("config", {})
                y = config.get("year")
                m = config.get("month")
                d = config.get("day")
                if y and m and d:
                    present_date = (d, m, y)
            
            if present_date:
                d, m, y = present_date
                print(f"Present Date is: {d:02d}-{m:02d}-{y}")
                # We need to set protection level for present year
                # Let's check if present year is in table
                if y not in PROTECTION_TABLE:
                    # Let's prompt user to input protection level or look at documentation
                    pwr = input(f"Enter protection level (PWR) for year {y} from documentation table: ").strip()
                    if pwr:
                        PROTECTION_TABLE[y] = int(pwr)
                setup_date(d, m, y)
            else:
                print("Could not determine present date.")
                
        elif choice == "5":
            setup_date(12, 11, 2024)
            
        elif choice == "6":
            try:
                day = int(input("Enter day (1-31): "))
                month = int(input("Enter month (1-12): "))
                year = int(input("Enter year (1500-2499): "))
                setup_date(day, month, year)
            except ValueError:
                print("Invalid input. Please enter integers.")
                
        elif choice == "7":
            try:
                year = int(input("Enter target year to monitor for: "))
                target_mode = get_target_mode(year)
                monitor_internal_mode(target_mode, year)
            except ValueError:
                print("Invalid input.")
                
        elif choice == "8":
            print("Goodbye.")
            break
        else:
            print("Invalid choice.")

if __name__ == "__main__":
    main_menu()
