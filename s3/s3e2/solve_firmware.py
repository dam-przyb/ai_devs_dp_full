"""LangGraph ReAct agent — AI_Devs4 S3E2 firmware task.

Strategy:
1. Call `help` to learn available shell commands.
2. Explore /opt/firmware/cooler/ — inspect the binary and its settings.ini.
3. Search the filesystem for the password required by cooler.bin.
4. Patch settings.ini if needed so the binary runs correctly.
5. Execute cooler.bin with correct arguments and capture the ECCS-... code.
6. Submit the code to /verify.
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

load_dotenv()

API_KEY: str = os.getenv("AIDEVSKEY", "")
OPENROUTER_KEY: str = os.getenv("OPENROUTERKEY", "")
SHELL_URL = "https://hub.ag3nts.org/api/shell"
VERIFY_URL = "https://hub.ag3nts.org/verify"
MODEL = "anthropic/claude-haiku-4.5"
LOG_DIR = Path(__file__).parent / "run_logs"
LOG_DIR.mkdir(exist_ok=True)


# ─── LLM ──────────────────────────────────────────────────────────────────────

def get_llm() -> ChatOpenAI:
    """Create a ChatOpenAI instance via OpenRouter."""
    return ChatOpenAI(
        model=MODEL,
        openai_api_key=OPENROUTER_KEY,
        openai_api_base="https://openrouter.ai/api/v1",
        temperature=0,
    )


# ─── Tools ────────────────────────────────────────────────────────────────────

@tool
def shell_cmd(cmd: str) -> str:
    """Execute a shell command on the remote virtual machine.

    Args:
        cmd: The shell command to run (e.g. 'ls /opt/firmware/cooler').

    Returns:
        The output from the shell, or an error description.
    """
    payload = {"apikey": API_KEY, "cmd": cmd}
    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = httpx.post(
                SHELL_URL,
                json=payload,
                timeout=30,
            )
            if response.status_code == 200:
                data = response.json()
                # Always return the full raw JSON so the agent sees every field.
                if isinstance(data, dict):
                    msg = str(data.get("message", ""))
                    if "ban" in msg.lower():
                        ban_secs = _extract_ban_seconds(msg)
                        return (
                            f"ACCESS BANNED for {ban_secs}s due to security violation. "
                            f"Full response: {json.dumps(data)}"
                        )
                    result = json.dumps(data)
                    # Truncate huge outputs (e.g. binary files) to avoid context overflow
                    if len(result) > 4000:
                        result = result[:4000] + "\n... [TRUNCATED — output too large]"
                    return result
                return str(data)[:4000]
            elif response.status_code in (429, 503):
                wait = 5 * (attempt + 1)
                time.sleep(wait)
                continue
            elif response.status_code == 403:
                # Temporary ban — extract seconds and wait automatically
                try:
                    ban_data = response.json()
                    ban_info = ban_data.get("ban", {})
                    seconds_left = int(ban_info.get("seconds_left", 30))
                    reason = ban_info.get("reason", "banned")
                    if attempt < max_retries - 1 and "banned" in ban_data.get("message", "").lower():
                        print(f"[SHELL] Banned: {reason}. Auto-waiting {seconds_left + 2}s...")
                        time.sleep(seconds_left + 2)
                        continue
                except Exception:  # noqa: BLE001
                    pass
                return f"HTTP 403: {response.text}"
            else:
                return f"HTTP error {response.status_code}: {response.text}"
        except httpx.TimeoutException:
            if attempt < max_retries - 1:
                time.sleep(3)
                continue
            return "Request timed out after all retries."
        except Exception as exc:  # noqa: BLE001
            return f"Request failed: {exc}"
    return "All retries exhausted. Shell API unavailable."


def _extract_ban_seconds(message: str) -> str:
    """Try to pull a numeric duration from a ban message."""
    import re
    match = re.search(r"(\d+)", message)
    return match.group(1) if match else "unknown"


@tool
def submit_answer(code: str) -> str:
    """Submit the ECCS code to the AI Devs verification endpoint.

    Args:
        code: The ECCS-... code obtained from running cooler.bin.

    Returns:
        The response from the verification server.
    """
    payload = {
        "apikey": API_KEY,
        "task": "firmware",
        "answer": {"confirmation": code},
    }
    try:
        response = httpx.post(VERIFY_URL, json=payload, timeout=30)
        return response.text
    except Exception as exc:  # noqa: BLE001
        return f"Submission failed: {exc}"


# ─── Agent ────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a careful Linux sysadmin on a restricted virtual machine via a shell API.
Your goal: run /opt/firmware/cooler/cooler.bin to get a secret ECCS code, then submit it to /verify.

═══ SECURITY RULES (breaking these = ban) ═══
- DO NOT access /etc, /root, /proc/ directories.
- DO NOT read .env files.
- DO NOT cat .bin (binary) files — they are enormous, will crash the context.
- DO NOT access anything listed in .gitignore.
- ALWAYS read .gitignore before touching ANY other file in that directory.
- You are a regular (non-root) user.

═══ SHELL API MECHANICS ═══
- shell_cmd returns FULL JSON. Parse it: real data is in the "data" field.
- Success: {"code": NNN, "data": "...", "message": "..."}
- Error: HTTP 4xx with {"code": -NNN, "message": "..."} — shown as "HTTP NNN: ..."
- Ban (HTTP 403): the tool auto-waits for the ban to expire then retries automatically.
- AVAILABLE COMMANDS: ls, cat, pwd, cd, find, history, whoami, editline, rm, reboot, uptime, date, help
- editline syntax: editline <filepath> <line_number> <new_content>
  (replaces the entire line at that line number with new_content)

═══ MANDATORY WORKFLOW — FOLLOW EXACTLY IN ORDER ═══

PHASE 1 — READ BEFORE TOUCHING:
  Step 1: cat /opt/firmware/cooler/.gitignore
          → note which files are forbidden
  Step 2: cat /opt/firmware/cooler/settings.ini
          → read the ACTUAL content, note every line and its line number
  Step 3: Analyse what is wrong in settings.ini (do NOT guess — use what you read)

PHASE 2 — FIX settings.ini:
  Step 4: For each line that needs changing, use:
          editline /opt/firmware/cooler/settings.ini <N> <correct_content>
          After EACH editline call, verify with: cat /opt/firmware/cooler/settings.ini
          Only proceed to the next edit after confirming the previous one is correct.

PHASE 3 — FIND PASSWORD:
  Step 5: Search for password files:
          find /home -type f
          find /tmp -type f
          find /opt -type f -name "*.txt"
          find /var -type f -name "*.txt"
          (Do NOT access /etc, /root, /proc)

PHASE 4 — REMOVE LOCK & RUN:
  Step 6: rm /opt/firmware/cooler/cooler-is-blocked.lock  (if it exists)
  Step 7: Run the binary. The shell API accepts the binary path as a command:
          /opt/firmware/cooler/cooler.bin
          If it requires a password: /opt/firmware/cooler/cooler.bin --password <PASSWORD>
          Try variations if needed.

PHASE 5 — SUBMIT:
  Step 8: When output contains ECCS-..., call submit_answer(code) with the ECCS code.
          The /verify response will contain {FLG:WORD} — report it as: FLAG FOUND: {FLG:...}

═══ CRITICAL RULES ═══
- NEVER guess settings.ini content or line numbers — always read first.
- After each editline, ALWAYS verify with cat before making the next edit.
- NEVER edit more than one line per shell_cmd call.
- NEVER cat cooler.bin.
"""


def run_agent() -> None:
    """Entry point: build and run the ReAct agent."""
    llm = get_llm()
    tools = [shell_cmd, submit_answer]
    agent = create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)

    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting firmware agent...")
    print(f"Model: {MODEL}")
    print("-" * 60)

    events = []
    final_output = None

    for event in agent.stream(
        {"messages": [{"role": "user", "content": "Please complete the firmware task as described. Your final goal is to find and report the flag in format {FLG:WORD} which will come from the /verify response after submitting the ECCS code."}]},
        stream_mode="values",
    ):
        messages = event.get("messages", [])
        if messages:
            last = messages[-1]
            role = getattr(last, "type", "unknown")
            content = getattr(last, "content", "")
            if role == "ai":
                print(f"\n[AI]: {content}")
            elif role == "tool":
                name = getattr(last, "name", "tool")
                print(f"\n[TOOL:{name}]: {content[:500]}{'...' if len(str(content)) > 500 else ''}")
            events.append({"role": role, "content": str(content)})
            final_output = str(content)

    # Save run log
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = LOG_DIR / f"run_{ts}.json"
    log_path.write_text(
        json.dumps({"timestamp": ts, "model": MODEL, "events": events}, indent=2),
        encoding="utf-8",
    )
    print(f"\n[LOG] Saved to {log_path}")

    if final_output:
        print(f"\n[FINAL]: {final_output}")


if __name__ == "__main__":
    run_agent()
