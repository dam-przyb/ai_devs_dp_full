from __future__ import annotations

import itertools
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

VERIFY_URL = "https://hub.ag3nts.org/verify"
FLAG_PATTERN = re.compile(r"\{FLG:[^}]+\}")


@dataclass
class RotationDecision:
    """Rotation plan for a single tile.

    Attributes:
        row: Row index in 1..3.
        col: Column index in 1..3.
        turns: Number of clockwise 90-degree rotations in 0..3.
        best_score: Similarity score for the selected rotation.
        second_score: Similarity score for the runner-up rotation.
    """

    row: int
    col: int
    turns: int
    best_score: float
    second_score: float


@dataclass
class GridInfo:
    """Detected puzzle grid lines in image coordinates."""

    row_lines: list[int]
    col_lines: list[int]


def utc_now() -> str:
    """Return current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def mask_secret(value: str) -> str:
    """Return safe short representation of a secret value."""
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def extract_flag(payload: Any) -> str | None:
    """Extract AG3NTS flag token from payload.

    Args:
        payload: API response body or any serializable object.

    Returns:
        Flag string when present, otherwise None.
    """
    if isinstance(payload, str):
        text = payload
    else:
        text = json.dumps(payload, ensure_ascii=False)
    match = FLAG_PATTERN.search(text)
    return match.group(0) if match else None


def image_to_gray_array(image_bytes: bytes) -> np.ndarray:
    """Convert PNG/JPG bytes to grayscale numpy array."""
    image = Image.open(BytesIO(image_bytes)).convert("L")
    return np.asarray(image, dtype=np.uint8)


def _longest_true_run(values: np.ndarray) -> int:
    """Return longest contiguous True run in a 1D boolean array."""
    best = 0
    current = 0
    for value in values:
        if bool(value):
            current += 1
            if current > best:
                best = current
        else:
            current = 0
    return best


def _cluster_indices(indices: list[int], gap: int = 2) -> list[list[int]]:
    """Group nearby integer positions into clusters."""
    if not indices:
        return []

    groups: list[list[int]] = [[indices[0]]]
    for idx in indices[1:]:
        if idx - groups[-1][-1] <= gap:
            groups[-1].append(idx)
        else:
            groups.append([idx])
    return groups


def _pick_four_lines(candidates: list[int], min_spacing: int = 30) -> list[int]:
    """Select four near-equidistant line positions from candidates."""
    if len(candidates) < 4:
        raise ValueError(f"Expected at least 4 line candidates, got {len(candidates)}")

    if len(candidates) == 4:
        return sorted(candidates)

    best_combo: tuple[int, int, int, int] | None = None
    best_score = float("-inf")

    for combo in itertools.combinations(sorted(candidates), 4):
        d1 = combo[1] - combo[0]
        d2 = combo[2] - combo[1]
        d3 = combo[3] - combo[2]
        if min(d1, d2, d3) < min_spacing:
            continue

        distances = np.asarray([d1, d2, d3], dtype=float)
        span = combo[3] - combo[0]
        variance_penalty = float(np.var(distances))
        score = span - (4.0 * variance_penalty)

        if score > best_score:
            best_score = score
            best_combo = combo

    if best_combo is None:
        raise ValueError("Could not select 4 grid lines from detected candidates")

    return list(best_combo)


def detect_grid(gray: np.ndarray, dark_threshold: int = 80) -> GridInfo:
    """Detect 3x3 puzzle grid line coordinates.

    Args:
        gray: Grayscale image array.
        dark_threshold: Pixel value threshold for dark line detection.

    Returns:
        GridInfo with 4 horizontal and 4 vertical line positions.
    """
    dark_mask = gray < dark_threshold
    height, width = gray.shape

    min_h_run = max(140, int(width * 0.27))
    min_v_run = max(140, int(height * 0.27))

    row_candidates = [
        row
        for row in range(height)
        if _longest_true_run(dark_mask[row, :]) >= min_h_run
    ]
    col_candidates = [
        col
        for col in range(width)
        if _longest_true_run(dark_mask[:, col]) >= min_v_run
    ]

    row_clusters = _cluster_indices(row_candidates, gap=2)
    col_clusters = _cluster_indices(col_candidates, gap=2)

    row_centers = [int(round(float(np.mean(cluster)))) for cluster in row_clusters]
    col_centers = [int(round(float(np.mean(cluster)))) for cluster in col_clusters]

    row_lines = _pick_four_lines(row_centers, min_spacing=35)
    col_lines = _pick_four_lines(col_centers, min_spacing=35)

    return GridInfo(row_lines=sorted(row_lines), col_lines=sorted(col_lines))


def _clean_small_components(mask: np.ndarray, min_size: int = 90) -> np.ndarray:
    """Remove tiny connected components from a boolean mask."""
    h, w = mask.shape
    visited = np.zeros((h, w), dtype=bool)
    cleaned = np.zeros((h, w), dtype=bool)

    for y in range(h):
        for x in range(w):
            if visited[y, x] or not mask[y, x]:
                continue

            stack = [(y, x)]
            visited[y, x] = True
            component: list[tuple[int, int]] = []

            while stack:
                cy, cx = stack.pop()
                component.append((cy, cx))

                for ny, nx in (
                    (cy - 1, cx),
                    (cy + 1, cx),
                    (cy, cx - 1),
                    (cy, cx + 1),
                ):
                    if ny < 0 or ny >= h or nx < 0 or nx >= w:
                        continue
                    if visited[ny, nx] or not mask[ny, nx]:
                        continue
                    visited[ny, nx] = True
                    stack.append((ny, nx))

            if len(component) >= min_size:
                for py, px in component:
                    cleaned[py, px] = True

    return cleaned


def extract_cell_masks(
    gray: np.ndarray,
    grid: GridInfo,
    pad: int = 4,
    output_size: int = 80,
    dark_threshold: int = 86,
) -> list[list[np.ndarray]]:
    """Extract and normalize 3x3 tile masks.

    Args:
        gray: Grayscale image array.
        grid: Detected grid lines.
        pad: Pixel padding from each cell boundary.
        output_size: Square tile output size.
        dark_threshold: Threshold used to isolate cable strokes.

    Returns:
        3x3 list of boolean masks where True marks cable pixels.
    """
    result: list[list[np.ndarray]] = []

    for row in range(3):
        row_tiles: list[np.ndarray] = []
        y0 = grid.row_lines[row] + pad
        y1 = grid.row_lines[row + 1] - pad

        for col in range(3):
            x0 = grid.col_lines[col] + pad
            x1 = grid.col_lines[col + 1] - pad

            if y1 <= y0 or x1 <= x0:
                raise ValueError("Invalid cell bounds while extracting tiles")

            cell = gray[y0:y1, x0:x1]
            resized = Image.fromarray(cell).resize((output_size, output_size), Image.Resampling.BILINEAR)
            resized_arr = np.asarray(resized, dtype=np.uint8)
            mask = resized_arr < dark_threshold
            cleaned = _clean_small_components(mask, min_size=90)
            row_tiles.append(cleaned)

        result.append(row_tiles)

    return result


def tile_edges(mask: np.ndarray, band: int = 6, min_pixels: int = 35) -> str:
    """Describe tile connectors by cardinal edges.

    Returns:
        String containing subset of N, E, S, W. If empty, returns "none".
    """
    north = int(mask[:band, :].sum()) >= min_pixels
    east = int(mask[:, -band:].sum()) >= min_pixels
    south = int(mask[-band:, :].sum()) >= min_pixels
    west = int(mask[:, :band].sum()) >= min_pixels

    labels = ""
    labels += "N" if north else ""
    labels += "E" if east else ""
    labels += "S" if south else ""
    labels += "W" if west else ""
    return labels or "none"


def build_edge_map(cells: list[list[np.ndarray]]) -> list[list[str]]:
    """Build symbolic board map from tile masks."""
    return [[tile_edges(cell) for cell in row] for row in cells]


def iou_score(a: np.ndarray, b: np.ndarray) -> float:
    """Compute IoU similarity score for two boolean masks."""
    union = np.logical_or(a, b).sum()
    if union == 0:
        return 1.0
    intersection = np.logical_and(a, b).sum()
    return float(intersection / union)


def score_rotations(current: np.ndarray, target: np.ndarray) -> list[float]:
    """Return IoU score for each clockwise rotation in [0, 1, 2, 3]."""
    scores: list[float] = []
    for turns in range(4):
        rotated = np.rot90(current, k=-turns)
        scores.append(iou_score(rotated, target))
    return scores


def decide_rotations(
    current_cells: list[list[np.ndarray]],
    target_cells: list[list[np.ndarray]],
) -> list[RotationDecision]:
    """Compute minimal per-cell clockwise rotations to match target board."""
    decisions: list[RotationDecision] = []

    for row in range(3):
        for col in range(3):
            scores = score_rotations(current_cells[row][col], target_cells[row][col])
            best_turns = int(np.argmax(scores))
            sorted_scores = sorted(scores, reverse=True)
            second_score = sorted_scores[1] if len(sorted_scores) > 1 else 0.0

            decisions.append(
                RotationDecision(
                    row=row + 1,
                    col=col + 1,
                    turns=best_turns,
                    best_score=float(scores[best_turns]),
                    second_score=float(second_score),
                )
            )

    return decisions


def decisions_to_commands(decisions: list[RotationDecision]) -> list[str]:
    """Expand per-cell turn counts into one-command-per-rotation sequence."""
    commands: list[str] = []
    for decision in decisions:
        coordinate = f"{decision.row}x{decision.col}"
        for _ in range(decision.turns):
            commands.append(coordinate)
    return commands


def decisions_to_dicts(decisions: list[RotationDecision]) -> list[dict[str, Any]]:
    """Convert RotationDecision objects to plain dictionaries."""
    return [asdict(item) for item in decisions]


def count_remaining_mismatches(
    current_cells: list[list[np.ndarray]],
    target_cells: list[list[np.ndarray]],
) -> list[str]:
    """Return coordinates where board still differs from the target orientation."""
    remaining: list[str] = []
    decisions = decide_rotations(current_cells, target_cells)
    for decision in decisions:
        if decision.turns != 0:
            remaining.append(f"{decision.row}x{decision.col}")
    return remaining


def load_recent_history(log_dir: Path, limit: int = 5) -> list[dict[str, Any]]:
    """Load compact summaries from latest historical attempts."""
    if not log_dir.exists():
        return []

    logs = sorted(log_dir.glob("run_*.json"), reverse=True)
    summaries: list[dict[str, Any]] = []

    for path in logs:
        if len(summaries) >= limit:
            break
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        summaries.append(
            {
                "run_id": content.get("run_id"),
                "status": content.get("status"),
                "moves_planned": content.get("moves_planned"),
                "moves_executed": content.get("moves_executed"),
                "remaining_mismatches": content.get("remaining_mismatches", []),
                "error": content.get("error"),
                "timestamp": content.get("timestamp"),
            }
        )

    return summaries


def save_json(path: Path, payload: dict[str, Any]) -> None:
    """Persist dictionary as pretty JSON using UTF-8 encoding."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
