"""CPU route candidate for the assigned one-way, first-intersection right turn.

Coordinates are engineering geometry in metres, not a claim that a real stand
was designated or that Native has loaded this layout.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASES = {
    "near_stand": {"stand_x": -55.0, "leave_x": -48.0},
    "far_stand": {"stand_x": -75.0, "leave_x": -68.0},
}


def make(case: str) -> dict:
    if case not in CASES:
        raise ValueError("unknown exact case")
    position = CASES[case]
    return {
        "format": "c150530-one-way-route-candidate-v1",
        "case": case,
        "coordinates": "metres; x east, y north",
        "travel_direction": "east",
        "road_lanes": [
            {"id": "approach", "start": [-90.0, -1.75], "end": [-4.0, -1.75], "direction": "east"},
            {"id": "first_junction_right", "start": [-4.0, -1.75], "end": [-1.75, -4.0], "direction": "right turn"},
            {"id": "south_exit", "start": [-1.75, -4.0], "end": [-1.75, -50.0], "direction": "south"},
            {"id": "first_junction_straight", "start": [-4.0, -1.75], "end": [4.0, -1.75], "direction": "east"},
            {"id": "east_exit", "start": [4.0, -1.75], "end": [50.0, -1.75], "direction": "east"},
        ],
        "directed_edges": [["approach", "first_junction_right"],
                           ["first_junction_right", "south_exit"],
                           ["approach", "first_junction_straight"],
                           ["first_junction_straight", "east_exit"]],
        "intersection_order": [{"id": "first", "approach_x": -4.0, "cross_street": "north_south"}],
        "stand": {"center": [position["stand_x"], -4.5], "parallel_to": "approach",
                  "curb_side": "right", "designation_provenance": "requires original source"},
        "departure": {"point": [position["leave_x"], -1.75], "lane": "approach"},
        "posted_notice": {"point": [position["stand_x"] + 10.0, -3.5],
                          "meaning": "right turn at first street intersection",
                          "installation_provenance": "requires original source"},
        "intended_route": ["approach", "first_junction_right", "south_exit"],
    }


def inspect(layout: dict) -> None:
    if layout.get("format") != "c150530-one-way-route-candidate-v1":
        raise ValueError("route candidate format differs")
    lanes = {lane["id"]: lane for lane in layout["road_lanes"]}
    if len(lanes) != len(layout["road_lanes"]):
        raise ValueError("duplicate lane")
    required = {"approach", "first_junction_right", "south_exit",
                "first_junction_straight", "east_exit"}
    if set(lanes) != required:
        raise ValueError("route lanes differ")
    edges = {tuple(edge) for edge in layout["directed_edges"]}
    if edges != {("approach", "first_junction_right"),
                 ("first_junction_right", "south_exit"),
                 ("approach", "first_junction_straight"),
                 ("first_junction_straight", "east_exit")}:
        raise ValueError("one-way connectivity differs")
    for source, target in edges:
        if lanes[source]["end"] != lanes[target]["start"]:
            raise ValueError("lane endpoints disconnected")
    if layout["intersection_order"] != [
        {"id": "first", "approach_x": -4.0, "cross_street": "north_south"}
    ]:
        raise ValueError("first intersection ordering differs")
    stand = layout["stand"]
    departure = layout["departure"]
    sign = layout["posted_notice"]
    if stand["parallel_to"] != "approach" or stand["curb_side"] != "right":
        raise ValueError("stand is not on assigned curb")
    if not (-90 < stand["center"][0] < departure["point"][0] < sign["point"][0] < -4):
        raise ValueError("stand, departure, notice and intersection order differs")
    if stand["center"][1] >= departure["point"][1]:
        raise ValueError("stand must be curbward of driving lane")
    if layout["intended_route"] != ["approach", "first_junction_right", "south_exit"]:
        raise ValueError("assigned right turn route differs")


def write_candidates() -> None:
    target = ROOT / "candidates"
    target.mkdir(exist_ok=True)
    for name in CASES:
        candidate = make(name)
        inspect(candidate)
        (target / f"{name}.json").write_text(json.dumps(candidate, indent=2) + "\n")


if __name__ == "__main__":
    write_candidates()
