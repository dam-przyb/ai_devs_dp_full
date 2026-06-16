import hashlib
import json
import os
import re
import time
from typing import Any, Dict, List, Tuple
from dotenv import load_dotenv
import requests
from langchain_openai import ChatOpenAI

# Load env from root directory
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, "..", "..", ".env")
load_dotenv(dotenv_path=env_path)


class RocketCrashedException(Exception):
    """Exception raised when the rocket crashes."""
    pass




def make_request(method: str, url: str, **kwargs: Any) -> requests.Response:
    """Perform an HTTP request with automatic retries for transient failures.

    Args:
        method: HTTP method (e.g., 'GET' or 'POST').
        url: Request target URL.
        **kwargs: Additional arguments for requests request.

    Returns:
        Response object of a successful request.

    Raises:
        RocketCrashedException: If the rocket crashed during verification.
        RuntimeError: If all retry attempts are exhausted.
    """
    max_retries = 10
    for i in range(max_retries):
        try:
            if method.upper() == "GET":
                response = requests.get(url, **kwargs)
            elif method.upper() == "POST":
                response = requests.post(url, **kwargs)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            # Back off specifically on 429 rate limits
            if response.status_code == 429:
                sleep_time = 2 * (i + 1)
                print(f"[{i + 1}/{max_retries}] Request to {url} returned status 429 (Rate Limited). Retrying in {sleep_time}s...")
                time.sleep(sleep_time)
                continue

            # Retry on server errors
            if response.status_code in [500, 502, 503, 504]:
                print(f"[{i + 1}/{max_retries}] Request to {url} returned status {response.status_code}. Retrying...")
                time.sleep(1.5)
                continue

            # If rocket crashed (status 400 with crash information), raise immediately without retrying
            if response.status_code == 400:
                try:
                    data = response.json()
                    if data.get("crashed") or "crashed" in data.get("message", "").lower() or data.get("code") == -950:
                        raise RocketCrashedException(data.get("message", "Rocket crashed."))
                except RocketCrashedException:
                    raise
                except Exception:
                    pass

            if response.status_code in [200, 201]:
                return response

            print(
                f"[{attempt + 1}/{max_retries}] Request to {url} returned status {response.status_code}. "
                f"Content: {response.text[:200]}. Retrying..."
            )
        except RocketCrashedException:
            raise
        except Exception as e:
            print(
                f"[{attempt + 1}/{max_retries}] Request to {url} failed with error: {e}. Retrying..."
            )

        time.sleep(delay)
        delay *= 1.5

    raise RuntimeError(f"Failed to query {url} after {max_retries} attempts.")


def parse_distorted_scanner(text: str, llm: ChatOpenAI) -> Tuple[Dict[str, Any], str, str]:
    """Decode and repair a distorted JSON string returned by the frequency scanner.

    Args:
        text: Noisy, corrupted JSON string from frequencyScanner.
        llm: LLM client used to repair and parse JSON structure.

    Returns:
        A tuple of (decoded dict, prompt string, raw LLM text response).
    """
    prompt = f"""You are an expert at decoding distorted and noisy signals.
We received a noisy response from a frequency scanner that contains 'frequency' (an integer) and 'detectionCode' (a string).
Noisy response:
"{text}"

Identify the original frequency and detectionCode values.
Note: The quotes wrapping keys and values in the JSON may be distorted (e.g. using single quotes, backticks, or mismatched quotes like "abc'). Do NOT include these wrapping quotes (or distorted quotes) in the parsed values.

Return ONLY a JSON object with keys "frequency" (integer) and "detectionCode" (string). Do not add any markdown formatting or explanations."""

    response = llm.invoke(prompt)
    content = str(response.content).strip()

    # Clean markdown formatting if present
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    content = content.strip("` \n\t")

    try:
        data = json.loads(content)
        if "frequency" in data and "detectionCode" in data:
            return {
                "frequency": int(data["frequency"]),
                "detectionCode": str(data["detectionCode"]).strip("\"'`"),
            }, prompt, content
        raise ValueError("Missing keys in parsed JSON")
    except Exception as e:
        print(f"Error parsing LLM JSON: {e}. Raw content: {content}")
        # Regex fallback
        freq_match = re.search(r'"frequency"\s*:\s*(\d+)', text)
        code_match = re.search(r'"detectionCode"\s*:\s*"([^"]+)"', text)
        if freq_match and code_match:
            return {
                "frequency": int(freq_match.group(1)),
                "detectionCode": code_match.group(1).strip("\"'`"),
            }, prompt, content
        raise e


def parse_hint_for_rock(hint: str, current_row: int, base_row: int, llm: ChatOpenAI) -> Tuple[List[int], str, str]:
    """Translate relative and nautical hints into the exact list of row indices containing the rock.

    All hints are vehicle-relative (relative to the pilot's current_row). The critical rule
    for edge rows (1 or 3) is that a side direction encompasses ALL rows on that open side:
    - Pilot at row 1 + starboard/right → rock could be row 2 OR row 3 → return [2, 3]
    - Pilot at row 3 + port/left → rock could be row 1 OR row 2 → return [1, 2]

    Args:
        hint: Spatial/nautical hint message in English describing the rock position.
        current_row: Current row position of the rocket (1, 2, or 3).
        base_row: Row number of the target base destination (1, 2, or 3).
        llm: LLM client used to translate text.

    Returns:
        A tuple of (list of row indices, prompt string, raw LLM text response).
    """
    # Build explicit direction table based on current_row — the ONLY interpretation model.
    # All hints are vehicle-relative (relative to the pilot's current position).
    # CRITICAL: Edge-row pilots (row 1 or 3) must return BOTH rows on the open side.
    if current_row == 1:
        port_result = "[1] (you are already AT the top wall — port does not apply; treat as ahead)"
        starboard_result = "[2, 3] — BOTH rows (pilot is at top edge, so entire open side is starboard)"
    elif current_row == 2:
        port_result = "[1] only"
        starboard_result = "[3] only"
    else:  # current_row == 3
        port_result = "[1, 2] — BOTH rows (pilot is at bottom edge, so entire open side is port)"
        starboard_result = "[3] (you are already AT the bottom wall — starboard does not apply; treat as ahead)"

    prompt = f"""You are a navigator on a 3-row grid (rows 1, 2, 3).
- Row 1 is the top row.
- Row 2 is the middle row.
- Row 3 is the bottom row.

The pilot is currently at row {current_row}. The target base is at row {base_row}.

All hints are VEHICLE-RELATIVE — described from the pilot's own perspective at row {current_row}.

DIRECTION TABLE for pilot at row {current_row}:
  "ahead / front / bow / nose / cockpit / trajectory / flight line / center / straight out" -> [{current_row}]
  "port / left / larboard" -> {port_result}
  "starboard / right" -> {starboard_result}
  "sides / flanks / wings" (when clear) -> confirms rock is NOT on those sides, rock is ahead

GROUND TRUTH EXAMPLES (all confirmed correct from actual game data):

Example 1 — starboard from row 2 = row 3 only:
- Hint: "The path on your port side stays open, and nothing blocks the nose of the craft. The trouble is sitting off your starboard wing."
- Pilot Row: 2, Base Row: 3
- Output: {{"rock_rows": [3], "reasoning": "Starboard from row 2 = row 3."}}

Example 2 — port from row 3 = BOTH rows 1 and 2 (edge rule):
- Hint: "Port is the side that currently carries the risk. The bow and starboard side remain clear."
- Pilot Row: 3, Base Row: 3
- Output: {{"rock_rows": [1, 2], "reasoning": "Port from edge row 3 = [1, 2] — both open-side rows."}}

Example 3 — starboard from row 1 = BOTH rows 2 and 3 (CRITICAL edge rule):
- Hint: "The only side you should distrust is starboard. Forward and port look clear."
- Pilot Row: 1, Base Row: 1
- Output: {{"rock_rows": [2, 3], "reasoning": "Starboard from edge row 1 = [2, 3] — both open-side rows."}}

Now apply the direction table and rules above to the following hint.
Return a JSON object with:
- "rock_rows": list of integers (1, 2, or 3) where the rock is located
- "reasoning": brief explanation referencing the direction table

Hint to parse: "{hint}"
Pilot row: {current_row} | Base row: {base_row}

Return ONLY the JSON. No markdown code block wrapper."""

    response = llm.invoke(prompt)
    content = str(response.content).strip()

    # Clean markdown formatting if present
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    content = content.strip("` \n\t")

    try:
        data = json.loads(content)
        return [int(r) for r in data["rock_rows"]], prompt, content
    except Exception as e:
        print(f"Error parsing LLM JSON in parse_hint_for_rock: {e}. Raw content: {content}")
        # Keyword fallback — pure vehicle-relative model
        h_lower = hint.lower()
        # Forward/center keywords → current_row
        if (
            "line of travel" in h_lower
            or "flight line" in h_lower
            or "straight out" in h_lower
            or "cockpit" in h_lower
            or "trajectory" in h_lower
            or "in front" in h_lower
            or "straight ahead" in h_lower
        ):
            rows = [current_row]
            return rows, prompt, f"Fallback: forward/center -> {rows}. Error: {e}"
        if "port" in h_lower or "left" in h_lower or "larboard" in h_lower:
            if current_row == 3:
                return [1, 2], prompt, f"Fallback: port side of row 3 is [1, 2]. Error: {e}"
            return [max(1, current_row - 1)], prompt, f"Fallback: port side of row {current_row} is {max(1, current_row - 1)}. Error: {e}"
        if "starboard" in h_lower or "right" in h_lower:
            if current_row == 1:
                return [2, 3], prompt, f"Fallback: starboard side of row 1 is [2, 3]. Error: {e}"
            return [min(3, current_row + 1)], prompt, f"Fallback: starboard side of row {current_row} is {min(3, current_row + 1)}. Error: {e}"
        if (
            "ahead" in h_lower
            or "front" in h_lower
            or "bow" in h_lower
            or "fore" in h_lower
            or "center" in h_lower
        ):
            return [current_row], prompt, f"Fallback: front is row {current_row}. Error: {e}"
        raise e


def is_clear_response(text: str) -> bool:
    """Determine if the frequency scanner response indicates that the path is clear.

    Args:
        text: Raw response string from the frequency scanner.

    Returns:
        True if the path is clear, False if targeted by a radar.
    """
    return bool(re.search(r"cl[e]+ar", text, re.IGNORECASE))


def check_and_disarm_radar(aidevs_key: str, llm: ChatOpenAI, step_log: Dict[str, Any]) -> None:
    """Query the scanner, detect if targeted, and send the disarm payload if necessary.

    Args:
        aidevs_key: API key for AI Devs 4 verify endpoint.
        llm: LLM client used to decode scanner JSON.
        step_log: Dictionary containing logs for the current step.
    """
    scanner_url = "https://hub.ag3nts.org/api/frequencyScanner"
    step_log["scanner_checks"] = []
    
    while True:
        url = f"{scanner_url}?key={aidevs_key}"
        resp = make_request("GET", url)
        text = resp.text.strip()

        check_entry = {"raw_response": text}

        # Check if clear
        if is_clear_response(text):
            print(f"Frequency check: It's clear! No active radar targeting us. Raw response: {text}")
            check_entry["status"] = "clear"
            step_log["scanner_checks"].append(check_entry)
            break

        print(f"Frequency check: Radar detected! Scanner response: {text}")
        check_entry["status"] = "targeted"

        # Parse noisy response
        try:
            data, prompt, raw_content = parse_distorted_scanner(text, llm)
            frequency = data["frequency"]
            detection_code = data["detectionCode"]
            check_entry["decoded"] = data
            check_entry["llm_prompt"] = prompt
            check_entry["llm_raw_response"] = raw_content
            print(
                f"Decoded radar info -> Frequency: {frequency}, Detection Code: {detection_code}"
            )

            # Compute SHA1(detectionCode + "disarm")
            disarm_str = f"{detection_code}disarm"
            disarm_hash = hashlib.sha1(disarm_str.encode("utf-8")).hexdigest()
            print(f"Computed disarmHash: {disarm_hash}")

            # Send disarm payload
            payload = {
                "apikey": aidevs_key,
                "frequency": frequency,
                "disarmHash": disarm_hash,
            }
            check_entry["disarm_payload"] = payload
            
            disarm_resp = make_request("POST", scanner_url, json=payload)
            check_entry["disarm_response"] = disarm_resp.text
            print(
                f"Disarm request sent. Status: {disarm_resp.status_code}, Response: {disarm_resp.text}"
            )
        except Exception as e:
            check_entry["error"] = str(e)
            print(f"Error during disarming process: {e}. Retrying check...")
            time.sleep(1)
            
        step_log["scanner_checks"].append(check_entry)


def main() -> bool:
    """Main execution loop that coordinates the rocket navigation and path solving."""
    aidevs_key = os.getenv("AIDEVSKEY")
    openrouter_key = os.getenv("OPENROUTERKEY")

    if not aidevs_key:
        print("Error: AIDEVSKEY not found in environment variables.")
        return False
    if not openrouter_key:
        print("Error: OPENROUTERKEY not found in environment variables.")
        return False

    # Instantiate LangChain OpenRouter model
    llm = ChatOpenAI(
        model="openai/gpt-oss-120b:free",
        openai_api_key=openrouter_key,
        openai_api_base="https://openrouter.ai/api/v1",
    )

    verify_url = "https://hub.ag3nts.org/verify"
    
    session_log = {
        "timestamp": time.strftime("%Y%m%d_%H%M%S"),
        "start_response": None,
        "steps": [],
        "final_state": None
    }
    
    def save_session_log() -> None:
        run_log_dir = os.path.join(script_dir, "run_log")
        os.makedirs(run_log_dir, exist_ok=True)
        
        # Save timestamped log
        log_path = os.path.join(run_log_dir, f"{session_log['timestamp']}.json")
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(session_log, f, indent=4, ensure_ascii=False)
        print(f"\nSaved LLM actions and game logs to {log_path}")
        
        # Save to literal timestamp.json (so user has a static path)
        static_log_path = os.path.join(run_log_dir, "timestamp.json")
        with open(static_log_path, "w", encoding="utf-8") as f:
            json.dump(session_log, f, indent=4, ensure_ascii=False)
        print(f"Saved latest log to {static_log_path}")

    # 1. Start the game
    print("Starting new game session...")
    payload = {
        "apikey": aidevs_key,
        "task": "goingthere",
        "answer": {"command": "start"},
    }
    
    try:
        resp = make_request("POST", verify_url, json=payload)
        game_state = resp.json()
        session_log["start_response"] = game_state
        print("Start Response:", json.dumps(game_state, indent=2))

        current_col = game_state["player"]["col"]
        current_row = game_state["player"]["row"]
        base_row = game_state["base"]["row"]
        base_col = game_state["base"]["col"]
        curr_stone = game_state.get("currentColumn", {}).get("stoneRow")

        # Session-scoped hint memory: stores confirmed hint -> actual stone row
        # Populated after each move from move_response.currentColumn.stoneRow
        hint_memory: Dict[str, int] = {}

        print(
            f"Started at (col={current_col}, row={current_row}). Target base is at (col={base_col}, row={base_row})."
        )

        # Loop until the rocket reaches base_col
        while current_col < base_col:
            print(f"\n--- STEP {current_col} -> {current_col + 1} ---")
            
            step_log = {
                "step_number": len(session_log["steps"]) + 1,
                "current_col": current_col,
                "current_row": current_row,
                "scanner_checks": [],
                "hint_raw": None,
                "hint_llm_response": None,
                "hint_interpretation_mode": None,
                "pilot_at_edge": current_row in (1, 3),
                "stone_rows": None,
                "candidates": None,
                "safe_rows_after_filter": None,
                "selected_move": None,
                "move_response": None,
                "error": None
            }
            session_log["steps"].append(step_log)

            # A. Check and disarm radar at current position
            check_and_disarm_radar(aidevs_key, llm, step_log)

            # B. Get hint for next column
            print("Fetching radio hint for the next column...")
            hint_resp = make_request(
                "POST",
                "https://hub.ag3nts.org/api/getmessage",
                json={"apikey": aidevs_key},
            )
            hint_data = hint_resp.json()
            hint = hint_data.get("hint", "")
            step_log["hint_raw"] = hint
            print(f"Hint received: '{hint}'")

            # C. Parse hint to find rock rows
            # Priority 1: Hint memory — confirmed stone row from earlier in this session.
            if hint in hint_memory:
                stone_rows = [hint_memory[hint]]
                prompt = "[MEMORY CACHE]"
                raw_content = f"Cached: hint seen before, actual stone was at row {hint_memory[hint]}"
                step_log["hint_interpretation_mode"] = "memory_cache"
                print(f"[CACHE HIT] Rock in column {current_col + 1} confirmed from memory: {stone_rows}")
            # Priority 2: LLM inference.
            else:
                stone_rows, prompt, raw_content = parse_hint_for_rock(hint, current_row, base_row, llm)
                step_log["hint_interpretation_mode"] = (
                    "llm_multi_row" if len(stone_rows) > 1 else "llm_single_row"
                )
                print(f"Rock in column {current_col + 1} is potentially at rows {stone_rows}")
            step_log["hint_llm_prompt"] = prompt
            step_log["hint_llm_response"] = raw_content
            step_log["stone_rows"] = stone_rows

            # D. Decide move
            
            # 4. Decide on move
            all_candidates = [("left", current_row - 1), ("go", current_row), ("right", current_row + 1)]
            # Filter by grid bounds
            all_candidates = [c for c in all_candidates if 1 <= c[1] <= 3]
            
            # Filter out known stone rows in the next column, AND the stone in the current column!
            # If we move diagonally into target_row, and the current column's rock is also at target_row, we hit it!
            step_log["safe_rows_after_filter"] = [r for r in [1, 2, 3] if r not in stone_rows and r != curr_stone]
            
            valid_candidates = [
                c for c in all_candidates 
                if c[1] not in stone_rows and c[1] != curr_stone
            ]
            step_log["candidates"] = {
                "all": all_candidates,
                "valid_non_stone": valid_candidates
            }
            step_log["safe_rows_after_filter"] = [row for _, row in valid_candidates]
            
            if not valid_candidates:
                print(
                    f"WARNING: No valid moves that avoid rock rows {stone_rows}! Choosing all non-stone candidates as fallback."
                )
                valid_candidates = [
                    (cmd, row) for cmd, row in all_candidates if row not in stone_rows
                ]
                if not valid_candidates:
                    valid_candidates = [("go", current_row)]

            # Score candidates based on reachability and proximity to target row
            def score_candidate(item: Tuple[str, int]) -> Tuple[int, int]:
                cmd, row = item
                next_col = current_col + 1
                is_reachable = abs(row - base_row) <= (base_col - next_col)
                distance = abs(row - base_row)
                # We want reachable moves first, then minimum distance
                return (-int(is_reachable), distance)

            valid_candidates.sort(key=score_candidate)
            best_cmd, best_row = valid_candidates[0]
            step_log["selected_move"] = {"command": best_cmd, "target_row": best_row}
            print(f"Valid moves sorted (best first): {valid_candidates}")
            print(f"Selected move command: '{best_cmd}' to row {best_row}")

            # E. Send move command
            move_payload = {
                "apikey": aidevs_key,
                "task": "goingthere",
                "answer": {"command": best_cmd},
            }
            print(f"Sending move command '{best_cmd}'...")
            try:
                move_resp = make_request("POST", verify_url, json=move_payload)
                move_data = move_resp.json()
                step_log["move_response"] = move_data
                          # Check for flag in response
                resp_text = move_resp.text
                if "FLG:" in resp_text or "flag" in resp_text.lower():
                    print("\n*** FLAG RECEIVED! ***")
                    
                    # Try to extract just the flag string and format it properly
                    flag_val = move_data.get("flag", resp_text)
                    if "FLG:" in flag_val:
                        flag_val = flag_val.split("FLG:")[1].split('"')[0].strip()
                    
                    # Remove underscores/dashes per user request
                    formatted_flag = flag_val.replace("_", "").replace("-", "")
                    
                    print(f"RAW FLAG: {flag_val}")
                    print(f"FORMATTED FLAG: {formatted_flag}")
                    session_log["final_state"] = {"status": "success", "flag": formatted_flag}

                    # Ensure run_log folder exists
                    run_log_dir = os.path.join(script_dir, "run_log")
                    os.makedirs(run_log_dir, exist_ok=True)
                    output_path = os.path.join(run_log_dir, "solve.json")
                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(move_data, f, indent=4, ensure_ascii=False)
                    print(f"Saved solver results to {output_path}")
                    return True # Success!

                # Update hint memory with confirmed ground truth from move response
                if "currentColumn" in move_data:
                    confirmed_stone_row = move_data["currentColumn"].get("stoneRow")
                    if confirmed_stone_row is not None and hint:
                        if hint not in hint_memory:
                            hint_memory[hint] = confirmed_stone_row
                            print(f"[MEMORY] Stored: hint -> actual stone row {confirmed_stone_row}")
                        elif hint_memory[hint] != confirmed_stone_row:
                            print(
                                f"[MEMORY] WARNING: hint seen with different stone rows: "
                                f"stored={hint_memory[hint]}, new={confirmed_stone_row}. Keeping first."
                            )

                # Update current state
                if "player" in move_data:
                    current_col = move_data["player"]["col"]
                    current_row = move_data["player"]["row"]
                else:
                    print(
                        "Warning: Player position missing in response. Manually incrementing column..."
                    )
                    current_col += 1
                
                if "currentColumn" in move_data and "stoneRow" in move_data["currentColumn"]:
                    curr_stone = move_data["currentColumn"]["stoneRow"]
            except RocketCrashedException as rce:
                print(f"\n!!! ROCKET CRASHED !!! Details: {rce}")
                step_log["error"] = str(rce)
                session_log["final_state"] = {"status": "crashed", "error": str(rce)}
                return False # Failed, will retry
                
    except Exception as general_err:
        print(f"An unexpected error occurred during execution: {general_err}")
        session_log["final_state"] = {"status": "error", "error": str(general_err)}
        return False
    finally:
        save_session_log()

def run_until_success():
    """Wrapper to run the game loop until the flag is retrieved, overcoming random API crashes."""
    attempt = 1
    max_attempts = 10
    while attempt <= max_attempts:
        print(f"\n{'='*50}\nSTARTING ATTEMPT {attempt}/{max_attempts}\n{'='*50}")
        success = main()
        if success:
            print("\nSUCCESS! Flag retrieved. Exiting loop.")
            break
        print("\nAttempt failed due to crash or error. Restarting game...\n")
        attempt += 1
        time.sleep(2) # Brief pause before restarting
    
    if attempt > max_attempts:
        print("\nReached max attempts (10) without success to save credits. Exiting.")

if __name__ == "__main__":
    run_until_success()

