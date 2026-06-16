"""S2E4 — mailbox task solver.

Single ReAct LangGraph agent that:
1. Calls zmail help to discover all available API actions
2. Searches for emails using Gmail-like operators (from:proton.me, etc.)
3. Fetches full message bodies for candidate emails
4. Extracts three values:
     - date (YYYY-MM-DD): planned attack date
     - password: employee system password
     - confirmation_code (SEC-<32 chars>, 36 total)
5. Submits to hub.ag3nts.org/verify and reads feedback iteratively
6. Continues until the flag {FLG:...} is returned
7. Saves a full run log to s2e4/run_logs/run_<timestamp>.json
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

TASK_NAME = "mailbox"
ZMAIL_URL = "https://hub.ag3nts.org/api/zmail"
VERIFY_URL = "https://hub.ag3nts.org/verify"
MODEL_NAME = "google/gemini-3-flash-preview"

API_KEY = os.getenv("AIDEVSKEY", "")
OPENROUTER_KEY = os.getenv("OPENROUTERKEY", "")

RUN_LOGS_DIR = Path(__file__).parent / "run_logs"

if not API_KEY:
    raise RuntimeError("AIDEVSKEY not found in environment / .env")
if not OPENROUTER_KEY:
    raise RuntimeError("OPENROUTERKEY not found in environment / .env")


def utc_now() -> str:
    """Return current UTC time as a compact string."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


# ---------------------------------------------------------------------------
# Global run log (populated by tools and callback handler)
# ---------------------------------------------------------------------------

run_log: list[dict[str, Any]] = []


def _log(entry: dict[str, Any]) -> None:
    """Append entry to run_log and print a compact summary to stdout."""
    run_log.append(entry)
    entry_type = entry.get("type", "?")
    ts = entry.get("ts", "")

    if entry_type == "http_request":
        body_preview = str(entry.get("body", ""))[:120]
        print(f"[{ts}] HTTP ↑  {entry.get('url')} | {body_preview}")
    elif entry_type == "http_response":
        status = entry.get("status_code", "?")
        preview = str(entry.get("preview", ""))[:180]
        print(f"[{ts}] HTTP ↓  status={status} | {preview}")
    elif entry_type == "llm_text":
        text = str(entry.get("text", ""))[:300]
        print(f"[{ts}] LLM  ←  {text}")
    elif entry_type == "tool_start":
        print(f"[{ts}] TOOL ↑  {entry.get('tool')} | input: {str(entry.get('input', ''))[:150]}")
    elif entry_type == "tool_end":
        print(f"[{ts}] TOOL ↓  {entry.get('tool')} | output: {str(entry.get('output', ''))[:180]}")
    elif entry_type == "flag_found":
        print(f"\n{'='*60}")
        print(f"[{ts}] FLAG FOUND: {entry.get('flag')}")
        print(f"{'='*60}\n")
    elif entry_type == "run_start":
        print(f"[{ts}] RUN START | run_id={entry.get('run_id')} model={entry.get('model')}")
    elif entry_type == "error":
        print(f"[{ts}] ERROR: {entry.get('error')}")
    else:
        print(f"[{ts}] {entry_type.upper()} | {json.dumps({k: v for k, v in entry.items() if k not in ('type', 'ts')})[:200]}")


# ---------------------------------------------------------------------------
# LangChain callback handler — captures LLM reasoning and tool events
# ---------------------------------------------------------------------------


class RunLogCallback(BaseCallbackHandler):
    """Log LLM responses and tool invocation start/end for observability."""

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        try:
            # ChatModel responses use generations[0][0].message.content
            msg = response.generations[0][0]
            text = getattr(msg, "text", None) or getattr(
                getattr(msg, "message", None), "content", str(msg)
            )
        except (IndexError, AttributeError):
            text = str(response)
        _log({"type": "llm_text", "text": str(text)[:1000], "ts": utc_now()})

    def on_tool_start(
        self, serialized: dict[str, Any], input_str: str, **kwargs: Any
    ) -> None:
        _log(
            {
                "type": "tool_start",
                "tool": serialized.get("name", "unknown"),
                "input": input_str[:800],
                "ts": utc_now(),
            }
        )

    def on_tool_end(self, output: Any, **kwargs: Any) -> None:
        # tool name not available here, just log output preview
        _log({"type": "tool_end", "tool": "?", "output": str(output)[:800], "ts": utc_now()})


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------


# Minimum seconds between consecutive zmail API calls to avoid rate limiting
_RATE_LIMIT_SECONDS = 5.0
_last_call_time: float = 0.0


def _zmail_call(action_payload: dict[str, Any]) -> dict[str, Any]:
    """POST to zmail API with API key, logging full request/response cycle."""
    global _last_call_time
    elapsed = time.monotonic() - _last_call_time
    if elapsed < _RATE_LIMIT_SECONDS:
        time.sleep(_RATE_LIMIT_SECONDS - elapsed)

    full_payload = {"apikey": API_KEY, **action_payload}
    # Log without exposing the key
    log_payload = {"apikey": "***", **action_payload}
    _log({"type": "http_request", "url": ZMAIL_URL, "body": log_payload, "ts": utc_now()})

    with httpx.Client(timeout=30) as client:
        resp = client.post(ZMAIL_URL, json=full_payload)
    _last_call_time = time.monotonic()

    try:
        data: dict[str, Any] = resp.json()
    except Exception:
        data = {"raw": resp.text}

    _log(
        {
            "type": "http_response",
            "url": ZMAIL_URL,
            "status_code": resp.status_code,
            "preview": str(data)[:600],
            "ts": utc_now(),
        }
    )
    return data


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool
def zmail_help(page: int = 1) -> str:
    """Call the zmail help action to discover all available API actions and their parameters.

    Always call this first to understand what actions are available.
    Use page to paginate if there are multiple pages of help content.
    """
    result = _zmail_call({"action": "help", "page": page})
    return json.dumps(result, ensure_ascii=False)


@tool
def zmail_get_inbox(page: int = 1) -> str:
    """Browse the full inbox and list all available messages with metadata (no body content).

    Use page to paginate through results. Returns message IDs, subjects, senders, dates.
    Use zmail_get_message to fetch the full body of any message.
    """
    result = _zmail_call({"action": "getInbox", "page": page})
    return json.dumps(result, ensure_ascii=False)


@tool
def zmail_search(query: str, page: int = 1) -> str:
    """Search the mailbox using Gmail-like operators to find relevant messages (metadata only).

    Supported operators:
      - from:<address or domain>  e.g. from:proton.me
      - to:<address>
      - subject:<keyword>
      - OR, AND to combine terms

    Examples:
      - "from:proton.me"
      - "subject:password"
      - "subject:SEC-"
      - "from:proton.me subject:attack"
      - "password OR haslo OR secret"

    Returns message metadata (IDs, subjects, senders). No body content.
    Always follow up with zmail_get_message to read the full body.
    """
    result = _zmail_call({"action": "search", "query": query, "page": page})
    return json.dumps(result, ensure_ascii=False)


@tool
def zmail_get_thread(thread_id: int) -> str:
    """List all rowIDs and messageIDs for every message in a thread (no body content).

    Use this when you have a threadID from inbox or search results to discover all
    message IDs in that thread. Then fetch each message with zmail_get_message.
    """
    result = _zmail_call({"action": "getThread", "threadID": thread_id})
    return json.dumps(result, ensure_ascii=False)


@tool
def zmail_get_message(message_id: str) -> str:
    """Fetch the FULL content and body of a specific message by its rowID or messageID.

    Pass either:
      - a numeric rowID (as a string, e.g. "86") — simpler, always works
      - a 32-char hex messageID hash

    The API action is 'getMessages' (plural) with parameter 'ids'.
    Critical: always call this before extracting any data value from a message.
    Never guess content from the subject line alone.
    The message body may contain passwords, dates, confirmation codes, or links.
    """
    result = _zmail_call({"action": "getMessages", "ids": message_id})
    return json.dumps(result, ensure_ascii=False)


@tool
def hub_verify(password: str, date: str, confirmation_code: str) -> str:
    """Submit the three extracted values to the verification hub and get feedback.

    Args:
        password: The employee system password found in the mailbox.
        date: The planned attack date in YYYY-MM-DD format.
        confirmation_code: Security ticket code in format SEC-<32 alphanumeric chars>
                           (total exactly 36 characters including the 'SEC-' prefix).

    Returns the hub response. If all three values are correct, the response contains
    a flag in format {FLG:...}. Otherwise the feedback tells you which fields are wrong.
    Use the feedback to refine your search and try again.
    """
    payload: dict[str, Any] = {
        "apikey": API_KEY,
        "task": TASK_NAME,
        "answer": {
            "password": password,
            "date": date,
            "confirmation_code": confirmation_code,
        },
    }
    log_payload = {**payload, "apikey": "***"}
    _log({"type": "http_request", "url": VERIFY_URL, "body": log_payload, "ts": utc_now()})

    with httpx.Client(timeout=30) as client:
        resp = client.post(VERIFY_URL, json=payload)

    try:
        data = resp.json()
    except Exception:
        data = {"raw": resp.text}

    _log(
        {
            "type": "http_response",
            "url": VERIFY_URL,
            "status_code": resp.status_code,
            "preview": str(data)[:600],
            "ts": utc_now(),
        }
    )

    result_str = json.dumps(data, ensure_ascii=False)
    flag_match = re.search(r"\{FLG:[^}]+\}", result_str)
    if flag_match:
        _log({"type": "flag_found", "flag": flag_match.group(), "ts": utc_now()})

    return result_str


# ---------------------------------------------------------------------------
# Agent prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a security investigator with access to a captured email inbox.
Your mission: extract exactly THREE pieces of intelligence from the mailbox.

TARGET VALUES:
1. date       — The date (format YYYY-MM-DD) when the security department plans to attack our power plant.
2. password   — The employee system password that was sent or stored in this mailbox.
3. confirmation_code — A security ticket confirmation code in format: SEC-<32 alphanumeric characters>
                       (total exactly 36 characters including the 'SEC-' prefix).

KNOWN INTELLIGENCE:
- Wiktor (a whistleblower from the resistance) sent an email FROM a proton.me address.
- The mailbox API supports Gmail-like search operators: from:, to:, subject:, OR, AND.
- The mailbox is LIVE — new emails may arrive during your search. If something is missing, retry.

SEARCH STRATEGY:
1. Call zmail_help first to learn the exact API actions and parameters.
2. Search "from:proton.me" to find Wiktor's email — read its full body with zmail_get_message.
3. Search "SEC-" to find the security ticket thread.
   - Use zmail_get_thread(threadID) to list ALL messages in that thread.
   - Then call zmail_get_message on each rowID/messageID to read full bodies.
4. Browse inbox pages with zmail_get_inbox to catch any remaining messages.
5. For EVERY promising message: call zmail_get_message(rowID) — use the numeric rowID
   from search/inbox results (e.g. "86"), it is the most reliable identifier.
   NEVER guess content from subject lines or snippets.
6. Once you have candidates for all three values, call hub_verify.
7. Use the feedback to fix wrong values and keep searching.
8. Repeat until hub_verify returns a response containing {FLG:...}.

TOOL USAGE NOTES:
- zmail_get_message: pass the numeric rowID as a string (e.g. "86") — this is most reliable.
- zmail_get_thread: pass the numeric threadID integer to list all messages in a thread.
- The search operator searches subjects and snippets only, NOT message bodies.

IMPORTANT RULES:
- confirmation_code must be EXACTLY 36 characters: SEC- (4 chars) + 32 alphanumeric chars.
- date must be exactly YYYY-MM-DD (e.g. 2026-03-15).
- When you find the flag {FLG:...}, state it clearly and stop.
- Be systematic: track which message IDs you have already read.
"""

TASK_PROMPT = (
    "Search the zmail mailbox and find the three intelligence values:\n"
    "  1. Attack date (YYYY-MM-DD)\n"
    "  2. Employee system password\n"
    "  3. Security confirmation code (SEC-... format, exactly 36 chars)\n\n"
    "Start with zmail_help to learn the API, then search systematically.\n"
    "Keep verifying with hub_verify until you receive a flag {FLG:...}."
)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the mailbox agent and save the run log."""
    RUN_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    run_id = utc_now()
    run_log.clear()

    _log(
        {
            "type": "run_start",
            "run_id": run_id,
            "model": MODEL_NAME,
            "task": TASK_NAME,
            "ts": run_id,
        }
    )

    llm = ChatOpenAI(
        model=MODEL_NAME,
        openai_api_key=OPENROUTER_KEY,
        openai_api_base="https://openrouter.ai/api/v1",
        temperature=0,
    )

    tools = [zmail_help, zmail_get_inbox, zmail_search, zmail_get_thread, zmail_get_message, hub_verify]

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=SYSTEM_PROMPT,
    )

    callback = RunLogCallback()
    config: dict[str, Any] = {"callbacks": [callback], "recursion_limit": 150}

    print(f"\n{'='*60}")
    print(f"Mailbox agent starting — run {run_id}")
    print(f"Model: {MODEL_NAME}  |  Task: {TASK_NAME}")
    print(f"{'='*60}\n")

    try:
        result = agent.invoke(
            {"messages": [HumanMessage(content=TASK_PROMPT)]},
            config=config,
        )
        final_message = result["messages"][-1].content
        _log(
            {
                "type": "agent_done",
                "final_message": str(final_message)[:2000],
                "ts": utc_now(),
            }
        )
        print(f"\n{'='*60}")
        print("AGENT FINAL MESSAGE:")
        print(final_message)
        print(f"{'='*60}\n")

    except Exception as exc:
        _log({"type": "error", "error": str(exc), "ts": utc_now()})
        print(f"[ERROR] {exc}")
        raise
    finally:
        log_path = RUN_LOGS_DIR / f"run_{run_id}.json"
        log_path.write_text(
            json.dumps(run_log, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"Run log saved → {log_path}")


if __name__ == "__main__":
    main()
