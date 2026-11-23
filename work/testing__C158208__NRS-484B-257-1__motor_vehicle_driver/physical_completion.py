"""Source-bound intersection traversal outcome from sealed original body ticks."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from source_tick_capture import verify_seal, validate_geometry


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assess(attempt: Path, case_id: str, construction_sha256: str, *, diagnostic_fixture: bool = False) -> dict:
    attempt = Path(attempt)
    names = ("nearest-view-original-ticks.jsonl", "nearest-view-saved-packet.json", "nearest-view-tick-seal.json")
    sources = [{"path": name, "sha256": _hash(attempt / name) if (attempt / name).is_file() else None}
               for name in names]
    result = {"case_id": case_id, "construction_sha256": construction_sha256,
              "provenance_kind": "synthetic_fixture" if diagnostic_fixture else "original_capture",
              "diagnostic_fixture": diagnostic_fixture, "maneuver_completed": False,
              "realized_observables": {},
              "physical_checks": {"maneuver": {"status": "unverified",
                  "method": "Full original ego body polygon traverses and clears the reviewed intersection polygon",
                  "sources": sources}}}
    try:
        packet = verify_seal(attempt)
        geometry = packet["geometry"]
        origin, axis, _, _, entry_station, polygon = validate_geometry(geometry)
        from shapely.geometry import Polygon
        intersection = Polygon(polygon)
        raws = [json.loads(line) for line in (attempt / names[0]).read_text().splitlines() if line]
        bodies = [Polygon(row["ego"]["body_vertices_xy_m"]) for row in raws]
        if any(not body.is_valid or body.area <= 0 for body in bodies):
            raise ValueError("invalid original ego body polygon")
        projection = lambda vertex: (vertex[0] - origin[0]) * axis[0] + (vertex[1] - origin[1]) * axis[1]
        front = [max(projection(v) for v in body.exterior.coords) for body in bodies]
        rear = [min(projection(v) for v in body.exterior.coords) for body in bodies]
        far_edge = max(projection(v) for v in polygon)
        contact = [body.intersects(intersection) for body in bodies]
        start_before = front[0] < entry_station and not contact[0]
        entered = any(contact[1:])
        cleared = rear[-1] > far_edge and not contact[-1]
        status = "met" if start_before and entered and cleared else "not_met"
        result["physical_checks"]["maneuver"].update({"status": status,
            "start_before_entry": start_before, "intersection_contact_observed": entered,
            "full_body_cleared": cleared})
        result["maneuver_completed"] = status == "met"
        result["realized_observables"] = {"ego_front_station_initial_m": front[0],
            "ego_rear_station_final_m": rear[-1], "intersection_far_edge_station_m": far_edge,
            "sample_count": len(raws), "first_frame": raws[0]["frame"], "last_frame": raws[-1]["frame"]}
    except (FileNotFoundError, KeyError, ValueError, TypeError, json.JSONDecodeError) as error:
        result["physical_checks"]["maneuver"]["reason"] = str(error)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--case", required=True)
    parser.add_argument("--construction-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    args = parser.parse_args()
    outcome = assess(args.attempt, args.case, args.construction_sha256,
                     diagnostic_fixture=args.diagnostic_fixture)
    args.output.write_text(json.dumps(outcome, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(outcome["physical_checks"]["maneuver"]["status"])
