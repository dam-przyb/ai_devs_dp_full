"""LangGraph drone mission agent — AI_Devs4 S2E5.

Phase 1: Vision model (gpt-5.4) analyzes drone.png to locate the dam sector.
Phase 2: ReAct LangGraph agent uses drone API tools to complete the mission.
"""

import base64
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

load_dotenv()

API_KEY = os.getenv("AIDEVSKEY")
OPENROUTER_KEY = os.getenv("OPENROUTERKEY")
BASE_URL = "https://hub.ag3nts.org"
MODEL = "openai/gpt-5.4"
IMAGE_PATH = Path(__file__).parent / "drone.png"
FACILITY_ID = "PWR6132PL"
LOG_DIR = Path(__file__).parent / "run_logs"

# Flag pattern: {FLG:WORD} — only real words (letters), not template placeholders
FLAG_PATTERN = re.compile(r"\{FLG:[A-Za-z]+\}")


def get_llm(model: str = MODEL) -> ChatOpenAI:
    """Create a ChatOpenAI instance via OpenRouter."""
    return ChatOpenAI(
        model=model,
        openai_api_key=OPENROUTER_KEY,
        openai_api_base="https://openrouter.ai/api/v1",
        temperature=0,
    )


# ─── Run logger ───────────────────────────────────────────────────────────────

class RunLogger:
    """Collects run data and writes a timestamped JSON log to run_logs/."""

    def __init__(self) -> None:
        self.timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.data: dict = {
            "timestamp": self.timestamp,
            "phase1_vision": None,
            "api_calls": [],
            "agent_messages": [],
            "flag": None,
        }
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def log_vision(self, raw_response: str, col: int, row: int) -> None:
        """Record phase 1 vision result."""
        self.data["phase1_vision"] = {
            "raw_response": raw_response,
            "col": col,
            "row": row,
        }

    def log_api_call(self, instructions: list[str], response_text: str) -> None:
        """Record a single drone API call and its response."""
        try:
            response_parsed = json.loads(response_text)
        except Exception:
            response_parsed = {"raw": response_text}
        self.data["api_calls"].append(
            {"instructions": instructions, "response": response_parsed}
        )

    def log_agent_messages(self, messages: list) -> None:
        """Record agent message history."""
        self.data["agent_messages"] = [
            {"role": m.__class__.__name__, "content": str(m.content)[:2000]}
            for m in messages
        ]

    def log_flag(self, flag: str) -> None:
        """Record the found flag."""
        self.data["flag"] = flag

    def save(self) -> Path:
        """Write the log file and return its path."""
        path = LOG_DIR / f"run_{self.timestamp}.json"
        path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[Log] Saved to {path}")
        return path


# Shared logger instance (populated across phases)
_logger: RunLogger | None = None


# ─── Phase 1: Vision map analysis ─────────────────────────────────────────────

def analyze_map() -> tuple[int, int]:
    """Use vision model to locate the dam sector on drone.png.

    Returns:
        Tuple of (col, row) — 1-indexed sector coordinates of the dam.
    """
    image_data = base64.b64encode(IMAGE_PATH.read_bytes()).decode("utf-8")

    llm = get_llm()
    message = HumanMessage(
        content=[
            {
                "type": "text",
                "text": (
                    "This aerial photo is divided by a red grid into sectors. "
                    "Count the columns from left to right (starting at 1) and rows from top to bottom (starting at 1). "
                    "Identify the single sector that contains the DAM — it is marked by an intensely colored "
                    "bright teal/cyan/blue water area that stands out clearly from the rest of the image. "
                    "Reply ONLY in this exact JSON format, no explanation: "
                    '{"col": <column_number>, "row": <row_number>, "total_cols": <n>, "total_rows": <n>}'
                ),
            },
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image_data}"},
            },
        ]
    )

    response = llm.invoke([message])
    text = response.content.strip()
    print(f"[Vision] Raw response: {text}")

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        data = json.loads(match.group())
        col, row = int(data["col"]), int(data["row"])
        print(
            f"[Vision] Dam located at col={col}, row={row} "
            f"(grid: {data['total_cols']}x{data['total_rows']})"
        )
        if _logger:
            _logger.log_vision(text, col, row)
        return col, row

    raise ValueError(f"Could not parse vision response: {text}")


# ─── Phase 2: Drone API tools ──────────────────────────────────────────────────

@tool
def call_drone_api(instructions: list[str]) -> str:
    """Send a list of instructions to the drone API and return the response.

    Args:
        instructions: Ordered list of drone instruction strings,
            e.g. ["setDestinationObject(PWR6132PL)", "set(2,4)", "flyToLocation"].

    Returns:
        JSON response from the drone API as a string.
        If it contains a flag like {FLG:WORD}, the mission is complete.
    """
    payload = {
        "apikey": API_KEY,
        "task": "drone",
        "answer": {"instructions": instructions},
    }
    print(f"[API] Sending: {instructions}")
    response = httpx.post(f"{BASE_URL}/verify", json=payload, timeout=30)
    result = response.text
    print(f"[API] Response: {result}")
    if _logger:
        _logger.log_api_call(instructions, result)
    return result


@tool
def reset_drone() -> str:
    """Perform a hard reset of the drone to factory settings.

    Use this when the drone configuration is badly misconfigured and
    subsequent errors seem to stem from accumulated bad state.

    Returns:
        JSON response from the drone API after reset.
    """
    payload = {
        "apikey": API_KEY,
        "task": "drone",
        "answer": {"instructions": ["hardReset"]},
    }
    print("[API] Performing hardReset...")
    response = httpx.post(f"{BASE_URL}/verify", json=payload, timeout=30)
    result = response.text
    print(f"[API] Reset response: {result}")
    if _logger:
        _logger.log_api_call(["hardReset"], result)
    return result


# ─── Phase 2: ReAct agent ─────────────────────────────────────────────────────

def run_agent(dam_x: int, dam_y: int) -> None:
    """Run the ReAct LangGraph agent to complete the drone mission.

    Args:
        dam_x: Column index (1-based) of the dam sector on the map.
        dam_y: Row index (1-based) of the dam sector on the map.
    """
    llm = get_llm()
    tools = [call_drone_api, reset_drone]

    system_prompt = f"""You are an operator controlling a drone (model DRN-BMB7) via its JSON API.

MISSION:
- Official destination for the drone system: facility ID {FACILITY_ID}
- Actual bomb drop target: the DAM at grid sector col={dam_x}, row={dam_y}

REQUIRED DRONE CONFIG — all fields must be set before calling flyToLocation:
1. setDestinationObject({FACILITY_ID})   ← target facility
2. set({dam_x},{dam_y})                  ← landing sector (dam)
3. set(destroy)                          ← mission goal: destroy
4. set(return)                           ← mission goal: return to base after mission
5. set(50m)                              ← flight height
6. set(50%)                              ← engine power
7. set(engineON)                         ← start engines
8. flyToLocation                         ← launch (MUST be last)

RULES:
- Send ALL instructions above in a SINGLE call_drone_api call in the order listed.
- If the API returns an error (code < 0), read the message carefully, fix ONLY what it says is wrong, and retry immediately. Do NOT give up.
- If config seems corrupted after multiple failures, call reset_drone() first, then resend all instructions.
- The flag looks like {{FLG:WORD}} where WORD is a real English or Polish word (only letters). When you see it in any API response, report it immediately.
- Do NOT add extra instructions (no name, owner, LED, calibration) unless the API specifically requests them.
"""

    agent = create_react_agent(llm, tools)

    result = agent.invoke(
        {
            "messages": [
                SystemMessage(content=system_prompt),
                HumanMessage(
                    content=(
                        "Execute the drone mission now. "
                        "Send all required instructions in one call and launch the drone. "
                        "If you get an error, fix it and retry. "
                        "Report the flag when you receive it in the API response."
                    )
                ),
            ]
        }
    )

    print("\n=== AGENT FINAL MESSAGES ===")
    for msg in result["messages"]:
        role = msg.__class__.__name__
        content = msg.content
        if isinstance(content, list):
            content = str(content)
        print(f"[{role}]: {content[:600]}{'...' if len(str(content)) > 600 else ''}")

    if _logger:
        _logger.log_agent_messages(result["messages"])

    # Search all messages for a real flag (letters only, not template placeholder)
    all_content = " ".join(str(m.content) for m in result["messages"])
    flags = FLAG_PATTERN.findall(all_content)
    if flags:
        flag = flags[-1]
        print(f"\n{'='*50}")
        print(f"FLAG FOUND: {flag}")
        print(f"{'='*50}")
        if _logger:
            _logger.log_flag(flag)
    else:
        print("\n[!] No flag found. Check messages and run_logs for clues.")


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _logger = RunLogger()

    print("=== S2E5 Drone Mission Agent ===\n")

    print("[Phase 1] Analyzing map image to locate dam sector...")
    dam_x, dam_y = analyze_map()
    print(f"[Phase 1] Dam confirmed at sector ({dam_x}, {dam_y})\n")

    print("[Phase 2] Starting drone control agent...\n")
    run_agent(dam_x, dam_y)

    _logger.save()
