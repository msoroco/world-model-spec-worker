"""Measure original door, loading and passing-path histories without a legal verdict."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C135087__NRS-484B-153-3__motor_vehicle_driver"
REQUIRED = ("frame_map", "door", "activity", "passing_vehicle", "geometry")


def _source(root: Path, entry: dict):
    rel = Path(entry["path"])
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("original source path escapes attempt")
    path = (root / rel).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("original source missing")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
        raise ValueError("original source hash mismatch")
    return json.loads(raw)


def measure(root: Path, inventory: dict, case_id: str, plan_path: Path) -> dict:
    if not case_id.startswith(ASSIGNMENT + "__") or inventory.get("case_id") != case_id:
        raise ValueError("exact case identity mismatch")
    if inventory.get("source_kind") != "original_native":
        raise ValueError("original Native acquisition required")
    sources = inventory.get("sources")
    if not isinstance(sources, dict) or set(sources) != set(REQUIRED):
        raise ValueError("complete original source inventory required")
    root = Path(root)
    data = {name: _source(root, sources[name]) for name in REQUIRED}
    plan = json.loads(Path(plan_path).read_text())
    if (plan.get("assignment_id"), plan.get("cell_id"), plan.get("law_id")) != (
            ASSIGNMENT, "C135087", "NRS-484B-153-3"):
        raise ValueError("frozen case plan identity mismatch")
    cases = [case for case in plan.get("cases", []) if case.get("case_id") == case_id]
    if len(cases) != 1:
        raise ValueError("exact door case absent or duplicated")
    scene = cases[0]["world_setup"]
    if (scene.get("layout"), scene.get("maneuver"), scene.get("control")) != (
            "narrow_road", "load_unload", "other_vehicle"):
        raise ValueError("narrow-road loading cell changed")
    geometry = data["geometry"]
    if geometry.get("source_kind") != "original_native_geometry":
        raise ValueError("original narrow-road geometry required")
    if geometry.get("loading_position_supported") is not True:
        raise ValueError("supported loading position unverified")
    if (geometry.get("road_width_m", 0) <= 0 or
            geometry.get("selected_vehicle_width_m", 0) <= 0 or
            geometry.get("selected_vehicle_length_m", 0) <= 0):
        raise ValueError("road or selected vehicle body geometry missing")
    if geometry.get("selected_vehicle_id") == geometry.get("passing_vehicle_id"):
        raise ValueError("passing vehicle must be separate")
    frames = data["frame_map"].get("frames")
    if not isinstance(frames, list) or len(frames) < 20:
        raise ValueError("original frame history incomplete")
    first = frames[0].get("frame")
    if type(first) is not int or [row.get("frame") for row in frames] != list(range(first, first + len(frames))):
        raise ValueError("original frames not consecutive")
    times = [row.get("time_s") for row in frames]
    if any(type(t) not in (float, int) or not math.isfinite(t) for t in times) or any(
            abs(b - a - .05) > .005 for a, b in zip(times, times[1:])):
        raise ValueError("original 20 Hz clock incomplete")
    for name in ("door", "activity", "passing_vehicle"):
        packet = data[name]
        if packet.get("case_id") != case_id or packet.get("source_kind") != "original_native":
            raise ValueError(name + " original case source mismatch")
        rows = packet.get("samples")
        if not isinstance(rows, list) or len(rows) != len(frames):
            raise ValueError(name + " history incomplete")
        if any(row.get("frame") != frame["frame"] or row.get("time_s") != frame["time_s"]
               for row, frame in zip(rows, frames)):
            raise ValueError(name + " frame/time join mismatch")
    doors = data["door"]["samples"]
    activities = data["activity"]["samples"]
    passing = data["passing_vehicle"]["samples"]
    if (data["door"].get("vehicle_id") != geometry["selected_vehicle_id"] or
            data["activity"].get("vehicle_id") != geometry["selected_vehicle_id"]):
        raise ValueError("selected vehicle door/activity source identity mismatch")
    kind = scene["load_kind"]
    if kind not in ("passenger", "cargo") or any(row.get("kind") != kind or
            type(row.get("active")) is not bool for row in activities):
        raise ValueError("original loading activity or kind missing")
    if not any(row["active"] for row in activities):
        raise ValueError("no original loading activity")
    if any(type(row.get("open")) is not bool or row.get("side") not in ("left", "right")
           for row in doors):
        raise ValueError("original door articulation missing")
    if doors[0]["open"] or doors[-1]["open"]:
        raise ValueError("original door opening and closing not both observed")
    opened = [i for i, row in enumerate(doors) if row["open"]]
    if opened != list(range(opened[0], opened[-1] + 1)):
        raise ValueError("multiple door intervals need separate source review")
    sides = {row["side"] for row in doors if row["open"]}
    if len(sides) != 1:
        raise ValueError("ambiguous original opened door side")
    door_side = sides.pop()
    center = float(geometry.get("selected_vehicle_center_y_m", float("nan")))
    center_x = float(geometry.get("selected_vehicle_center_x_m", float("nan")))
    half_width = float(geometry["selected_vehicle_width_m"]) / 2
    if not all(math.isfinite(v) for v in (center, center_x, half_width)):
        raise ValueError("selected vehicle body position missing")
    if abs(center) + half_width > geometry["road_width_m"] / 2:
        raise ValueError("selected loading vehicle outside original road width")
    clearances = []
    traffic_sides = set()
    passing_x = []
    for row in passing:
        if row.get("vehicle_id") != geometry["passing_vehicle_id"]:
            raise ValueError("separate passing vehicle identity mismatch")
        x, y, width, length = (row.get("center_x_m"), row.get("center_y_m"),
                               row.get("width_m"), row.get("length_m"))
        if any(type(v) not in (float, int) or not math.isfinite(v) for v in
               (x, y, width, length)) or width <= 0 or length <= 0:
            raise ValueError("passing vehicle original body history missing")
        offset = y - center
        clearance = abs(offset) - half_width - width / 2
        if clearance <= 0:
            raise ValueError("passing vehicle body overlaps loading vehicle")
        if abs(y) + width / 2 > geometry["road_width_m"] / 2:
            raise ValueError("passing vehicle body outside original road width")
        clearances.append(clearance)
        passing_x.append(x)
        traffic_sides.add("left" if offset > 0 else "right")
    if len(traffic_sides) != 1:
        raise ValueError("passing traffic side changes during episode")
    direction = 1 if passing_x[-1] > passing_x[0] else -1
    if (abs(passing_x[-1] - passing_x[0]) < geometry["selected_vehicle_length_m"] or
            any(direction * (b - a) < -.05 for a, b in zip(passing_x, passing_x[1:])) or
            not any(abs(passing_x[i] - center_x) <=
                    (geometry["selected_vehicle_length_m"] + passing[i]["length_m"]) / 2
                    for i in opened)):
        raise ValueError("passing vehicle lacks original door-window traversal")
    traffic_side = traffic_sides.pop()
    is_closest = door_side == traffic_side
    expected_closest = scene["door_side"] == "traffic_side"
    if is_closest != expected_closest:
        raise ValueError("measured door side contradicts exact case")
    inactive = [i for i in opened if not activities[i]["active"]]
    return {
        "format": "c135087-original-door-measurement-v1",
        "case_id": case_id, "source_kind": "original_native",
        "source_sha256": {key: sources[key]["sha256"] for key in REQUIRED},
        "frame_count": len(frames), "open_start_frame": frames[opened[0]]["frame"],
        "closed_after_frame": frames[opened[-1] + 1]["frame"],
        "open_duration_s": len(opened) * .05,
        "inactive_open_duration_s": len(inactive) * .05,
        "activity_kind": kind, "door_side": door_side,
        "passing_traffic_side": traffic_side,
        "door_closest_to_passing_traffic": is_closest,
        "minimum_body_clearance_m": min(clearances),
        "legal_necessity_or_immediacy": "unresolved",
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite saved measurement")
    inventory = json.loads((args.attempt / "inventory.json").read_text())
    measured = measure(args.attempt, inventory, args.case, args.plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(measured, indent=2) + "\n")


if __name__ == "__main__":
    main()
