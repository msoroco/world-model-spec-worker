"""Source-bound original-frame entry timing for NRS 484B.250(2).

This measures a physical timing quantity. It does not decide whether entry was
"approximately" simultaneous, whether subsection 4 applies, or who had priority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


REQUIRED = ("site-context.json", "road.xodr", "ego-body-history.jsonl",
            "other-body-history.jsonl")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source(root: Path, manifest: dict, name: str) -> Path:
    path = root / name
    item = manifest.get(name)
    if (not path.is_file() or path.is_symlink() or not isinstance(item, dict)
            or item.get("kind") != "original_native" or item.get("sha256") != _sha(path)):
        raise ValueError("Missing or stale original Native source: " + name)
    return path


def _rows(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if len(rows) < 2:
        raise ValueError("Original Native history needs two or more frames")
    return rows


def _project(vertices: list[list[float]], axis: tuple[float, float]) -> tuple[float, float]:
    values = [x * axis[0] + y * axis[1] for x, y in vertices]
    return min(values), max(values)


def _intersects_rectangle(body: list[list[float]], bounds: list[float]) -> bool:
    if len(body) < 3 or len(bounds) != 4 or any(len(point) != 2 for point in body):
        raise ValueError("Invalid original body polygon or intersection bounds")
    if not all(math.isfinite(v) for p in body for v in p) or not all(math.isfinite(v) for v in bounds):
        raise ValueError("Nonfinite original geometry")
    xmin, ymin, xmax, ymax = bounds
    if xmin >= xmax or ymin >= ymax:
        raise ValueError("Invalid intersection rectangle")
    rectangle = [[xmin, ymin], [xmax, ymin], [xmax, ymax], [xmin, ymax]]
    axes = [(1.0, 0.0), (0.0, 1.0)]
    axes += [(body[(i + 1) % len(body)][1] - body[i][1],
              body[i][0] - body[(i + 1) % len(body)][0]) for i in range(len(body))]
    for axis in axes:
        if axis == (0.0, 0.0):
            raise ValueError("Degenerate body edge")
        a, b = _project(body, axis), _project(rectangle, axis)
        if a[1] < b[0] or b[1] < a[0]:
            return False
    return True


def _entry(rows: list[dict], bounds: list[float]) -> dict:
    occupied = [_intersects_rectangle(row["body_vertices_xy_m"], bounds) for row in rows]
    if occupied[0]:
        raise ValueError("History starts after intersection entry")
    for i in range(1, len(rows)):
        if occupied[i] and not occupied[i - 1]:
            return {"lower_frame": rows[i - 1]["frame"], "upper_frame": rows[i]["frame"],
                    "lower_time_s": rows[i - 1]["time_s"], "upper_time_s": rows[i]["time_s"]}
    raise ValueError("No original footprint-intersection entry transition")


def measure(root: Path) -> dict:
    root = Path(root)
    manifest = json.loads((root / "source-manifest.json").read_text())
    sources = {name: _source(root, manifest, name) for name in REQUIRED}
    site = json.loads(sources["site-context.json"].read_text())
    if site.get("map_sha256") != _sha(sources["road.xodr"]):
        raise ValueError("Reviewed site map differs from original Native map")
    if (not site.get("reviewer") or not site.get("source_citation")
            or site.get("cell_id") != "C125763" or site.get("control") != "yield_sign"
            or site.get("ego_highway") == site.get("other_highway")
            or site.get("approach_relation") != "crossing"
            or site.get("ego_side") not in ("left", "right")):
        raise ValueError("Reviewed intersection scope is missing or differs")
    ego = _rows(sources["ego-body-history.jsonl"])
    other = _rows(sources["other-body-history.jsonl"])
    if len(ego) != len(other):
        raise ValueError("Original histories have different frame counts")
    previous = None
    for a, b in zip(ego, other):
        frame, time_s = a.get("frame"), a.get("time_s")
        if (frame, time_s) != (b.get("frame"), b.get("time_s")):
            raise ValueError("Original frame/time join differs")
        if a.get("actor_id") != site.get("ego_actor_id") or b.get("actor_id") != site.get("other_actor_id"):
            raise ValueError("Original actor identity differs from reviewed site")
        if type(frame) is not int or type(time_s) not in (int, float) or not math.isfinite(time_s):
            raise ValueError("Invalid original frame or time")
        if previous and (frame != previous[0] + 1 or not 0.049 <= time_s - previous[1] <= 0.051):
            raise ValueError("Original history is not contiguous 20 Hz")
        previous = frame, time_s
    bounds = site["intersection_bounds_xy_m"]
    ego_entry, other_entry = _entry(ego, bounds), _entry(other, bounds)
    delta = ego_entry["upper_time_s"] - other_entry["upper_time_s"]
    return {"format": "worker-crossing-entry-timing-v1",
            "assignment_id": "testing__C125763__NRS-484B-250-2__motor_vehicle_driver",
            "ego_entry": ego_entry, "other_entry": other_entry,
            "intersection_entry_time_difference_s": delta,
            "difference_bracket_s": [ego_entry["lower_time_s"] - other_entry["upper_time_s"],
                                     ego_entry["upper_time_s"] - other_entry["lower_time_s"]],
            "ego_side": site["ego_side"], "official_device_present": True,
            "legal_applicability": "unresolved_subsection_4_and_official_device_exception",
            "approximately_same_time": "unresolved_judgment",
            "source_sha256": {name: manifest[name]["sha256"] for name in REQUIRED},
            "legal_verdict_claimed": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(measure(args.attempt), indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
