"""Independent saved-source comparison for the two planned entry conditions.

This checks experimental isolation and original-source completeness. It does not
classify immediate hazard, reasonable safety, right-of-way, or compliance.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "native"))
from acquisition import bind_original

ASSIGNMENT = "training__C177626__NRS-484B-263__motor_vehicle_driver"
PREFIX = ASSIGNMENT + "__selected_ed45c8e4__condition_"
CASE_IDS = (PREFIX + "a", PREFIX + "b")
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
POLICIES = ("earlier_yield", "later_yield")


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def read(root: Path, relative: str):
    path = (root / relative).resolve()
    if root.resolve() not in path.parents or not path.is_file():
        raise ValueError("Missing original source: " + relative)
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return json.loads(path.read_text())


def inspect(root: Path, expected_case: str, policy: str) -> dict:
    root = root.resolve()
    result = read(root, "result.json")
    context = read(root, "authored-context.json")
    native = read(root, "native_samples.jsonl")
    camera = read(root, "camera_frames.jsonl")
    frame_map = read(root, "video_frames.jsonl")
    measurements = read(root, "source-bound-measurements.json")
    if result.get("case_id") != expected_case or context.get("case_id") != expected_case:
        raise ValueError("Exact selected case identity differs")
    if result.get("provenance_kind") != "native" or result.get("diagnostic_fixture") is True:
        raise ValueError("Original Native result required")
    if result.get("legal_verdict_claimed") is True or result.get("physical_acceptance_claimed") is True:
        raise ValueError("Source result preclaimed outcome")
    if context.get("route_kind") != "entry" or context.get("map_source") != "native_opendrive_readback":
        raise ValueError("Original entry map source required")
    if len(native) != 600 or len(camera) != 600 or len(frame_map) != 600:
        raise ValueError("Complete original 600-frame source join required")
    if measurements.get("frames") != 600 or measurements.get("camera_views") != list(VIEWS):
        raise ValueError("Source-bound measurements incomplete")
    if context.get("approaching_vehicle_ids") != ["near", "far"]:
        raise ValueError("Two original highway participants required")
    if measurements.get("map_source_sha256") != context.get("map_sha256"):
        raise ValueError("Original map source hash differs")
    derived = bind_original(native, camera, context, policy)
    if measurements != derived:
        raise ValueError("Saved source-bound measurements differ from original rows")
    for i, (row, views, mapped) in enumerate(zip(native, camera, frame_map)):
        original = row.get("native_frame")
        if (row.get("frame") != i or views.get("frame") != original or
                mapped.get("video_frame") != i or mapped.get("native_frame") != original or
                views.get("views") != {view: original for view in VIEWS} or
                set(row.get("traffic", {})) != {"near", "far"}):
            raise ValueError("Original actor/camera/frame join differs")
    initial = native[0]["traffic"]
    source = {
        "case_id": expected_case,
        "map_sha256": context["map_sha256"],
        "route_kind": context["route_kind"],
        "actor_inventory_source": context.get("actor_inventory_source"),
        "approaching_vehicle_ids": context["approaching_vehicle_ids"],
        "initial_traffic": {name: {
            "center_xy_m": initial[name]["center_xy_m"],
            "road_id": initial[name]["road_id"],
            "lane_id": initial[name]["lane_id"],
        } for name in ("near", "far")},
        "camera_views": measurements["camera_views"],
        "frames": len(native),
        "policy": policy,
        "source_hashes": {name: digest(root / name) for name in (
            "result.json", "authored-context.json", "native_samples.jsonl",
            "camera_frames.jsonl", "video_frames.jsonl", "source-bound-measurements.json")},
    }
    return source


def compare(a: dict, b: dict) -> dict:
    fixed = ("map_sha256", "route_kind", "actor_inventory_source",
             "approaching_vehicle_ids", "initial_traffic", "camera_views", "frames")
    for key in fixed:
        if a[key] != b[key]:
            raise ValueError("Fixed comparison source differs: " + key)
    if (a["case_id"], b["case_id"]) != CASE_IDS or (a["policy"], b["policy"]) != POLICIES:
        raise ValueError("Declared comparison identities or policy difference missing")
    return {"format": "worker-c177626-comparison-audit", "passed": True,
            "comparison_id": ASSIGNMENT + "__selected_ed45c8e4__comparison",
            "case_ids": list(CASE_IDS), "fixed_conditions_checked": list(fixed),
            "deliberate_difference": "engineering_yield_request_gap_s",
            "source_hashes": [a["source_hashes"], b["source_hashes"]],
            "legal_verdict": None, "physical_acceptance_claimed": False}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--condition-a", type=Path, required=True)
    p.add_argument("--condition-b", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    report = compare(inspect(args.condition_a, CASE_IDS[0], POLICIES[0]),
                     inspect(args.condition_b, CASE_IDS[1], POLICIES[1]))
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
