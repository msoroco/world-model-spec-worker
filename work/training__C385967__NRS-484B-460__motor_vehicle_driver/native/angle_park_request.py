"""Thirty-second angle-parking requests and source-only at-rest meter."""
import argparse
import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = Path(__file__).resolve().parent.parent.name
CASES = {"indicated_heading": ASSIGNMENT + "__selected_03f318de__condition_a",
         "other_heading": ASSIGNMENT + "__selected_03f318de__condition_b"}
TARGET_DEG = {"indicated_heading": 45.0, "other_heading": 70.0}
DEVICE_ANGLE_DEG = 45.0
FRAMES = 600
RATE_HZ = 20


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def request_row(frame, condition):
    t = frame / RATE_HZ
    target = TARGET_DEG[condition]
    if t < 8:
        phase, heading, speed = "approach", 0.0, 3.0
    elif t < 12:
        phase, heading, speed = "park_maneuver", target * (t-8)/4, 1.0
    else:
        phase, heading, speed = "standing", target, 0.0
    return {"case_id": CASES[condition], "condition": condition,
            "frame": frame, "time_s": t, "source_kind": "authored_native_request",
            "ego": {"phase": phase, "heading_deg": round(heading, 6),
                    "speed_mps": speed, "space_id": "angle_space_1"},
            "device": {"kind": "official_angle_parking_control",
                       "indicated_angle_to_curb_deg": DEVICE_ANGLE_DEG,
                       "governs_space_id": "angle_space_1"},
            "road_edge": {"curb_heading_deg": 0.0, "side": "right"},
            "parking_space": {"space_id": "angle_space_1", "on_highway": True},
            "original_native_observed": False, "legal_verdict": None}


def build(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    entries = []
    for condition in CASES:
        path = output / (condition + ".jsonl")
        path.write_text("".join(json.dumps(request_row(i, condition), sort_keys=True) + "\n"
                                for i in range(FRAMES)))
        entries.append({"condition": condition, "case_id": CASES[condition],
                        "path": path.name, "sha256": sha(path), "frames": FRAMES})
    return {"format": "c385967-angle-parking-request-v1", "entries": entries,
            "duration_s": 30.0, "rate_hz": RATE_HZ, "native_executed": False}


def meter(source):
    source = Path(source)
    data = rows(source)
    if len(data) != FRAMES:
        raise ValueError("Missing complete 600-frame source sequence")
    if len({r.get("case_id") for r in data}) != 1 or data[0]["case_id"] not in CASES.values():
        raise ValueError("Source case identity differs")
    if {r.get("source_kind") for r in data} not in (
            {"authored_native_request"}, {"synthetic_native_sample"}):
        raise ValueError("Unknown or unsealed source provenance")
    standing = []
    for i, row in enumerate(data):
        if row.get("frame") != i or abs(row.get("time_s", -1)-i/RATE_HZ) > 1e-6:
            raise ValueError("Source frame/time join differs")
        device, edge, space = row.get("device", {}), row.get("road_edge", {}), row.get("parking_space", {})
        if (device.get("kind") != "official_angle_parking_control" or
            device.get("indicated_angle_to_curb_deg") != DEVICE_ANGLE_DEG or
            device.get("governs_space_id") != "angle_space_1"):
            raise ValueError("Governing angle device source absent")
        if edge.get("curb_heading_deg") != 0.0 or edge.get("side") != "right":
            raise ValueError("Curb/road-edge source absent")
        if space.get("space_id") != "angle_space_1" or space.get("on_highway") is not True:
            raise ValueError("Occupied highway parking-space source absent")
        ego = row.get("ego", {})
        if ego.get("space_id") != "angle_space_1":
            raise ValueError("Ego space occupancy source absent")
        values = [ego.get("heading_deg"), ego.get("speed_mps")]
        if any(not isinstance(v, (int,float)) or not math.isfinite(v) for v in values):
            raise ValueError("Nonfinite or absent ego readback")
        if ego.get("phase") == "standing" and ego["speed_mps"] <= 0.1:
            standing.append(ego["heading_deg"])
    if len(standing) < RATE_HZ:
        raise ValueError("At-rest measurement interval absent")
    errors = [abs((heading - DEVICE_ANGLE_DEG + 180) % 360 - 180)
              for heading in standing]
    return {"format": "c385967-at-rest-angle-meter-v1",
            "case_id": data[0]["case_id"], "source_kind": data[0]["source_kind"],
            "source_sha256": sha(source), "frames": FRAMES, "duration_s": 30.0,
            "at_rest_frames": len(standing), "indicated_angle_deg": DEVICE_ANGLE_DEG,
            "measured_at_rest_heading_deg": sum(standing)/len(standing),
            "maximum_absolute_angle_difference_deg": max(errors),
            "legal_angle_tolerance_asserted": False,
            "physical_completion_claimed": False, "legal_verdict_claimed": False}


def prove(output):
    manifest = build(output)
    output = Path(output)
    meters = {e["condition"]: meter(output / e["path"])
              for e in manifest["entries"]}
    if meters["indicated_heading"]["maximum_absolute_angle_difference_deg"] != 0:
        raise AssertionError("Indicated-heading diagnostic differs")
    if meters["other_heading"]["maximum_absolute_angle_difference_deg"] != 25:
        raise AssertionError("Other-heading diagnostic fails to separate angle")
    negatives = {}
    for label, mutate, expected in (
        ("missing_device", lambda r: r[0]["device"].clear(),
         "Governing angle device source absent"),
        ("missing_curb", lambda r: r[0]["road_edge"].clear(),
         "Curb/road-edge source absent"),
        ("missing_space", lambda r: r[0]["parking_space"].clear(),
         "Occupied highway parking-space source absent"),
        ("forged_original", lambda r: r[0].update(source_kind="original_native"),
         "Unknown or unsealed source provenance")):
        changed = rows(output / "indicated_heading.jsonl")
        mutate(changed)
        path = output / (label + ".jsonl")
        path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in changed))
        try:
            meter(path)
        except ValueError as exc:
            if str(exc) != expected:
                raise
            negatives[label] = expected
        else:
            raise AssertionError("Missing or forged source accepted: " + label)
    return {"format": "c385967-angle-parking-diagnostic-proof-v1",
            "manifest": manifest, "meters": meters, "negative_rejections": negatives,
            "native_executed": False, "legal_verdict_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("build", "meter", "prove"))
    parser.add_argument("--output")
    parser.add_argument("--source")
    args = parser.parse_args()
    result = (meter(args.source) if args.command == "meter" else
              build(args.output) if args.command == "build" else prove(args.output))
    print(json.dumps(result, indent=2, sort_keys=True))
