"""Derive the first post-stand intersection maneuver from saved Native samples.

The input is a complete original-frame JSONL acquisition, joined to a sealed
file hash and exact candidate map. The result is an engineering measurement,
never a legal determination or evidence of a genuine stand designation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from candidate_opendrive import inspect as inspect_xodr
from reviewed_context import validate as validate_context
from stand_route import inspect as inspect_route

ASSIGNMENT = "testing__C150530__LVMC-11-60-090__taxi_driver"
RATE_HZ = 20


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inside(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        raise ValueError("saved source missing or outside attempt root")
    return resolved


def _samples(path: Path) -> list[dict]:
    rows = []
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid original frame {line_number}") from exc
        for key in ("frame", "time_s", "x_m", "y_m", "yaw_deg", "road_id", "lane_id"):
            if key not in row:
                raise ValueError(f"original frame lacks {key}: {line_number}")
        if not isinstance(row["frame"], int) or isinstance(row["frame"], bool):
            raise ValueError("nonintegral original frame")
        if any(not isinstance(row[key], (int, float)) or not math.isfinite(row[key])
               for key in ("time_s", "x_m", "y_m", "yaw_deg")):
            raise ValueError("nonfinite original motion sample")
        point = row.get("position_m")
        if (not isinstance(point, list) or len(point) != 3 or
                any(not isinstance(value, (int, float)) or not math.isfinite(value)
                    for value in point) or
                abs(point[0] - row["x_m"]) > 1e-6 or
                abs(point[1] - row["y_m"]) > 1e-6):
            raise ValueError("original position vector differs")
        if row["lane_id"] != -1 or row["road_id"] not in (10, 110, 11, 120, 12):
            raise ValueError("original sample leaves candidate one-way route")
        if rows:
            previous = rows[-1]
            if row["frame"] != previous["frame"] + 1:
                raise ValueError("original frame sequence has a gap or duplicate")
            delta = row["time_s"] - previous["time_s"]
            if not (0.035 <= delta <= 0.065):
                raise ValueError("original 20 Hz sample time differs")
            if math.dist((row["x_m"], row["y_m"]),
                         (previous["x_m"], previous["y_m"])) > 0.75:
                raise ValueError("original motion sample teleports")
        rows.append(row)
    if len(rows) < 4:
        raise ValueError("original motion trace too short")
    return rows


def finalize(trace: Path, seal: Path, context_packet: Path, map_path: Path,
             layout_path: Path, attempt_root: Path) -> dict:
    trace, seal = _inside(trace, attempt_root), _inside(seal, attempt_root)
    context_packet = _inside(context_packet, attempt_root)
    receipt = json.loads(seal.read_text())
    layout = json.loads(layout_path.read_text())
    inspect_route(layout)
    case = layout["case"]
    map_bytes = map_path.read_bytes()
    inspect_xodr(map_bytes, case)
    context_join = validate_context(json.loads(context_packet.read_text()),
                                    attempt_root, map_path, layout_path)
    full_case = ASSIGNMENT + "__" + case
    if (receipt.get("format") != "c150530-original-trace-seal-v1" or
            receipt.get("case_id") != full_case or receipt.get("rate_hz") != RATE_HZ or
            receipt.get("trace_sha256") != sha(trace) or
            receipt.get("context_packet_sha256") != sha(context_packet) or
            receipt.get("map_sha256") != hashlib.sha256(map_bytes).hexdigest()):
        raise ValueError("original trace seal or exact map hash differs")
    rows = _samples(trace)
    if receipt.get("frame_count") != len(rows) or receipt.get("first_frame") != rows[0]["frame"] or receipt.get("last_frame") != rows[-1]["frame"]:
        raise ValueError("original frame count or bounds differ from seal")
    stand_x = layout["stand"]["center"][0]
    if not (abs(rows[0]["x_m"] - stand_x) <= 3 and -5.5 <= rows[0]["y_m"] <= -3.5
            and rows[0]["road_id"] == 10):
        raise ValueError("original trace does not begin at candidate stand")
    departure_x = layout["departure"]["point"][0]
    departure = next((index for index, row in enumerate(rows[1:], 1)
                      if row["road_id"] == 10 and row["x_m"] >= departure_x - 1
                      and -2.5 <= row["y_m"] <= -1.0), None)
    if departure is None:
        raise ValueError("stand-to-driving-lane departure not observed")
    junction = next((index for index, row in enumerate(rows[departure + 1:], departure + 1)
                     if row["road_id"] in (110, 120)), None)
    if junction is None:
        raise ValueError("first post-departure intersection not observed")
    first_road = rows[junction]["road_id"]
    if any(row["road_id"] != 10 for row in rows[:junction]):
        raise ValueError("a different road appeared before first intersection")
    if not (-5 <= rows[junction]["x_m"] <= 5 and -5 <= rows[junction]["y_m"] <= 1):
        raise ValueError("junction road sample outside authored intersection")
    exit_road = 11 if first_road == 110 else 12
    exit_index = next((index for index, row in enumerate(rows[junction + 1:], junction + 1)
                       if row["road_id"] == exit_road), None)
    if exit_index is None:
        raise ValueError("first intersection receiving road not observed")
    if any(row["road_id"] != first_road for row in rows[junction:exit_index]):
        raise ValueError("junction route changed before receiving road")
    approach = rows[junction - 1]["yaw_deg"]
    exit_heading = rows[exit_index]["yaw_deg"]
    angle = ((exit_heading - approach + 180) % 360) - 180
    right_turn = first_road == 110 and exit_road == 11 and -135 < angle < -45
    return {
        "format": "c150530-original-trace-measurement-v1",
        "case_id": full_case,
        "trace_sha256": sha(trace),
        "seal_sha256": sha(seal),
        "context_packet_sha256": sha(context_packet),
        "context_source_joins": context_join["sources"],
        "map_sha256": hashlib.sha256(map_bytes).hexdigest(),
        "frame_count": len(rows),
        "stand_departure_frame": rows[departure]["frame"],
        "first_intersection_entry_frame": rows[junction]["frame"],
        "first_intersection_exit_frame": rows[exit_index]["frame"],
        "first_junction_road_id": first_road,
        "receiving_road_id": exit_road,
        "turn_angle_deg": angle,
        "engineering_right_turn_observed": right_turn,
        "limitation": "Saved geometry only; trace authenticity, designation and legal applicability need independent original-source audit",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("trace", "seal", "context_packet", "map", "layout", "attempt_root", "output"):
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    args = parser.parse_args()
    result = finalize(args.trace, args.seal, args.context_packet, args.map,
                      args.layout, args.attempt_root)
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
