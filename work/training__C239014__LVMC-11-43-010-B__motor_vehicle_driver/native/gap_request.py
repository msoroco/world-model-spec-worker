"""Thirty-second roundabout entry requests and source-only timing checks.

The generated rows are authored requests or synthetic diagnostics, never Native
observations. An original attempt must retain the same fields from CARLA actor
readback before the saved meter can be used for physical review.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent.name
CASE_IDS = {
    "waited_entry": ASSIGNMENT + "__selected_a60a4f45__condition_a",
    "early_entry": ASSIGNMENT + "__selected_a60a4f45__condition_b",
}
RATE_HZ = 20
FRAMES = 600


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def request_row(frame, condition):
    """Pose requests on an entry tangent and counterclockwise circulatory arc."""
    t = frame / RATE_HZ
    entry_time = 17.0 if condition == "waited_entry" else 12.5
    if t < 7:
        ego_x, ego_y, speed, phase = -43 + 4 * t, -20, 4.0, "approach"
    elif t < entry_time:
        ego_x, ego_y, speed, phase = -15, -20, 0.0, "entry_wait"
    else:
        arc = min((t - entry_time) * 0.24, 2.1)
        ego_x = -20 * math.cos(arc)
        ego_y = -20 * math.sin(arc)
        speed, phase = 4.8, "circulation"
    # Each circulating actor is already inside the ring before ego entry.
    lead_arc = (t - 12) * 0.35
    follower_arc = (t - 24) * 0.35
    return {
        "frame": frame, "time_s": t, "source_kind": "authored_native_request",
        "case_id": CASE_IDS[condition], "condition": condition,
        "ego": {"x_m": round(ego_x, 6), "y_m": round(ego_y, 6),
                "speed_mps": speed, "phase": phase},
        "circulating": [
            {"id": "lead", "x_m": round(-20 * math.cos(lead_arc), 6),
             "y_m": round(-20 * math.sin(lead_arc), 6), "speed_mps": 7.0,
             "inside_roundabout": True},
            {"id": "follower", "x_m": round(-20 * math.cos(follower_arc), 6),
             "y_m": round(-20 * math.sin(follower_arc), 6), "speed_mps": 7.0,
             "inside_roundabout": True},
        ],
        "original_native_observed": False, "legal_verdict": None,
    }


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
    return {"format": "c239014-roundabout-entry-request-v1", "rate_hz": RATE_HZ,
            "duration_s": FRAMES / RATE_HZ, "entries": entries,
            "source_kind": "authored_native_request", "native_executed": False}


def meter(source):
    source = Path(source)
    data = rows(source)
    if len(data) != FRAMES:
        raise ValueError("Missing complete 600-frame source sequence")
    case_ids = {row.get("case_id") for row in data}
    if len(case_ids) != 1 or next(iter(case_ids)) not in CASE_IDS.values():
        raise ValueError("Source case identity differs")
    source_kinds = {row.get("source_kind") for row in data}
    if len(source_kinds) != 1 or next(iter(source_kinds)) not in (
            "authored_native_request", "synthetic_native_sample"):
        raise ValueError("Unknown source provenance")
    for i, row in enumerate(data):
        if row.get("frame") != i or abs(row.get("time_s", -1) - i / RATE_HZ) > 1e-6:
            raise ValueError("Source frame/time join differs")
        ego = row.get("ego", {})
        actors = row.get("circulating", [])
        if {actor.get("id") for actor in actors} != {"lead", "follower"}:
            raise ValueError("Missing required circulating actor source")
        if not all(actor.get("inside_roundabout") is True for actor in actors):
            raise ValueError("Circulating actor not inside roundabout")
        values = [ego.get("x_m"), ego.get("y_m"), ego.get("speed_mps")]
        values += [actor.get(key) for actor in actors for key in
                   ("x_m", "y_m", "speed_mps")]
        if any(not isinstance(value, (int, float)) or not math.isfinite(value)
               for value in values):
            raise ValueError("Nonfinite or absent actor readback")
    waits = [row for row in data if row["ego"]["phase"] == "entry_wait"]
    entries = [row for row in data if row["ego"]["phase"] == "circulation"]
    if not waits or not entries or max(row["frame"] for row in waits) >= min(
            row["frame"] for row in entries):
        raise ValueError("No ordered entry wait and circulation")
    first_entry = entries[0]
    entry_frame = first_entry["frame"]
    # The entry conflict neighborhood is a predeclared engineering proxy,
    # not a statutory definition of a sufficient traffic gap.
    near = []
    for row in data:
        close = any(math.dist((actor["x_m"], actor["y_m"]), (-20, 0)) <= 6.0
                    for actor in row["circulating"])
        if close:
            near.append(row["frame"])
    previous = max((frame for frame in near if frame <= entry_frame), default=None)
    following = min((frame for frame in near if frame > entry_frame), default=None)
    if previous is None or following is None:
        raise ValueError("Traffic gap is not bracketed by both actors")
    return {"format": "c239014-entry-gap-meter-v1", "case_id": first_entry["case_id"],
            "source_kind": first_entry["source_kind"], "source_sha256": sha(source),
            "frames": FRAMES, "duration_s": 30.0, "wait_frames": len(waits),
            "first_entry_frame": entry_frame,
            "previous_conflict_frame": previous, "next_conflict_frame": following,
            "previous_gap_s": round((entry_frame - previous) / RATE_HZ, 3),
            "next_gap_s": round((following - entry_frame) / RATE_HZ, 3),
            "traffic_near_at_entry": entry_frame in near,
            "legal_gap_threshold_asserted": False,
            "physical_completion_claimed": False,
            "original_native_observed": False}


def prove(output):
    manifest = build(output)
    output = Path(output)
    meters = {entry["condition"]: meter(output / entry["path"])
              for entry in manifest["entries"]}
    if meters["waited_entry"]["traffic_near_at_entry"]:
        raise AssertionError("Waited diagnostic still overlaps circulating traffic")
    if not meters["early_entry"]["traffic_near_at_entry"]:
        raise AssertionError("Early diagnostic misses circulating traffic")
    negatives = {}
    for condition in ("waited_entry", "early_entry"):
        path = output / (condition + ".jsonl")
        altered = rows(path)
        altered[0]["circulating"].pop()
        negative_path = output / (condition + "-missing-actor.jsonl")
        negative_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n"
                                         for row in altered))
        try:
            meter(negative_path)
        except ValueError as exc:
            if str(exc) != "Missing required circulating actor source":
                raise
            negatives[condition] = str(exc)
        else:
            raise AssertionError("Missing source was accepted")
    altered = rows(output / "waited_entry.jsonl")
    altered.pop(200)
    missing_frame = output / "waited_entry-missing-frame.jsonl"
    missing_frame.write_text("".join(json.dumps(row, sort_keys=True) + "\n"
                                     for row in altered))
    try:
        meter(missing_frame)
    except ValueError as exc:
        if str(exc) != "Missing complete 600-frame source sequence":
            raise
        negatives["missing_frame"] = str(exc)
    else:
        raise AssertionError("Incomplete source was accepted")
    altered = rows(output / "waited_entry.jsonl")
    altered[0]["source_kind"] = "original_native"
    forged = output / "waited_entry-forged-original.jsonl"
    forged.write_text("".join(json.dumps(row, sort_keys=True) + "\n"
                              for row in altered))
    try:
        meter(forged)
    except ValueError as exc:
        if str(exc) != "Unknown source provenance":
            raise
        negatives["forged_original"] = str(exc)
    else:
        raise AssertionError("Unsealed original provenance was accepted")
    return {"format": "c239014-entry-gap-diagnostic-proof-v1",
            "manifest": manifest, "meters": meters, "negative_rejections": negatives,
            "diagnostic_only": True, "native_executed": False,
            "legal_verdict_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("build", "prove", "meter"))
    parser.add_argument("--output")
    parser.add_argument("--source")
    args = parser.parse_args()
    if args.command == "meter":
        result = meter(args.source)
    elif args.command == "build":
        result = build(args.output)
    else:
        result = prove(args.output)
    print(json.dumps(result, indent=2, sort_keys=True))
