"""Exact 30-second bus speed requests and source-bound diagnostic meter.

No calendar, beacon, sign validity, Native pixels or legal result is inferred
from these authored/synthetic diagnostic rows.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = Path(__file__).resolve().parent.parent.name
CASE_IDS = {"lower_speed": ASSIGNMENT + "__selected_d08892c9__condition_a",
            "higher_speed": ASSIGNMENT + "__selected_d08892c9__condition_b"}
SPEEDS_MPS = {"lower_speed": 20 * 0.44704,
              "higher_speed": 30 * 0.44704}
FRAMES = 600
RATE_HZ = 20
ZONE_START_M = 100.0
ZONE_END_M = 200.0
LEGAL_LIMIT_MPS = 25 * 0.44704


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def request_row(frame, condition):
    t = frame / RATE_HZ
    speed = SPEEDS_MPS[condition]
    x = -50 + speed * t
    return {"case_id": CASE_IDS[condition], "condition": condition,
            "frame": frame, "time_s": t, "source_kind": "authored_native_request",
            "bus": {"actor_class": "motor_bus", "x_m": round(x, 6),
                    "y_m": 0.0, "speed_mps": speed},
            "zone": {"kind": "school_crossing_zone", "start_x_m": ZONE_START_M,
                     "end_x_m": ZONE_END_M, "sign_source": "authored_zone_design"},
            "children": [{"id": "child_left", "x_m": 145.0, "y_m": 5.0},
                         {"id": "child_right", "x_m": 155.0, "y_m": -5.0}],
            "school_calendar_verified": False, "beacon_state_verified": False,
            "sign_effective_hours_verified": False, "legal_verdict": None,
            "original_native_observed": False}


def build(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    entries = []
    for condition in CASE_IDS:
        path = output / (condition + ".jsonl")
        path.write_text("".join(json.dumps(request_row(i, condition), sort_keys=True) + "\n"
                                for i in range(FRAMES)))
        entries.append({"condition": condition, "case_id": CASE_IDS[condition],
                        "path": path.name, "sha256": sha(path), "frames": FRAMES})
    return {"format": "c255451-school-crossing-request-v1", "entries": entries,
            "rate_hz": RATE_HZ, "duration_s": 30.0,
            "source_kind": "authored_native_request", "native_executed": False}


def meter(source):
    source = Path(source)
    data = rows(source)
    if len(data) != FRAMES:
        raise ValueError("Missing complete 600-frame source sequence")
    case_ids = {row.get("case_id") for row in data}
    if len(case_ids) != 1 or next(iter(case_ids)) not in CASE_IDS.values():
        raise ValueError("Source case identity differs")
    kinds = {row.get("source_kind") for row in data}
    if len(kinds) != 1 or next(iter(kinds)) not in (
            "authored_native_request", "synthetic_native_sample"):
        raise ValueError("Unknown or unsealed source provenance")
    speeds = []
    zone_frames = []
    for i, row in enumerate(data):
        if row.get("frame") != i or abs(row.get("time_s", -1) - i / RATE_HZ) > 1e-6:
            raise ValueError("Source frame/time join differs")
        bus = row.get("bus", {})
        zone = row.get("zone", {})
        if bus.get("actor_class") != "motor_bus":
            raise ValueError("Motor bus source absent")
        if zone.get("kind") != "school_crossing_zone" or (
                zone.get("start_x_m"), zone.get("end_x_m")) != (
                    ZONE_START_M, ZONE_END_M):
            raise ValueError("Signed school crossing zone source absent")
        if {child.get("id") for child in row.get("children", [])} != (
                {"child_left", "child_right"}):
            raise ValueError("Child actor source absent")
        values = [bus.get("x_m"), bus.get("y_m"), bus.get("speed_mps")]
        if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
            raise ValueError("Nonfinite or absent bus readback")
        if ZONE_START_M <= bus["x_m"] <= ZONE_END_M:
            zone_frames.append(i)
            speeds.append(bus["speed_mps"])
    if len(zone_frames) < 20:
        raise ValueError("Insufficient measured school-zone occupancy")
    return {"format": "c255451-school-zone-meter-v1",
            "case_id": data[0]["case_id"], "source_kind": data[0]["source_kind"],
            "source_sha256": sha(source), "frames": FRAMES, "duration_s": 30.0,
            "zone_first_frame": zone_frames[0], "zone_last_frame": zone_frames[-1],
            "zone_frames": len(zone_frames), "maximum_zone_speed_mps": max(speeds),
            "frames_above_statutory_25_mph": sum(v > LEGAL_LIMIT_MPS for v in speeds),
            "calendar_and_effective_hours_verified": False,
            "beacon_state_verified": False, "legal_verdict_claimed": False,
            "physical_completion_claimed": False}


def prove(output):
    manifest = build(output)
    output = Path(output)
    meters = {entry["condition"]: meter(output / entry["path"])
              for entry in manifest["entries"]}
    if meters["lower_speed"]["frames_above_statutory_25_mph"] != 0:
        raise AssertionError("Lower-speed diagnostic exceeds stated limit")
    if meters["higher_speed"]["frames_above_statutory_25_mph"] != (
            meters["higher_speed"]["zone_frames"]):
        raise AssertionError("Higher-speed diagnostic does not separate speed")
    negatives = {}
    for label, mutate, expected in (
        ("missing_child", lambda r: r[0]["children"].pop(), "Child actor source absent"),
        ("missing_zone", lambda r: r[0]["zone"].clear(), "Signed school crossing zone source absent"),
        ("missing_bus", lambda r: r[0]["bus"].clear(), "Motor bus source absent"),
        ("forged_original", lambda r: r[0].update(source_kind="original_native"),
         "Unknown or unsealed source provenance")):
        changed = rows(output / "lower_speed.jsonl")
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
            raise AssertionError("Missing/forged source was accepted: " + label)
    return {"format": "c255451-school-zone-diagnostic-proof-v1",
            "manifest": manifest, "meters": meters,
            "negative_rejections": negatives, "diagnostic_only": True,
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
