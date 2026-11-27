"""Source-bound requested lane-signal attempt pairs, without legal verdicts."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
KINDS = ("green_selected_drive", "adjacent_dark_drive",
         "second_green_drive", "green_selected_stand")
SOURCE_CLAUSE = "A downward-pointing green arrow means that a driver facing the signal may drive in any lane over which the green signal is shown."


def sha(data):
    return hashlib.sha256(data).hexdigest()


def prove(root, assignment, *, manifest=None, constructions=None):
    """Prove planned contrasts and distinguish absent permission from violation."""
    root = Path(root)
    if SOURCE_CLAUSE not in assignment["law"]["text"] or assignment["law_id"] != "NRS-484B-307-12a":
        raise ValueError("exact source permission clause missing")
    manifest = manifest or json.loads((root / "execution-manifest.json").read_text())
    if manifest.get("assignment_id") != assignment["assignment_id"]:
        raise ValueError("manifest assignment differs")
    entries = manifest["cases"]
    if len(entries) != 4 or {e["case_id"].rsplit("__", 1)[-1] for e in entries} != set(KINDS):
        raise ValueError("exact four attempted configurations required")
    observed = {}
    for entry in entries:
        kind = entry["case_id"].rsplit("__", 1)[-1]
        path = Path(entry["construction"])
        if path.is_absolute() or ".." in path.parts or path != Path("cases") / kind / "construction.json":
            raise ValueError("construction path differs")
        raw = (root / path).read_bytes() if constructions is None else constructions[kind]
        if sha(raw) != entry["construction_sha256"]:
            raise ValueError("construction SHA differs")
        construction = json.loads(raw)
        scene_files = [file for file in construction["files"] if file["path"] == "scene.json"]
        if len(scene_files) != 1 or construction["case_id"] != entry["case_id"]:
            raise ValueError("case scene or identity missing")
        scene = json.loads(scene_files[0]["content"])
        if scene["case_id"] != entry["case_id"] or scene["assignment_id"] != assignment["assignment_id"]:
            raise ValueError("scene assignment differs")
        signals = scene["signals"]
        if (len(signals) != 2 or {s["governed_lane_id"] for s in signals} != {"east", "west"} or
                any(s["facing"] != "bus_approach" or s["placement"] != "over_individual_lanes"
                    for s in signals)):
            raise ValueError("requested facing lane-head mapping differs")
        head_displays = {s["governed_lane_id"]: s["display"] for s in signals}
        if any(value not in {"down_green_arrow", "dark"} for value in head_displays.values()):
            raise ValueError("requested overhead head display differs")
        selected = next(s for s in signals if s["governed_lane_id"] == scene["bus_lane_id"])
        if selected["display"] not in {"down_green_arrow", "dark"}:
            raise ValueError("requested selected-lane display differs")
        route = scene["route_waypoint_centers_m"]
        if (not isinstance(route, list) or len(route) < 2 or any(
                not isinstance(point, list) or len(point) != 2 or
                any(not isinstance(value, (int, float)) or isinstance(value, bool) or
                    not math.isfinite(value) for value in point)
                for point in route)):
            raise ValueError("requested route geometry missing or invalid")
        route_length = sum(math.dist(a, b) for a, b in zip(route, route[1:]))
        moving = route_length > 1e-9
        observed[kind] = {"construction_sha256": sha(raw), "bus_lane": scene["bus_lane_id"],
                          "head_displays": head_displays, "route_length_m": route_length,
                          "selected_lane_display": selected["display"], "route_requests_motion": moving,
                          "requested_permission_configuration": moving and selected["display"] == "down_green_arrow"}
    expected = {
        "green_selected_drive": ("east", "down_green_arrow", True, True),
        "adjacent_dark_drive": ("west", "dark", True, False),
        "second_green_drive": ("west", "down_green_arrow", True, True),
        "green_selected_stand": ("east", "down_green_arrow", False, False),
    }
    for kind, values in expected.items():
        actual = observed[kind]
        expected_heads = {"east": "down_green_arrow", "west": (
            "down_green_arrow" if kind == "second_green_drive" else "dark")}
        if actual["head_displays"] != expected_heads:
            raise ValueError("requested fixed overhead head configuration differs: " + kind)
        if tuple(actual[key] for key in ("bus_lane", "selected_lane_display", "route_requests_motion",
                                         "requested_permission_configuration")) != values:
            raise ValueError("source-bound requested attempt differs: " + kind)
    return {"format": "worker-permission-attempt-pair-proof", "assignment_id": assignment["assignment_id"],
            "source_clause": SOURCE_CLAUSE, "source_sha256": sha(assignment["law"]["text"].encode()),
            "attempts": observed, "pairs": [
                {"case_ids": ["adjacent_dark_drive", "second_green_drive"],
                 "controlled_variable": "second_lane_green_request",
                 "meaning": "requested lane permission absent versus requested lane permission available"},
                {"case_ids": ["green_selected_drive", "green_selected_stand"],
                 "controlled_variable": "bus_motion_request",
                 "meaning": "requested drive versus stationary under a requested green indication"}],
            "original_native_observed": False, "legal_violation_claimed": False,
            "pinned_compliant_violating_pair_claimed": False}


def main():
    assignment = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text())
    report = prove(ROOT, assignment)
    (ROOT / "proposals/permission-attempt-pair-proof.json").write_text(json.dumps(report, indent=2) + "\n")
    print("source-bound requested permission attempt pairs passed without violation claim")


if __name__ == "__main__":
    main()
