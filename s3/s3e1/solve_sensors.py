"""S3E1 sensor anomaly detection with note-template profiling.

Approach:
1. Programmatic checks for all measurement anomalies.
2. Note-template intent classification for all templates seen on clean records:
   - cache hit
   - local rule classifier
   - LLM fallback for unresolved templates only
3. Build an auditable run report and optionally submit to /verify.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

try:
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover - import-time guard for optional runtime path
    ChatOpenAI = None  # type: ignore[assignment]

load_dotenv()


@dataclass(frozen=True)
class SensorRule:
    """Validation rule for one sensor field.

    Attributes:
        field: JSON field name.
        minimum: Inclusive lower bound for active sensors.
        maximum: Inclusive upper bound for active sensors.
    """

    field: str
    minimum: float
    maximum: float


@dataclass
class NoteProfile:
    """Occurrence profile of one operator note template.

    Attributes:
        clean_ids: File IDs where measurements are clean.
        dirty_ids: File IDs where measurements are anomalous.
    """

    clean_ids: list[str] = field(default_factory=list)
    dirty_ids: list[str] = field(default_factory=list)


@dataclass
class DataCheckResult:
    """Result of deterministic measurement validation.

    Attributes:
        data_anomalies: Mapping of file ID to anomaly reasons.
        note_profiles: Note template matrix across clean/dirty files.
        total_files: Number of JSON files processed.
        clean_files: Count of files with no measurement anomaly.
        dirty_files: Count of files with measurement anomaly.
        range_violation_reasons: Count of range-violation reasons.
        inactive_nonzero_reasons: Count of inactive-field-nonzero reasons.
    """

    data_anomalies: dict[str, list[str]]
    note_profiles: dict[str, NoteProfile]
    total_files: int
    clean_files: int
    dirty_files: int
    range_violation_reasons: int
    inactive_nonzero_reasons: int


@dataclass
class NoteClassificationResult:
    """Result of note intent classification.

    Attributes:
        note_intents: Mapping note text -> OK/PROBLEM intent.
        problem_note_clean_ids: Clean-data file IDs where note intent is PROBLEM.
        ok_note_dirty_ids: Dirty-data file IDs where note intent is OK.
        source_counts: Number of templates resolved via cache/rule/llm.
        unresolved_before_llm: Number of templates sent to LLM.
        new_cache_entries: Number of new labels written to cache.
    """

    note_intents: dict[str, str]
    problem_note_clean_ids: set[str]
    ok_note_dirty_ids: set[str]
    source_counts: dict[str, int]
    unresolved_before_llm: int
    new_cache_entries: int


SENSORS_DIR = Path(__file__).parent / "sensors"
RUN_LOG_DIR = Path(__file__).parent / "run_logs"
CACHE_FILE = RUN_LOG_DIR / "note_classification_cache.json"
VERIFY_URL = "https://hub.ag3nts.org/verify"
TASK_NAME = "evaluation"

SENSOR_RULES: dict[str, SensorRule] = {
    "temperature": SensorRule("temperature_K", 553.0, 873.0),
    "pressure": SensorRule("pressure_bar", 60.0, 160.0),
    "water": SensorRule("water_level_meters", 5.0, 15.0),
    "voltage": SensorRule("voltage_supply_v", 229.0, 231.0),
    "humidity": SensorRule("humidity_percent", 40.0, 80.0),
}

# Strongly negative patterns for operational language in this dataset.
PROBLEM_PATTERNS = [
    "unstable",
    "irregular",
    "anomaly",
    "anomal",
    "fault",
    "error",
    "failure",
    "concern",
    "problem",
    "issue",
    "warning",
    "abnormal",
    "degradation",
    "malfunction",
    "suspicious",
    "questionable",
    "unreliable",
    "doubt",
    "doubts",
    "compromised",
    "not comfortable",
    "did not look right",
    "not the pattern i expected",
    "cannot be treated as normal",
    "root-cause",
    "investigation",
    "diagnostic",
    "troubleshooting",
    "urgent verification",
    "maintenance",
    "escalated",
    "escalated",
    "escalate",
    "review",
]

# Strongly positive patterns for regular operation language in this dataset.
OK_PATTERNS = [
    "looks stable",
    "within expected range",
    "status remains healthy",
    "system response remains predictable",
    "operational state is consistent",
    "all values follow expected distribution",
    "fits reference behavior",
    "performance appears nominal",
    "observed pattern remains trustworthy",
    "tracking data remains coherent",
    "baseline behavior is preserved",
    "confirmed regular operation",
    "no concerning drift",
    "consistency is maintained",
    "no corrective steps were needed",
    "closed this check without action",
    "left the setup untouched",
    "approved as-is",
]


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments.

    Returns:
        Parsed argument namespace.
    """
    parser = argparse.ArgumentParser(description="S3E1 sensor anomaly detector")
    parser.add_argument("--submit", action="store_true", help="Submit answer to /verify.")
    parser.add_argument("--task", default=TASK_NAME, help="Task name sent to /verify.")
    parser.add_argument("--verify-url", default=VERIFY_URL, help="Verification endpoint.")
    parser.add_argument(
        "--sensors-dir",
        default=str(SENSORS_DIR),
        help="Path to directory containing sensor JSON files.",
    )
    parser.add_argument(
        "--cache-file",
        default=str(CACHE_FILE),
        help="Path to note classification cache file.",
    )
    parser.add_argument(
        "--llm-model",
        default="openai/gpt-4o-mini",
        help="OpenRouter model used for unresolved note templates.",
    )
    parser.add_argument(
        "--llm-chunk-size",
        type=int,
        default=250,
        help="Maximum note templates per LLM batch.",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM fallback and fail if unresolved templates remain.",
    )
    return parser.parse_args()


def get_active_sensors(sensor_type: str) -> set[str]:
    """Parse sensor_type into active sensor names.

    Args:
        sensor_type: Sensor type field, for example "temperature/voltage".

    Returns:
        Set of normalized sensor tokens.
    """
    return {token.strip().lower() for token in sensor_type.split("/") if token.strip()}


def check_data(data: dict[str, Any]) -> tuple[list[str], int, int]:
    """Validate one record against sensor rules.

    Args:
        data: Parsed sensor JSON object.

    Returns:
        Tuple of:
            - reason list for detected anomalies,
            - count of range violation reasons,
            - count of inactive non-zero reasons.
    """
    reasons: list[str] = []
    range_violations = 0
    inactive_nonzero = 0

    sensor_type = str(data.get("sensor_type", ""))
    active = get_active_sensors(sensor_type)

    for sensor_name, rule in SENSOR_RULES.items():
        value = float(data.get(rule.field, 0))
        if sensor_name in active:
            if value < rule.minimum or value > rule.maximum:
                reasons.append(
                    f"{rule.field}={value} out of range [{rule.minimum}, {rule.maximum}]"
                )
                range_violations += 1
        else:
            if value != 0:
                reasons.append(
                    f"{rule.field}={value} should be 0 (sensor '{sensor_name}' inactive)"
                )
                inactive_nonzero += 1

    return reasons, range_violations, inactive_nonzero


def run_programmatic_checks(sensors_dir: Path) -> DataCheckResult:
    """Run deterministic measurement checks over all sensor files.

    Args:
        sensors_dir: Directory containing sensor JSON files.

    Returns:
        DataCheckResult with anomalies, note matrix and summary counts.
    """
    data_anomalies: dict[str, list[str]] = {}
    note_profiles: dict[str, NoteProfile] = {}
    range_violation_reasons = 0
    inactive_nonzero_reasons = 0

    files = sorted(sensors_dir.glob("*.json"))
    for path in files:
        file_id = path.stem
        data = json.loads(path.read_text(encoding="utf-8"))
        note = str(data.get("operator_notes", ""))
        profile = note_profiles.setdefault(note, NoteProfile())

        reasons, ranges, inactive = check_data(data)
        range_violation_reasons += ranges
        inactive_nonzero_reasons += inactive

        if reasons:
            data_anomalies[file_id] = reasons
            profile.dirty_ids.append(file_id)
        else:
            profile.clean_ids.append(file_id)

    return DataCheckResult(
        data_anomalies=data_anomalies,
        note_profiles=note_profiles,
        total_files=len(files),
        clean_files=len(files) - len(data_anomalies),
        dirty_files=len(data_anomalies),
        range_violation_reasons=range_violation_reasons,
        inactive_nonzero_reasons=inactive_nonzero_reasons,
    )


def load_note_cache(cache_file: Path) -> dict[str, str]:
    """Load note intent cache from disk.

    Supports two formats:
    - legacy: {"note": "OK"}
    - wrapped: {"labels": {"note": "OK"}}

    Args:
        cache_file: Cache file path.

    Returns:
        Mapping of note text to intent label.
    """
    if not cache_file.exists():
        return {}

    raw = json.loads(cache_file.read_text(encoding="utf-8"))
    labels_obj: Any
    if isinstance(raw, dict) and isinstance(raw.get("labels"), dict):
        labels_obj = raw["labels"]
    else:
        labels_obj = raw

    cache: dict[str, str] = {}
    if not isinstance(labels_obj, dict):
        return cache

    for note, label in labels_obj.items():
        normalized = str(label).upper().strip()
        if normalized in {"OK", "PROBLEM"}:
            cache[str(note)] = normalized
    return cache


def save_note_cache(cache_file: Path, cache: dict[str, str]) -> None:
    """Persist note intent cache.

    Args:
        cache_file: Cache file path.
        cache: Mapping note text -> intent label.
    """
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    sorted_items = dict(sorted(cache.items(), key=lambda item: item[0]))
    cache_file.write_text(
        json.dumps(sorted_items, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def classify_note_with_rules(note: str) -> str | None:
    """Classify note intent with conservative lexical rules.

    Args:
        note: Operator note text.

    Returns:
        "OK", "PROBLEM", or None when ambiguous.
    """
    text = note.lower()
    has_problem = any(pattern in text for pattern in PROBLEM_PATTERNS)
    has_ok = any(pattern in text for pattern in OK_PATTERNS)

    # Precision-first mode:
    # - auto-label only clearly positive notes as OK
    # - any possible problem signal is left unresolved for LLM/cache
    if has_ok and not has_problem:
        return "OK"
    return None


def create_llm(model_name: str) -> Any:
    """Create ChatOpenAI client configured for OpenRouter.

    Args:
        model_name: OpenRouter model name.

    Returns:
        Initialized ChatOpenAI client.

    Raises:
        RuntimeError: If dependencies or credentials are unavailable.
    """
    if ChatOpenAI is None:
        raise RuntimeError(
            "langchain_openai is not installed. Install dependencies before using LLM fallback."
        )

    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENROUTERKEY")
    if not api_key:
        raise RuntimeError(
            "Missing OpenRouter credentials. Set OPENROUTER_API_KEY or OPENROUTERKEY."
        )

    return ChatOpenAI(
        model=model_name,
        openai_api_key=api_key,
        openai_api_base="https://openrouter.ai/api/v1",
        temperature=0,
    )


def response_to_text(content: Any) -> str:
    """Normalize LLM response content to plain text.

    Args:
        content: Raw response.content from LangChain.

    Returns:
        Plain-text rendering of the content payload.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict):
                chunks.append(str(item.get("text", "")))
            else:
                chunks.append(str(item))
        return "".join(chunks)
    return str(content)


def classify_note_batch_with_llm(llm: Any, notes: list[str]) -> dict[str, str]:
    """Classify one note batch with retry for incomplete model output.

    Args:
        llm: Initialized ChatOpenAI client.
        notes: Batch of note templates.

    Returns:
        Mapping note text -> intent label.

    Raises:
        RuntimeError: If model output stays incomplete after retries.
    """
    pending = list(notes)
    resolved: dict[str, str] = {}

    for _ in range(2):
        if not pending:
            break

        numbered = "\n".join(f"{idx + 1}. {note}" for idx, note in enumerate(pending))
        prompt = (
            "Classify each operator note as OK or PROBLEM.\n"
            "PROBLEM means the operator describes instability, fault, risk, anomaly, "
            "investigation, escalation, distrust, or non-normal behavior.\n"
            "OK means the operator states regular, healthy, stable, expected operation "
            "with no corrective action needed.\n\n"
            "Return ONLY one line per note in this exact format:\n"
            "<number>:OK\n"
            "or\n"
            "<number>:PROBLEM\n\n"
            f"Notes:\n{numbered}"
        )

        raw_text = response_to_text(llm.invoke(prompt).content)
        parsed_indexes: set[int] = set()
        for line in raw_text.splitlines():
            match = re.match(r"^\s*(\d+)\s*:\s*(OK|PROBLEM)\s*$", line.strip(), re.IGNORECASE)
            if not match:
                continue
            idx = int(match.group(1)) - 1
            if idx < 0 or idx >= len(pending):
                continue
            label = match.group(2).upper()
            note = pending[idx]
            resolved[note] = label
            parsed_indexes.add(idx)

        pending = [note for idx, note in enumerate(pending) if idx not in parsed_indexes]

    if pending:
        raise RuntimeError(
            f"Incomplete LLM classification for {len(pending)} note templates. "
            "Use --no-llm only when cache+rules are sufficient."
        )
    return resolved


def classify_notes_with_llm(
    notes: list[str],
    model_name: str,
    chunk_size: int,
) -> dict[str, str]:
    """Classify unresolved notes with LLM in chunks.

    Args:
        notes: Note templates that require semantic classification.
        model_name: OpenRouter model name.
        chunk_size: Max notes per request.

    Returns:
        Mapping note text -> intent label.
    """
    if not notes:
        return {}

    llm = create_llm(model_name)
    results: dict[str, str] = {}

    for start in range(0, len(notes), chunk_size):
        chunk = notes[start : start + chunk_size]
        print(f"LLM classifying notes {start + 1}-{start + len(chunk)} of {len(notes)}")
        results.update(classify_note_batch_with_llm(llm=llm, notes=chunk))

    return results


def run_note_classification(
    note_profiles: dict[str, NoteProfile],
    cache: dict[str, str],
    model_name: str,
    chunk_size: int,
    use_llm: bool,
) -> NoteClassificationResult:
    """Resolve note intent for templates seen on clean records.

    Args:
        note_profiles: Note profile matrix across clean/dirty occurrences.
        cache: Existing note intent cache.
        model_name: OpenRouter model used for fallback classification.
        chunk_size: Number of templates per LLM batch.
        use_llm: Whether unresolved templates can be sent to LLM.

    Returns:
        NoteClassificationResult with classified intents and ID sets.

    Raises:
        RuntimeError: If unresolved templates remain and LLM is disabled.
    """
    note_intents: dict[str, str] = {}
    source_counts = {"cache": 0, "rule": 0, "llm": 0}

    candidate_notes = sorted(
        note for note, profile in note_profiles.items() if profile.clean_ids
    )
    unresolved: list[str] = []

    for note in candidate_notes:
        if note in cache:
            note_intents[note] = cache[note]
            source_counts["cache"] += 1
            continue

        rule_label = classify_note_with_rules(note)
        if rule_label is not None:
            note_intents[note] = rule_label
            source_counts["rule"] += 1
        else:
            unresolved.append(note)

    unresolved_before_llm = len(unresolved)
    new_cache_entries = 0

    if unresolved:
        if not use_llm:
            raise RuntimeError(
                f"LLM disabled, but {len(unresolved)} clean-note templates are unresolved."
            )
        llm_labels = classify_notes_with_llm(
            notes=unresolved,
            model_name=model_name,
            chunk_size=chunk_size,
        )
        for note, label in llm_labels.items():
            note_intents[note] = label
            cache[note] = label
            source_counts["llm"] += 1
            new_cache_entries += 1

    problem_note_clean_ids: set[str] = set()
    ok_note_dirty_ids: set[str] = set()
    for note in candidate_notes:
        intent = note_intents[note]
        profile = note_profiles[note]
        if intent == "PROBLEM":
            problem_note_clean_ids.update(profile.clean_ids)
        else:
            ok_note_dirty_ids.update(profile.dirty_ids)

    return NoteClassificationResult(
        note_intents=note_intents,
        problem_note_clean_ids=problem_note_clean_ids,
        ok_note_dirty_ids=ok_note_dirty_ids,
        source_counts=source_counts,
        unresolved_before_llm=unresolved_before_llm,
        new_cache_entries=new_cache_entries,
    )


def submit_answer(
    anomaly_ids: list[str],
    task_name: str,
    verify_url: str,
) -> dict[str, Any]:
    """Submit anomaly IDs to /verify.

    Args:
        anomaly_ids: Final list of anomaly file IDs.
        task_name: Task name expected by central endpoint.
        verify_url: Verification endpoint URL.

    Returns:
        Parsed JSON response.

    Raises:
        RuntimeError: If API key is missing.
        httpx.HTTPStatusError: If endpoint returns non-2xx response.
    """
    api_key = os.getenv("AIDEVSKEY")
    if not api_key:
        raise RuntimeError("Missing AIDEVSKEY environment variable.")

    payload = {
        "apikey": api_key,
        "task": task_name,
        "answer": {"recheck": anomaly_ids},
    }

    print(f"Submitting {len(anomaly_ids)} IDs to {verify_url}")
    response = httpx.post(verify_url, json=payload, timeout=30)
    print(f"Verify status: {response.status_code}")
    print(f"Verify body: {response.text}")
    response.raise_for_status()
    return response.json()


def build_report(
    data_result: DataCheckResult,
    note_result: NoteClassificationResult,
    all_anomaly_ids: list[str],
) -> dict[str, Any]:
    """Build structured run report.

    Args:
        data_result: Deterministic check result.
        note_result: Note classification result.
        all_anomaly_ids: Final deduplicated anomaly IDs.

    Returns:
        JSON-serializable run report.
    """
    templates_total = len(data_result.note_profiles)
    templates_with_clean = sum(
        1 for profile in data_result.note_profiles.values() if profile.clean_ids
    )
    templates_with_dirty = sum(
        1 for profile in data_result.note_profiles.values() if profile.dirty_ids
    )
    templates_mixed = sum(
        1
        for profile in data_result.note_profiles.values()
        if profile.clean_ids and profile.dirty_ids
    )
    problem_templates = sum(
        1 for label in note_result.note_intents.values() if label == "PROBLEM"
    )

    return {
        "timestamp": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "data": {
            "total_files": data_result.total_files,
            "clean_files": data_result.clean_files,
            "dirty_files": data_result.dirty_files,
            "data_anomaly_ids": sorted(data_result.data_anomalies.keys()),
            "range_violation_reasons": data_result.range_violation_reasons,
            "inactive_nonzero_reasons": data_result.inactive_nonzero_reasons,
        },
        "notes": {
            "templates_total": templates_total,
            "templates_with_clean_ids": templates_with_clean,
            "templates_with_dirty_ids": templates_with_dirty,
            "templates_mixed": templates_mixed,
            "classified_templates": len(note_result.note_intents),
            "problem_templates": problem_templates,
            "classification_sources": note_result.source_counts,
            "unresolved_before_llm": note_result.unresolved_before_llm,
            "new_cache_entries": note_result.new_cache_entries,
            "problem_note_clean_ids": sorted(note_result.problem_note_clean_ids),
            "ok_note_dirty_ids": sorted(note_result.ok_note_dirty_ids),
        },
        "final": {
            "anomaly_count": len(all_anomaly_ids),
            "anomaly_ids": all_anomaly_ids,
        },
    }


def save_reports(report: dict[str, Any], run_log_dir: Path) -> Path:
    """Save timestamped and latest reports.

    Args:
        report: Run report dictionary.
        run_log_dir: Log output directory.

    Returns:
        Path to timestamped report file.
    """
    run_log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = report["timestamp"]
    run_path = run_log_dir / f"run_{timestamp}.json"
    latest_path = run_log_dir / "latest_summary.json"
    serialized = json.dumps(report, indent=2, ensure_ascii=False)
    run_path.write_text(serialized, encoding="utf-8")
    latest_path.write_text(serialized, encoding="utf-8")
    return run_path


def main() -> None:
    """Run the end-to-end anomaly detection pipeline."""
    args = parse_args()
    sensors_dir = Path(args.sensors_dir)
    cache_file = Path(args.cache_file)

    print("=" * 64)
    print("STEP 1: Programmatic measurement checks")
    print("=" * 64)
    data_result = run_programmatic_checks(sensors_dir=sensors_dir)
    print(f"Processed files: {data_result.total_files}")
    print(f"Data anomalies: {data_result.dirty_files}")
    print(f"Clean files: {data_result.clean_files}")
    print(f"Range-violation reasons: {data_result.range_violation_reasons}")
    print(f"Inactive-nonzero reasons: {data_result.inactive_nonzero_reasons}")

    print("\n" + "=" * 64)
    print("STEP 2: Note-template intent classification")
    print("=" * 64)
    cache = load_note_cache(cache_file=cache_file)
    print(f"Loaded note cache entries: {len(cache)}")
    note_result = run_note_classification(
        note_profiles=data_result.note_profiles,
        cache=cache,
        model_name=args.llm_model,
        chunk_size=args.llm_chunk_size,
        use_llm=not args.no_llm,
    )
    if note_result.new_cache_entries:
        save_note_cache(cache_file=cache_file, cache=cache)
        print(f"Saved note cache entries: {len(cache)}")

    all_anomaly_ids = sorted(
        set(data_result.data_anomalies.keys()) | note_result.problem_note_clean_ids
    )
    print(f"Clean-data files with PROBLEM notes: {len(note_result.problem_note_clean_ids)}")
    print(f"Total anomaly IDs prepared: {len(all_anomaly_ids)}")

    report = build_report(
        data_result=data_result,
        note_result=note_result,
        all_anomaly_ids=all_anomaly_ids,
    )

    if args.submit:
        print("\n" + "=" * 64)
        print("STEP 3: Submit")
        print("=" * 64)
        submit_response = submit_answer(
            anomaly_ids=all_anomaly_ids,
            task_name=args.task,
            verify_url=args.verify_url,
        )
        report["submit_response"] = submit_response

    run_path = save_reports(report=report, run_log_dir=cache_file.parent)
    print(f"Run report saved: {run_path}")


if __name__ == "__main__":
    main()
