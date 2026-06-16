from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

import httpx
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from electricity_helper import (
    build_edge_map,
    count_remaining_mismatches,
    decide_rotations,
    decisions_to_commands,
    decisions_to_dicts,
    detect_grid,
    extract_cell_masks,
    extract_flag,
    image_to_gray_array,
    load_recent_history,
    mask_secret,
    save_json,
    utc_now,
)

TASK_NAME = "electricity"
VERIFY_URL = "https://hub.ag3nts.org/verify"
IMAGE_TEMPLATE = "https://hub.ag3nts.org/data/{api_key}/electricity.png"
SOLVED_URL = "https://hub.ag3nts.org/i/solved_electricity.png"
MODEL_NAME = "google/gemini-3.5-flash"


class SolverState(TypedDict, total=False):
    run_id: str
    started_at: str
    base_dir: str
    logs_dir: str
    artifacts_dir: str
    apikey_masked: str
    model_name: str
    history: list[dict[str, Any]]
    current_png_path: str
    target_png_path: str
    current_grid: dict[str, Any]
    target_grid: dict[str, Any]
    current_edge_map: list[list[str]]
    target_edge_map: list[list[str]]
    rotation_decisions: list[dict[str, Any]]
    move_commands: list[str]
    api_events: list[dict[str, Any]]
    executed_moves: int
    final_verify_response: dict[str, Any]
    status: str
    flag: str | None
    remaining_mismatches: list[str]
    llm_audit: str
    error: str | None


def fail_state(state: SolverState, error_message: str) -> SolverState:
    """Mark state as failed while preserving partial progress."""
    state["status"] = "failed"
    state["error"] = error_message
    return state


def node_load_context(state: SolverState) -> SolverState:
    """Load environment, initialize run metadata, and read recent history."""
    base_dir = Path(__file__).resolve().parent
    logs_dir = base_dir / "run_logs"

    load_dotenv(base_dir.parent.parent / ".env")
    load_dotenv(base_dir.parent / ".env")
    load_dotenv(base_dir / ".env")

    api_key = os.getenv("AIDEVSKEY", "").strip()
    openrouter_key = os.getenv("OPENROUTERKEY", "").strip()

    if not api_key:
        return fail_state(state, "Missing AIDEVSKEY in environment")
    if not openrouter_key:
        return fail_state(state, "Missing OPENROUTERKEY in environment")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    artifacts_dir = logs_dir / f"artifacts_{run_id}"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    state["run_id"] = run_id
    state["started_at"] = utc_now()
    state["base_dir"] = str(base_dir)
    state["logs_dir"] = str(logs_dir)
    state["artifacts_dir"] = str(artifacts_dir)
    state["apikey_masked"] = mask_secret(api_key)
    state["model_name"] = MODEL_NAME
    state["history"] = load_recent_history(log_dir=logs_dir, limit=5)
    state["status"] = "running"
    state["error"] = None
    state["api_events"] = []
    state["executed_moves"] = 0
    state["flag"] = None

    return state



def node_reset_and_fetch(state: SolverState) -> SolverState:
    """Reset the board and fetch current plus solved reference images."""
    if state.get("status") == "failed":
        return state

    api_key = os.getenv("AIDEVSKEY", "").strip()
    if not api_key:
        return fail_state(state, "AIDEVSKEY missing in reset step")

    current_url = IMAGE_TEMPLATE.format(api_key=api_key) + "?reset=1"
    artifacts_dir = Path(state["artifacts_dir"])
    current_path = artifacts_dir / "current_reset.png"
    target_path = artifacts_dir / "target_solved.png"

    try:
        with httpx.Client(timeout=30.0) as client:
            current_response = client.get(current_url)
            current_response.raise_for_status()
            current_path.write_bytes(current_response.content)

            target_response = client.get(SOLVED_URL)
            target_response.raise_for_status()
            target_path.write_bytes(target_response.content)
    except Exception as exc:
        return fail_state(state, f"Image fetch failed: {exc}")

    state["current_png_path"] = str(current_path)
    state["target_png_path"] = str(target_path)
    return state



def node_parse_boards(state: SolverState) -> SolverState:
    """Parse board images into tile masks and symbolic edge maps."""
    if state.get("status") == "failed":
        return state

    try:
        current_bytes = Path(state["current_png_path"]).read_bytes()
        target_bytes = Path(state["target_png_path"]).read_bytes()

        current_gray = image_to_gray_array(current_bytes)
        target_gray = image_to_gray_array(target_bytes)

        current_grid = detect_grid(current_gray)
        target_grid = detect_grid(target_gray)

        current_cells = extract_cell_masks(current_gray, current_grid)
        target_cells = extract_cell_masks(target_gray, target_grid)

        state["current_grid"] = {
            "row_lines": current_grid.row_lines,
            "col_lines": current_grid.col_lines,
        }
        state["target_grid"] = {
            "row_lines": target_grid.row_lines,
            "col_lines": target_grid.col_lines,
        }

        state["current_edge_map"] = build_edge_map(current_cells)
        state["target_edge_map"] = build_edge_map(target_cells)

        decisions = decide_rotations(current_cells, target_cells)
        state["rotation_decisions"] = decisions_to_dicts(decisions)
        state["move_commands"] = decisions_to_commands(decisions)
    except Exception as exc:
        return fail_state(state, f"Board parsing failed: {exc}")

    return state



def node_llm_audit(state: SolverState) -> SolverState:
    """Use OpenRouter LLM to audit parse quality and confidence."""
    if state.get("status") == "failed":
        return state

    openrouter_key = os.getenv("OPENROUTERKEY", "").strip()
    if not openrouter_key:
        return fail_state(state, "OPENROUTERKEY missing in LLM audit step")

    llm = ChatOpenAI(
        model=MODEL_NAME,
        openai_api_key=openrouter_key,
        openai_api_base="https://openrouter.ai/api/v1",
        temperature=0,
    )

    payload = {
        "history": state.get("history", []),
        "current_edge_map": state.get("current_edge_map", []),
        "target_edge_map": state.get("target_edge_map", []),
        "rotation_decisions": state.get("rotation_decisions", []),
        "moves_count": len(state.get("move_commands", [])),
    }

    system_text = (
        "You audit a deterministic puzzle-rotation plan. "
        "Respond with concise diagnostics in JSON with keys: risk_level, concerns, recommendation. "
        "Do not propose random moves. Focus on confidence and potential parser ambiguity."
    )

    try:
        response = llm.invoke(
            [
                SystemMessage(content=system_text),
                HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
            ]
        )
        state["llm_audit"] = response.content if isinstance(response.content, str) else str(response.content)
    except Exception as exc:
        state["llm_audit"] = f"LLM audit skipped due to error: {exc}"

    return state



def _post_rotate(api_key: str, coordinate: str) -> dict[str, Any]:
    payload = {
        "apikey": api_key,
        "task": TASK_NAME,
        "answer": {"rotate": coordinate},
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.post(VERIFY_URL, json=payload)
        response.raise_for_status()
        try:
            return response.json()
        except ValueError:
            return {"raw": response.text}


def node_execute_moves(state: SolverState) -> SolverState:
    """Execute computed rotation commands via verify API."""
    if state.get("status") == "failed":
        return state

    api_key = os.getenv("AIDEVSKEY", "").strip()
    if not api_key:
        return fail_state(state, "AIDEVSKEY missing in execute step")

    events: list[dict[str, Any]] = []

    try:
        for index, coordinate in enumerate(state.get("move_commands", []), start=1):
            result = _post_rotate(api_key=api_key, coordinate=coordinate)
            event = {
                "index": index,
                "rotate": coordinate,
                "response": result,
                "flag_detected": extract_flag(result),
            }
            events.append(event)

            if event["flag_detected"]:
                state["flag"] = event["flag_detected"]
                break
    except Exception as exc:
        state["api_events"] = events
        state["executed_moves"] = len(events)
        return fail_state(state, f"Move execution failed: {exc}")

    state["api_events"] = events
    state["executed_moves"] = len(events)

    if state.get("flag"):
        state["status"] = "solved"

    return state



def node_verify_final(state: SolverState) -> SolverState:
    """Fetch final board and compute remaining mismatches."""
    if state.get("status") == "failed":
        return state

    if state.get("status") == "solved":
        state["remaining_mismatches"] = []
        return state

    api_key = os.getenv("AIDEVSKEY", "").strip()
    if not api_key:
        return fail_state(state, "AIDEVSKEY missing in verify step")

    artifacts_dir = Path(state["artifacts_dir"])
    final_path = artifacts_dir / "current_final.png"

    try:
        with httpx.Client(timeout=30.0) as client:
            final_response = client.get(IMAGE_TEMPLATE.format(api_key=api_key))
            final_response.raise_for_status()
            final_path.write_bytes(final_response.content)

        final_gray = image_to_gray_array(final_path.read_bytes())
        target_gray = image_to_gray_array(Path(state["target_png_path"]).read_bytes())

        final_grid = detect_grid(final_gray)
        target_grid = detect_grid(target_gray)

        final_cells = extract_cell_masks(final_gray, final_grid)
        target_cells = extract_cell_masks(target_gray, target_grid)

        remaining = count_remaining_mismatches(final_cells, target_cells)
        state["remaining_mismatches"] = remaining
        state["status"] = "solved" if not remaining else "failed"
        if remaining:
            state["error"] = f"Board mismatch after execution: {remaining}"
    except Exception as exc:
        return fail_state(state, f"Final verification failed: {exc}")

    return state



def node_finalize_log(state: SolverState) -> SolverState:
    """Write full run log and a lightweight latest summary file."""
    logs_dir = Path(state.get("logs_dir") or (Path(__file__).resolve().parent / "run_logs"))
    run_id = state.get("run_id", datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))

    report = {
        "task": TASK_NAME,
        "run_id": run_id,
        "timestamp": utc_now(),
        "status": state.get("status", "failed"),
        "error": state.get("error"),
        "flag": state.get("flag"),
        "model": state.get("model_name"),
        "apikey_masked": state.get("apikey_masked"),
        "moves_planned": len(state.get("move_commands", [])),
        "moves_executed": state.get("executed_moves", 0),
        "remaining_mismatches": state.get("remaining_mismatches", []),
        "history_summary": state.get("history", []),
        "current_grid": state.get("current_grid"),
        "target_grid": state.get("target_grid"),
        "current_edge_map": state.get("current_edge_map"),
        "target_edge_map": state.get("target_edge_map"),
        "rotation_decisions": state.get("rotation_decisions", []),
        "move_commands": state.get("move_commands", []),
        "llm_audit": state.get("llm_audit", ""),
        "api_events": state.get("api_events", []),
    }

    save_json(logs_dir / f"run_{run_id}.json", report)
    save_json(logs_dir / "latest_summary.json", {
        "run_id": run_id,
        "timestamp": report["timestamp"],
        "status": report["status"],
        "flag": report["flag"],
        "moves_planned": report["moves_planned"],
        "moves_executed": report["moves_executed"],
        "remaining_mismatches": report["remaining_mismatches"],
        "error": report["error"],
    })

    return state



def build_graph():
    """Create the solver LangGraph pipeline."""
    graph = StateGraph(SolverState)

    graph.add_node("load_context", node_load_context)
    graph.add_node("reset_and_fetch", node_reset_and_fetch)
    graph.add_node("parse_boards", node_parse_boards)
    graph.add_node("llm_audit", node_llm_audit)
    graph.add_node("execute_moves", node_execute_moves)
    graph.add_node("verify_final", node_verify_final)
    graph.add_node("finalize_log", node_finalize_log)

    graph.set_entry_point("load_context")
    graph.add_edge("load_context", "reset_and_fetch")
    graph.add_edge("reset_and_fetch", "parse_boards")
    graph.add_edge("parse_boards", "llm_audit")
    graph.add_edge("llm_audit", "execute_moves")
    graph.add_edge("execute_moves", "verify_final")
    graph.add_edge("verify_final", "finalize_log")
    graph.add_edge("finalize_log", END)

    return graph.compile()



def main() -> int:
    """Run solver workflow and print concise terminal summary."""
    app = build_graph()
    final_state = app.invoke({})

    status = final_state.get("status", "failed")
    flag = final_state.get("flag")
    run_id = final_state.get("run_id", "unknown")

    print(f"[run] {run_id}")
    print(f"[status] {status}")
    print(f"[moves] planned={len(final_state.get('move_commands', []))} executed={final_state.get('executed_moves', 0)}")

    if flag:
        print(f"[flag] {flag}")

    if status != "solved":
        print(f"[error] {final_state.get('error')}")
        print(f"[remaining] {final_state.get('remaining_mismatches', [])}")
        return 1

    return 0



if __name__ == "__main__":
    sys.exit(main())
