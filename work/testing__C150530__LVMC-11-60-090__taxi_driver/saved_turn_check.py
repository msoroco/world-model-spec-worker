"""Source-bound saved-event checker; reports measurements, never legal acceptance."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

REQUIRED_CONTEXT = ("cab_license", "stand_designation", "posted_notice", "jurisdiction")


def _verified_source(ref: dict, source_root: Path) -> dict:
    if not isinstance(ref, dict) or not ref.get("path") or not ref.get("sha256"):
        raise ValueError("context lacks source path and hash")
    path = (source_root / ref["path"]).resolve()
    if not path.is_relative_to(source_root.resolve()) or not path.is_file():
        raise ValueError("context source absent or outside source root")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != ref["sha256"]:
        raise ValueError("context source hash differs")
    return {"path": ref["path"], "sha256": actual}


def check(trace: dict, layout: dict, source_root: Path) -> dict:
    from stand_route import inspect

    inspect(layout)
    if trace.get("case") != layout["case"]:
        raise ValueError("trace case differs from route candidate")
    context = trace.get("context", {})
    sources = {}
    for field in REQUIRED_CONTEXT:
        item = context.get(field, {})
        if item.get("status") != "documented":
            raise ValueError(field + " has no documented source")
        sources[field] = _verified_source(item.get("source"), source_root)
    events = trace.get("events")
    if not isinstance(events, list) or len(events) < 4:
        raise ValueError("saved events missing")
    times = [event.get("time_s") for event in events]
    if any(not isinstance(t, (int, float)) or not math.isfinite(t) for t in times):
        raise ValueError("event time invalid")
    if any(later <= earlier for earlier, later in zip(times, times[1:])):
        raise ValueError("event order invalid")
    kinds = [event.get("kind") for event in events]
    if kinds.count("stand_departure") != 1 or kinds.count("intersection_entry") < 1:
        raise ValueError("stand departure or intersection entry missing")
    departure_index = kinds.index("stand_departure")
    intersections = [event for event in events[departure_index + 1:]
                     if event.get("kind") == "intersection_entry"]
    if not intersections or intersections[0].get("intersection_id") != "first":
        raise ValueError("first post-departure intersection missing or misordered")
    if any(event.get("kind") == "intersection_entry" for event in events[:departure_index]):
        raise ValueError("intersection precedes stand departure")
    first_time = intersections[0]["time_s"]
    maneuvers = [event for event in events if event.get("kind") == "intersection_exit"
                 and event.get("intersection_id") == "first" and event["time_s"] > first_time]
    if len(maneuvers) != 1:
        raise ValueError("first intersection exit missing or ambiguous")
    exit_event = maneuvers[0]
    approach_heading = exit_event.get("approach_heading_deg")
    departure_heading = exit_event.get("departure_heading_deg")
    if any(not isinstance(x, (int, float)) or not math.isfinite(x)
           for x in (approach_heading, departure_heading)):
        raise ValueError("turn headings absent")
    turn_angle = ((departure_heading - approach_heading + 180) % 360) - 180
    if exit_event.get("exit_lane") not in {"south_exit", "east_exit"}:
        raise ValueError("exit lane absent from candidate")
    right_turn_observed = -135 < turn_angle < -45 and exit_event["exit_lane"] == "south_exit"
    event_sources = [_verified_source(event.get("source"), source_root) for event in events]
    return {
        "format": "c150530-saved-turn-measurement-v1",
        "case": trace["case"],
        "first_intersection_id": "first",
        "departure_time_s": events[departure_index]["time_s"],
        "first_intersection_time_s": first_time,
        "turn_angle_deg": turn_angle,
        "exit_lane": exit_event["exit_lane"],
        "right_turn_observed": right_turn_observed,
        "context_sources": sources,
        "event_sources": event_sources,
        "limitation": "Source references and route measurements only; original sensor provenance, Native motion and legal applicability require independent review.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--layout", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = check(json.loads(args.trace.read_text()), json.loads(args.layout.read_text()),
                   args.source_root)
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
