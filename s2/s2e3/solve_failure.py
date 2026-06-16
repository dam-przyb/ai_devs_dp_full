"""
S2E3 — failure task solver.

LangGraph agent that:
1. Pre-filters the raw failure.log (rule-based: WARN/ERRO/CRIT only)
2. Asks gpt-5-mini to compress entries to <=1500 tokens
3. Counts tokens with tiktoken
4. Submits to hub.ag3nts.org/verify and reads technician feedback
5. Iterates (max 15 rounds) adjusting based on feedback until the flag is found
6. Saves a full run log to s2e3/run_logs/run_<timestamp>.json
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

import httpx
import tiktoken
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

load_dotenv()

TASK_NAME = "failure"
VERIFY_URL = "https://hub.ag3nts.org/verify"
MODEL_NAME = "openai/gpt-5-mini"
MAX_ITERATIONS = 15
TOKEN_LIMIT = 1500
# Conservative: 1 token ≈ 4 chars, but tiktoken is exact so we use it directly.
LOG_FILE = Path(__file__).parent / "failure.log"
RUN_LOGS_DIR = Path(__file__).parent / "run_logs"

API_KEY = os.getenv("AIDEVSKEY", "")
OPENROUTER_KEY = os.getenv("OPENROUTERKEY", "")

if not API_KEY:
    raise RuntimeError("AIDEVSKEY not found in environment / .env")
if not OPENROUTER_KEY:
    raise RuntimeError("OPENROUTERKEY not found in environment / .env")


def _make_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=MODEL_NAME,
        openai_api_key=OPENROUTER_KEY,
        openai_api_base="https://openrouter.ai/api/v1",
        temperature=0,
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _count_tokens(text: str) -> int:
    """Count tokens using cl100k_base (compatible with GPT-4/gpt-5-mini)."""
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class FailureState(TypedDict, total=False):
    run_id: str
    pre_filtered_lines: list[str]
    compressed_log: str
    token_count: int
    iteration: int
    compress_attempts: int  # attempts within a single iteration (shorten loop)
    last_feedback: str
    flag: str | None
    run_log: list[dict[str, Any]]
    status: str  # "running" | "flag_found" | "max_iterations"


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def node_pre_filter(state: FailureState) -> FailureState:
    """Read failure.log and keep only WARN / ERRO / CRIT lines."""
    print("[pre_filter] Reading log file…")
    raw_lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
    filtered = [ln for ln in raw_lines if re.search(r"\[(WARN|ERRO|CRIT)\]", ln)]
    print(f"[pre_filter] {len(raw_lines)} total lines → {len(filtered)} WARN/ERRO/CRIT kept")
    return {
        **state,
        "pre_filtered_lines": filtered,
        "iteration": 0,
        "compress_attempts": 0,
        "run_log": [],
        "flag": None,
        "status": "running",
        "last_feedback": "",
        "compressed_log": "",
    }


def node_llm_compress(state: FailureState) -> FailureState:
    """Use LLM to compress the pre-filtered lines to <=1500 tokens.

    Three cases:
    1. First compression (compress_attempts == 0, no current compressed log):
       compress the full pre-filtered source.
    2. Token-limit re-compression (compress_attempts > 0, token still over limit):
       send the current too-long output and ask to shorten it further.
    3. Feedback-driven re-compression (iteration > 0, after a submission):
       send feedback + current compressed + source for reference.
    """
    iteration = state.get("iteration", 0)
    compress_attempts = state.get("compress_attempts", 0)
    feedback = state.get("last_feedback", "")
    pre_filtered = state.get("pre_filtered_lines", [])
    current_compressed = state.get("compressed_log", "")

    print(
        f"[llm_compress] Iteration {iteration}, compress_attempt {compress_attempts} "
        f"— asking {MODEL_NAME} to compress…"
    )

    llm = _make_llm()

    if iteration > 0 and feedback:
        # Case 3: post-submission feedback adjustment
        user_content = f"""You previously compressed the power plant failure logs.
The technicians reviewed your compressed log and provided this feedback:

FEEDBACK:
{feedback}

Your current compressed log (which may be missing or unclear on some components):
{current_compressed}

Full WARN/ERRO/CRIT source lines (for reference, to find missing component data):
{chr(10).join(pre_filtered)}

Task:
- Update the compressed log to address the feedback (add missing component entries, clarify unclear ones).
- Keep only relevant failure-analysis entries, one event per line.
- Maintain strict chronological order (ascending timestamp).
- Stay strictly under {TOKEN_LIMIT} tokens total.
- Output ONLY the updated log lines, no commentary.
"""
    elif compress_attempts > 0 and current_compressed:
        # Case 2: previous attempt was too long — shorten the existing output
        target = int(TOKEN_LIMIT * 0.85)  # aim for 85% of limit for safety
        user_content = f"""The following compressed power plant failure log is too long ({state.get('token_count', '?')} tokens, limit is {TOKEN_LIMIT}).

CURRENT LOG (too long):
{current_compressed}

Task:
- Shorten the log further to fit under {target} tokens.
- Merge similar consecutive events, drop the least informative entries.
- Preserve critical events (CRIT severity) and all unique component IDs.
- Keep strict chronological order (ascending timestamp).
- One event per line, no commentary.
- Target: under {target} tokens.
"""
    else:
        # Case 1: initial compression from raw pre-filtered source
        source_text = "\n".join(pre_filtered)
        user_content = f"""Below are the WARN/ERRO/CRIT log entries from a power plant failure event.

Your task:
- Keep ONLY entries relevant to the physical plant components and failure analysis:
  power supply, cooling system, water pumps, water tanks, steam turbines, firmware/software, reactor safety systems.
- Discard noise (routine monitoring confirmations, repeated identical lines).
- Paraphrase / shorten each entry while preserving: timestamp (YYYY-MM-DD HH:MM), severity [WARN/ERRO/CRIT], component ID, and a brief description.
- Output one event per line, no extra commentary.
- Output lines in strict chronological order (ascending timestamp).
- Target well under {TOKEN_LIMIT} tokens total (aim for ~1200).

LOG ENTRIES:
{source_text}
"""

    messages = [
        SystemMessage(
            content=(
                "You are a nuclear power plant log analyst. "
                "You produce concise, accurate compressed log summaries for failure analysis. "
                "Output only the log lines — no headers, no explanations."
            )
        ),
        HumanMessage(content=user_content),
    ]

    response = llm.invoke(messages)
    compressed_raw = response.content.strip()

    # --- Post-process: sort lines chronologically by their timestamp ---
    _ts_pat = re.compile(r"(\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2})")

    def _line_sort_key(line: str) -> str:
        m = _ts_pat.search(line)
        return m.group(1) if m else ""

    lines = [ln for ln in compressed_raw.splitlines() if ln.strip()]
    lines.sort(key=_line_sort_key)
    compressed = "\n".join(lines)
    # ---

    token_count = _count_tokens(compressed)
    print(f"[llm_compress] Compressed to {token_count} tokens ({len(compressed.splitlines())} lines)")

    return {
        **state,
        "compressed_log": compressed,
        "token_count": token_count,
        "compress_attempts": compress_attempts + 1,
    }


def node_token_check(state: FailureState) -> FailureState:
    """Verify token count; update state. Routing happens in conditional edge."""
    token_count = _count_tokens(state.get("compressed_log", ""))
    print(f"[token_check] Token count: {token_count} / {TOKEN_LIMIT}")
    return {**state, "token_count": token_count}


def node_submit(state: FailureState) -> FailureState:
    """POST the compressed log to the verification endpoint."""
    iteration = state.get("iteration", 0) + 1
    compressed_log = state.get("compressed_log", "")
    run_log = list(state.get("run_log", []))

    print(f"[submit] Iteration {iteration} — posting to {VERIFY_URL}…")

    payload = {
        "apikey": API_KEY,
        "task": TASK_NAME,
        "answer": {"logs": compressed_log},
    }

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(VERIFY_URL, json=payload)
        resp_json = resp.json()
    except Exception as exc:
        resp_json = {"error": str(exc)}

    print(f"[submit] Response: {json.dumps(resp_json, ensure_ascii=False)[:300]}")

    # Extract flag if present
    flag = None
    resp_text = json.dumps(resp_json)
    flag_match = re.search(r"\{FLG:[^}]+\}", resp_text)
    if flag_match:
        flag = flag_match.group(0)
        print(f"[submit] FLAG FOUND: {flag}")

    # Extract feedback message for next iteration
    feedback = (
        resp_json.get("message")
        or resp_json.get("hint")
        or resp_json.get("error")
        or resp_text
    )

    run_log.append({
        "iteration": iteration,
        "token_count": state.get("token_count"),
        "compressed_log_lines": len(compressed_log.splitlines()),
        "api_response": resp_json,
        "flag": flag,
    })

    new_status = "flag_found" if flag else ("max_iterations" if iteration >= MAX_ITERATIONS else "running")

    return {
        **state,
        "iteration": iteration,
        "compress_attempts": 0,  # reset for next submission cycle
        "last_feedback": feedback if isinstance(feedback, str) else json.dumps(feedback),
        "flag": flag,
        "run_log": run_log,
        "status": new_status,
    }


def node_save_log(state: FailureState) -> FailureState:
    """Save the full run log to a JSON file."""
    RUN_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    run_id = state.get("run_id", _utc_now())
    out_path = RUN_LOGS_DIR / f"run_{run_id}.json"

    payload = {
        "run_id": run_id,
        "status": state.get("status"),
        "flag": state.get("flag"),
        "iterations": state.get("iteration"),
        "final_token_count": state.get("token_count"),
        "final_compressed_log": state.get("compressed_log"),
        "run_log": state.get("run_log", []),
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[save_log] Run log saved → {out_path}")
    return state


# ---------------------------------------------------------------------------
# Conditional routing
# ---------------------------------------------------------------------------


def route_after_token_check(state: FailureState) -> str:
    """If within limit → submit; else → compress again."""
    if state.get("token_count", 9999) <= TOKEN_LIMIT:
        return "submit"
    print(f"[route] Token count {state['token_count']} exceeds {TOKEN_LIMIT}, re-compressing…")
    return "llm_compress"


def route_after_submit(state: FailureState) -> str:
    """Route to END (save log) if done, else back to adjust."""
    status = state.get("status", "running")
    if status in ("flag_found", "max_iterations"):
        return "save_log"
    return "llm_compress"


# ---------------------------------------------------------------------------
# Build graph
# ---------------------------------------------------------------------------


def build_graph() -> Any:
    g = StateGraph(FailureState)

    g.add_node("pre_filter", node_pre_filter)
    g.add_node("llm_compress", node_llm_compress)
    g.add_node("token_check", node_token_check)
    g.add_node("submit", node_submit)
    g.add_node("save_log", node_save_log)

    g.set_entry_point("pre_filter")
    g.add_edge("pre_filter", "llm_compress")
    g.add_edge("llm_compress", "token_check")

    g.add_conditional_edges(
        "token_check",
        route_after_token_check,
        {"submit": "submit", "llm_compress": "llm_compress"},
    )

    g.add_conditional_edges(
        "submit",
        route_after_submit,
        {"llm_compress": "llm_compress", "save_log": "save_log"},
    )

    g.add_edge("save_log", END)

    return g.compile()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    run_id = _utc_now()
    print(f"=== failure solver | run {run_id} | model {MODEL_NAME} ===")
    print(f"    API key: {API_KEY[:8]}…")
    print(f"    Log file: {LOG_FILE}")
    print(f"    Max iterations: {MAX_ITERATIONS} | Token limit: {TOKEN_LIMIT}")
    print()

    graph = build_graph()
    initial_state: FailureState = {"run_id": run_id}
    final_state = graph.invoke(initial_state)

    print()
    if final_state.get("flag"):
        print(f"SUCCESS! Flag: {final_state['flag']}")
    elif final_state.get("status") == "max_iterations":
        print(f"Reached max iterations ({MAX_ITERATIONS}). Re-run the script to continue.")
    else:
        print("Finished with unknown status. Check run log for details.")


if __name__ == "__main__":
    main()
