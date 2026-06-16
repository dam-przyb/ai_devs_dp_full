import asyncio
import os
import re
import httpx
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

AIDEVS_KEY = os.getenv("AIDEVSKEY")
VERIFY_URL = "https://hub.ag3nts.org/verify"

if not AIDEVS_KEY:
    raise ValueError("Missing AIDEVSKEY in environment variables.")

async def send_action(client: httpx.AsyncClient, action: str, **kwargs):
    payload = {
        "apikey": AIDEVS_KEY,
        "task": "windpower",
        "answer": {
            "action": action,
            **kwargs
        }
    }
    response = await client.post(VERIFY_URL, json=payload, timeout=30)
    return response.json()

def parse_deficit(deficit_str: str) -> float:
    # Find all numbers in the string (including floats)
    numbers = re.findall(r"\d+\.?\d*", deficit_str)
    if not numbers:
        return 0.0
    # Return the maximum to be safe
    return max(float(num) for num in numbers)

def estimate_power(wind: float) -> float:
    if wind < 4.0:
        return 0.0
    if wind > 14.0:
        return 0.0
    
    # Linear interpolation using the lower bound yield percentages:
    # 4 -> 10%
    # 6 -> 30%
    # 8 -> 60%
    # 10 -> 90%
    # 12-14 -> 100%
    if wind >= 12.0:
        yield_pct = 100.0
    elif wind >= 10.0:
        yield_pct = 90.0 + (wind - 10.0) * (100.0 - 90.0) / (12.0 - 10.0)
    elif wind >= 8.0:
        yield_pct = 60.0 + (wind - 8.0) * (90.0 - 60.0) / (10.0 - 8.0)
    elif wind >= 6.0:
        yield_pct = 30.0 + (wind - 6.0) * (60.0 - 30.0) / (8.0 - 6.0)
    else:
        yield_pct = 10.0 + (wind - 4.0) * (30.0 - 10.0) / (6.0 - 4.0)
        
    return 14.0 * (yield_pct / 100.0)

async def main():
    async with httpx.AsyncClient() as client:
        print("[1/8] Starting service window...")
        start_res = await send_action(client, "start")
        print("Start Response:", start_res)
        
        # We need to act quickly, so queue weather, turbinecheck, and powerplantcheck in parallel
        print("[2/8] Queuing initial reports...")
        q_tasks = [
            send_action(client, "get", param="weather"),
            send_action(client, "get", param="turbinecheck"),
            send_action(client, "get", param="powerplantcheck")
        ]
        q_responses = await asyncio.gather(*q_tasks)
        print("Queue responses:", q_responses)
        
        # Poll for the three results concurrently
        print("[3/8] Polling for reports...")
        weather_report = None
        turbine_report = None
        powerplant_report = None
        
        # Poll up to 100 times with a 0.2s delay (20s total)
        for poll_idx in range(1, 101):
            await asyncio.sleep(0.2)
            res = await send_action(client, "getResult")
            
            if isinstance(res, dict):
                sf = res.get("sourceFunction")
                if sf == "weather":
                    weather_report = res
                    print(f"  -> Poll #{poll_idx}: Retrieved weather report.")
                elif sf == "turbinecheck":
                    turbine_report = res
                    print(f"  -> Poll #{poll_idx}: Retrieved turbinecheck report.")
                elif sf == "powerplantcheck":
                    powerplant_report = res
                    print(f"  -> Poll #{poll_idx}: Retrieved powerplantcheck report.")
                    
            if weather_report and turbine_report and powerplant_report:
                print("All initial reports collected!")
                break
                
        if not weather_report or not powerplant_report:
            print("ERROR: Did not retrieve all initial reports in time.")
            return

        # 4. Analyze reports
        # Parse power deficit
        deficit_raw = powerplant_report.get("powerDeficitKw", "0")
        if isinstance(deficit_raw, (int, float)):
            deficit = float(deficit_raw)
        else:
            deficit = parse_deficit(str(deficit_raw))
        print(f"Parsed power deficit: {deficit} kW")
        
        # Parse forecast
        forecast = weather_report.get("forecast", [])
        print(f"Analyzing {len(forecast)} weather forecast hours...")
        
        storms = []
        production_hour = None
        
        for record in forecast:
            ts = record.get("timestamp")
            wind = record.get("windMs")
            if wind is None:
                continue
            
            # If wind is > 14 m/s, it's a storm (cutoffWindMs = 14)
            if wind > 14.0:
                storms.append((ts, wind))
            # Find first production hour where we can cover the deficit
            elif production_hour is None:
                est_power = estimate_power(wind)
                if est_power >= deficit:
                    production_hour = (ts, wind, est_power)
                    
        print(f"Storm hours detected to protect (total {len(storms)}): {storms}")
        if production_hour:
            print(f"First sufficient production hour: {production_hour[0]} with windMs={production_hour[1]} (est. power={production_hour[2]:.2f} kW)")
        else:
            print("ERROR: No production hour found in forecast that covers the deficit.")
            return

        # Define configurations to generate unlock codes for
        # Form: (timestamp, windMs, pitchAngle, turbineMode)
        configs_to_gen = []
        for ts, wind in storms:
            configs_to_gen.append((ts, wind, 90, "idle"))
            
        configs_to_gen.append((production_hour[0], production_hour[1], 0, "production"))
        
        # 5. Request unlock codes asynchronously
        print("[4/8] Requesting unlock codes asynchronously...")
        code_tasks = []
        for ts, wind, pitch, mode in configs_to_gen:
            dt, tm = ts.split(" ")
            code_tasks.append(
                send_action(
                    client,
                    "unlockCodeGenerator",
                    startDate=dt,
                    startHour=tm,
                    windMs=wind,
                    pitchAngle=pitch
                )
            )
        code_responses = await asyncio.gather(*code_tasks)
        print("Code generation requests queued:", code_responses)
        
        # Poll for all codes
        print("[5/8] Polling for unlock codes...")
        unlock_codes = {}
        needed_count = len(configs_to_gen)
        
        # Poll up to 100 times with a 0.2s delay
        for poll_idx in range(1, 101):
            await asyncio.sleep(0.2)
            res = await send_action(client, "getResult")
            
            if isinstance(res, dict) and res.get("sourceFunction") == "unlockCodeGenerator":
                signed_params = res.get("signedParams", {})
                sd = signed_params.get("startDate")
                sh = signed_params.get("startHour")
                code_val = res.get("unlockCode")
                
                if sd and sh and code_val:
                    matched_ts = f"{sd} {sh}"
                    unlock_codes[matched_ts] = code_val
                    print(f"  -> Poll #{poll_idx}: Collected unlockCode for {matched_ts}")
                    
            if len(unlock_codes) >= needed_count:
                print("All unlock codes collected!")
                break
                
        if len(unlock_codes) < needed_count:
            print(f"ERROR: Could not fetch all unlock codes in time (got {len(unlock_codes)}/{needed_count}).")
            return
            
        # 6. Store configs
        print("[6/8] Storing turbine configurations...")
        configs_payload = {}
        for ts, wind, pitch, mode in configs_to_gen:
            configs_payload[ts] = {
                "pitchAngle": pitch,
                "turbineMode": mode,
                "unlockCode": unlock_codes[ts]
            }
            
        config_res = await send_action(client, "config", configs=configs_payload)
        print("Config Response:", config_res)
        
        # 7. Run mandatory turbinecheck
        print("[7/8] Queuing and running mandatory turbine check...")
        q_check = await send_action(client, "get", param="turbinecheck")
        print("Turbine check queued:", q_check)
        
        turbinecheck_done = False
        for poll_idx in range(1, 51):
            await asyncio.sleep(0.2)
            res = await send_action(client, "getResult")
            if isinstance(res, dict) and res.get("sourceFunction") == "turbinecheck":
                print("Final Turbine Check Report:")
                import json
                print(json.dumps(res, indent=2, ensure_ascii=False))
                turbinecheck_done = True
                break
                
        if not turbinecheck_done:
            print("ERROR: Did not retrieve the final turbinecheck report.")
            return
            
        # 8. Submit final done
        print("[8/8] Submitting final 'done' action...")
        done_res = await send_action(client, "done")
        print("\n================ FINAL RESULTS ================")
        import json
        print(json.dumps(done_res, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(main())
