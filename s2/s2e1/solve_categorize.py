from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


VERIFY_URL = "https://hub.ag3nts.org/verify"
TASK_NAME = "categorize"
CSV_NAME = "categorize.csv"
FLAG_FILE = "flag.json"
FLAG_PATTERN = re.compile(r"\{FLG:[^}]+\}")


PROMPT_VARIANTS = [
    (
        "Reply DNG or NEU only. "
        "If item is reactor/fuel/cassette/thorium/nuclear related -> NEU always. "
        "Else weapon/explosive/radioactive/toxic/hazard -> DNG, otherwise NEU. "
        "Item: {id} | {description}"
    ),
    (
        "Output only DNG or NEU. "
        "Reactor parts and fuel cassettes are ALWAYS NEU. "
        "Otherwise: firearms, explosives, toxic or radioactive things are DNG; the rest NEU. "
        "Data: {id}; {description}"
    ),
    (
        "Answer with one token: DNG or NEU. "
        "Reactor, nuclear fuel, thorium, cassette -> NEU (forced). "
        "Other truly dangerous items (weapons/explosives/toxic/radioactive) -> DNG. "
        "Else NEU. "
        "Goods: {id} {description}"
    ),
]


@dataclass
class Item:
    item_id: str
    description: str


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        values[key] = value
    return values


def _find_env_files(start_dir: Path) -> Iterable[Path]:
    current = start_dir.resolve()
    while True:
        candidate = current / ".env"
        if candidate.exists():
            yield candidate
        if current.parent == current:
            break
        current = current.parent


def load_api_key(work_dir: Path) -> str:
    preferred_names = [
        "AG3NTS_API_KEY",
        "AIDEVS_API_KEY",
        "AIDEV_API_KEY",
        "CENTRALA_API_KEY",
        "API_KEY",
    ]

    for name in preferred_names:
        value = os.environ.get(name, "").strip()
        if value:
            return value

    merged: dict[str, str] = {}
    for env_file in _find_env_files(work_dir):
        merged.update(_parse_env_file(env_file))

    for name in preferred_names:
        value = merged.get(name, "").strip()
        if value:
            return value

    for key, value in merged.items():
        key_u = key.upper()
        if "KEY" in key_u and ("AIDEV" in key_u or "AG3" in key_u or "CENTR" in key_u):
            if value.strip():
                return value.strip()

    raise RuntimeError("API key not found in env vars or .env files.")


def post_verify(api_key: str, prompt: str, timeout_sec: int = 30) -> dict:
    payload = {
        "apikey": api_key,
        "task": TASK_NAME,
        "answer": {"prompt": prompt},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        VERIFY_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=timeout_sec) as response:
        body = response.read().decode("utf-8", errors="replace")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"raw": body}


def extract_flag(obj: object) -> str | None:
    text = json.dumps(obj, ensure_ascii=False) if not isinstance(obj, str) else obj
    match = FLAG_PATTERN.search(text)
    return match.group(0) if match else None


def reset_budget(api_key: str) -> None:
    _ = post_verify(api_key=api_key, prompt="reset")


def fetch_fresh_csv(api_key: str, work_dir: Path) -> list[Item]:
    csv_url = f"https://hub.ag3nts.org/data/{urllib.parse.quote(api_key)}/{CSV_NAME}"
    with urllib.request.urlopen(csv_url, timeout=30) as response:
        content = response.read().decode("utf-8", errors="replace")

    csv_path = work_dir / CSV_NAME
    csv_path.write_text(content, encoding="utf-8")

    rows: list[Item] = []
    reader = csv.DictReader(content.splitlines())
    for row in reader:
        item_id = (row.get("code") or "").strip()
        description = (row.get("description") or "").strip()
        if not item_id or not description:
            continue
        rows.append(Item(item_id=item_id, description=description))

    if not rows:
        raise RuntimeError("Downloaded CSV has no valid rows.")
    return rows


def run_attempt(api_key: str, items: list[Item], prompt_template: str) -> tuple[str | None, dict]:
    last_response: dict = {}
    for item in items:
        prompt = prompt_template.format(id=item.item_id, description=item.description)
        response = post_verify(api_key=api_key, prompt=prompt)
        last_response = response
        flag = extract_flag(response)
        if flag:
            return flag, response
    return None, last_response


def save_flag(work_dir: Path, flag: str, response: dict) -> Path:
    target = work_dir / FLAG_FILE
    payload = {
        "task": TASK_NAME,
        "flag": flag,
        "timestamp": int(time.time()),
        "response": response,
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def main() -> int:
    work_dir = Path(__file__).resolve().parent

    try:
        api_key = load_api_key(work_dir)
    except Exception as exc:  # pragma: no cover
        print(f"[error] Cannot load API key: {exc}")
        return 1

    print("[info] Starting auto-retry solver...")

    attempt = 0
    while True:
        attempt += 1
        prompt_template = PROMPT_VARIANTS[(attempt - 1) % len(PROMPT_VARIANTS)]
        print(f"[info] Attempt {attempt}: reset + fresh CSV + 10 verifications")

        try:
            reset_budget(api_key)
            items = fetch_fresh_csv(api_key=api_key, work_dir=work_dir)
            flag, response = run_attempt(api_key=api_key, items=items, prompt_template=prompt_template)
        except urllib.error.HTTPError as exc:
            print(f"[warn] HTTP error {exc.code}: {exc.reason}")
            time.sleep(1.5)
            continue
        except urllib.error.URLError as exc:
            print(f"[warn] Network error: {exc}")
            time.sleep(1.5)
            continue
        except Exception as exc:
            print(f"[warn] Attempt failed: {exc}")
            time.sleep(1.0)
            continue

        if flag:
            path = save_flag(work_dir=work_dir, flag=flag, response=response)
            print(f"[success] Flag saved to: {path}")
            return 0

        print("[info] No flag yet, retrying with next prompt variant...")
        time.sleep(0.8)


if __name__ == "__main__":
    sys.exit(main())
