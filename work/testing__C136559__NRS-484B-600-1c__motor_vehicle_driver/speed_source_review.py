"""Source-bound original speed and posted-governing-portion review.

This measures strict numeric speed differences. Authority, road applicability,
and a sign outside camera view require independent source evidence.
"""
from __future__ import annotations

import hashlib
import json
import math
from decimal import Decimal, localcontext
from pathlib import Path


ASSIGNMENT = "testing__C136559__NRS-484B-600-1c__motor_vehicle_driver"
SOURCES = ("frame_map", "vehicle_motion", "route_occupancy", "posted_control")
UNIT_TO_MPS = {"mph": 0.44704, "km/h": 1 / 3.6, "m/s": 1.0}


def _source(root: Path, entry: dict) -> dict:
    rel = Path(entry["path"])
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("original posted-speed source path escapes attempt")
    path = (root / rel).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("original posted-speed source missing")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
        raise ValueError("original posted-speed source hash mismatch")
    return json.loads(raw)


def measure(root: Path, inventory: dict, case_id: str) -> dict:
    root = Path(root)
    if not case_id.startswith(ASSIGNMENT + "__") or inventory.get("case_id") != case_id:
        raise ValueError("exact posted-speed case mismatch")
    if inventory.get("source_kind") != "original_native":
        raise ValueError("original Native source required")
    sources = inventory.get("sources")
    if not isinstance(sources, dict) or set(sources) != set(SOURCES):
        raise ValueError("complete posted-speed original source inventory required")
    packets = {name: _source(root, sources[name]) for name in SOURCES}
    frames = packets["frame_map"].get("frames")
    if not isinstance(frames, list) or len(frames) < 900:
        raise ValueError("original 900-frame history missing")
    first = frames[0].get("frame")
    if type(first) is not int or [r.get("frame") for r in frames] != list(range(first, first + len(frames))):
        raise ValueError("original frame sequence not consecutive")
    times = [r.get("time_s") for r in frames]
    if any(type(t) not in (int, float) or not math.isfinite(t) for t in times) or any(
            abs(b - a - .05) > .005 for a, b in zip(times, times[1:])):
        raise ValueError("original frame clock not 20 Hz")
    motion = packets["vehicle_motion"]
    route = packets["route_occupancy"]
    for name, packet in (("vehicle motion", motion), ("route occupancy", route)):
        if packet.get("case_id") != case_id or packet.get("source_kind") != "original_native":
            raise ValueError(f"{name} original identity mismatch")
        if not isinstance(packet.get("samples"), list) or len(packet["samples"]) != len(frames):
            raise ValueError(f"{name} original history incomplete")
    control = packets["posted_control"]
    if (control.get("source_kind") != "original_native_context" or
            control.get("case_id") != case_id or
            control.get("unit") not in UNIT_TO_MPS or
            type(control.get("rate")) not in (int, float) or control["rate"] <= 0 or
            not math.isfinite(control["rate"]) or
            not control.get("highway_dedication_source") or
            not control.get("public_access_source") or
            not control.get("narrow_road_geometry_source") or
            not control.get("vehicle_clearance_source") or
            not control.get("governed_segment_source") or
            not control.get("governed_direction_source") or
            not control.get("sign_position_source") or
            not control.get("posting_authority_source") or
            type(control.get("public_authority_posted")) is not bool or
            type(control.get("sign_in_camera_view")) is not bool or
            not control.get("vehicle_id") or
            not control.get("governed_road_id") or
            not control.get("governed_segment_id") or
            not control.get("governed_direction")):
        raise ValueError("original posted control and highway provenance incomplete")
    if not control["sign_in_camera_view"] and not control.get("off_camera_reading_assumption_source"):
        raise ValueError("off-camera governing limit remains unknown without reading assumption")
    with localcontext() as context:
        context.prec = 50
        source_rate = Decimal(str(control["rate"]))
        if control["unit"] == "mph":
            rate_mps = source_rate * Decimal("0.44704")
        elif control["unit"] == "km/h":
            rate_mps = source_rate * Decimal(5) / Decimal(18)
        else:
            rate_mps = source_rate
    samples = []
    for frame, m, r in zip(frames, motion["samples"], route["samples"]):
        for name, row in (("motion", m), ("route", r)):
            if row.get("frame") != frame["frame"] or row.get("time_s") != frame["time_s"]:
                raise ValueError(f"original {name} frame/time join mismatch")
        if (m.get("vehicle_id") != control["vehicle_id"] or
                type(m.get("speed_mps")) not in (int, float) or
                not math.isfinite(m["speed_mps"]) or m["speed_mps"] < 0):
            raise ValueError("original vehicle speed or identity invalid")
        if (not isinstance(r.get("road_id"), str) or
                not isinstance(r.get("segment_id"), str) or
                not isinstance(r.get("direction"), str)):
            raise ValueError("original occupied road, portion or direction missing")
        if type(r.get("on_highway")) is not bool or type(r.get("operating")) is not bool:
            raise ValueError("original highway/operation state missing")
        governed = (r["on_highway"] and r["operating"] and
                    r["road_id"] == control["governed_road_id"] and
                    r["segment_id"] == control["governed_segment_id"] and
                    r["direction"] == control["governed_direction"] and
                    control["public_authority_posted"])
        with localcontext() as context:
            context.prec = 50
            difference = Decimal(str(m["speed_mps"])) - rate_mps if governed else None
        samples.append({"frame": frame["frame"], "time_s": frame["time_s"],
                        "speed_mps": m["speed_mps"], "governed_portion": governed,
                        "rate_difference_mps": float(difference) if governed else None,
                        "above_posted_rate": difference > 0 if governed else None})
    return {"format": "c136559-original-posted-speed-v1", "case_id": case_id,
            "source_sha256": {name: sources[name]["sha256"] for name in SOURCES},
            "original_frames": len(frames), "posted_rate": control["rate"],
            "posted_unit": control["unit"], "posted_rate_mps": float(rate_mps),
            "public_authority_posted": control["public_authority_posted"],
            "sign_in_camera_view": control["sign_in_camera_view"],
            "governed_frames": sum(row["governed_portion"] for row in samples),
            "observed_above_frames": sum(row["above_posted_rate"] is True for row in samples),
            "samples": samples, "legal_applicability_and_priority": "unresolved"}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite original speed review")
    inventory = json.loads((args.attempt / "inventory.json").read_text())
    result = measure(args.attempt, inventory, args.case)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
