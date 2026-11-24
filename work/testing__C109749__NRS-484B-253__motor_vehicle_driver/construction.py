"""Portable exact-case Native construction requests for NRS 484B.253.

The source packet is a reviewed map survey input. These are requested spawn,
route and control parameters; no resulting behavior is asserted.
"""

import argparse
import json
from pathlib import Path

from native_intersection import validate
from requirement_finalizer import ASSIGNMENT_ID, BRANCHES

POLICIES = {
    "inside_yield": ("inside", True, True, None),
    "inside_no_yield": ("inside", False, True, None),
    "approaching_yield": ("approaching", True, True, None),
    "approaching_no_yield": ("approaching", False, True, None),
    "signal_given": ("inside", True, True, None),
    "signal_omitted": ("inside", True, False, None),
    "reciprocal_yield": ("inside", True, True, True),
    "reciprocal_no_yield": ("inside", True, True, False),
}
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def build(case_id, packet):
    if not case_id.startswith(ASSIGNMENT_ID + "__"):
        raise ValueError("wrong assignment case")
    suffix = case_id.removeprefix(ASSIGNMENT_ID + "__")
    if suffix not in BRANCHES or suffix not in POLICIES:
        raise ValueError("unplanned exact left-turn case")
    validate(packet)
    initial_position, wait, signal, later_wait = POLICIES[suffix]
    if initial_position == "inside":
        initial_waypoint = packet["opposing_route"][1]
    else:
        initial_waypoint = packet["opposing_route"][0]
    if initial_position == "inside" and initial_waypoint["junction_id"] != packet["junction_id"]:
        raise ValueError("opponent inside spawn has wrong junction")
    if initial_position == "approaching" and initial_waypoint["junction_id"] == packet["junction_id"]:
        raise ValueError("opponent approach spawn already within junction")
    if later_wait is not None and not packet.get("later_opposing_route"):
        raise ValueError("reciprocal case needs a distinct later opposing route")
    return {
        "assignment_id": ASSIGNMENT_ID, "case_id": case_id,
        "native_map_sha256": packet["map_sha256"], "map_source_ref": packet["source_ref"],
        "junction_id": packet["junction_id"],
        "intersection_polygon": packet["intersection_polygon"],
        "ego_blueprint_id": packet["ego_blueprint_id"],
        "opponent_blueprint_id": packet["opponent_blueprint_id"],
        "ego_spawn_waypoint": packet["ego_route"][0],
        "initial_opponent_spawn_waypoint": initial_waypoint,
        "ego_route": packet["ego_route"],
        "initial_opponent_route": packet["opposing_route"],
        "later_opposing_route": packet.get("later_opposing_route") if later_wait is not None else None,
        "controller": {"wait_for_initial_opponent": wait, "signal_left": signal,
                       "wait_for_later_opponent": later_wait,
                       "target_speed_mps": 5.0},
        "capture": {"rate_hz": 20, "duration_s": 45, "frame_count": 900,
                    "cameras": list(CAMERAS),
                    "overview_resolution": [1920, 1080],
                    "detail_resolutions": [[1280, 720]] * 3},
        "required_original_sources": ["original-map.json", "original-trace.jsonl",
                                      "original-frame-map.json", "acquisition-receipt.json"],
        "legal_outcome": "unresolved", "physical_realization": "pending",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--map-packet", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    request = build(args.case, json.loads(Path(args.map_packet).read_text(encoding="utf-8")))
    Path(args.output).write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
