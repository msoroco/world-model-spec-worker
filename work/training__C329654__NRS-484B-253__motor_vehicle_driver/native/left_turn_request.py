"""Thirty-second left-turn yield requests and source-timed diagnostics."""
import argparse
import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = Path(__file__).resolve().parent.parent.name
CASES = {"yield_then_turn": ASSIGNMENT + "__selected_d457f261__condition_a",
         "turn_before_pass": ASSIGNMENT + "__selected_d457f261__condition_b"}
RELEASE_S = {"yield_then_turn": 15.0, "turn_before_pass": 9.0}
FRAMES = 600
RATE_HZ = 20


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def request_row(frame, condition):
    t = frame / RATE_HZ
    release = RELEASE_S[condition]
    if t < 5:
        phase, progress, speed = "approach", 0.0, 4.0
    elif t < release:
        phase, progress, speed = "yield_wait", 0.0, 0.0
    else:
        phase, progress, speed = "left_turn", min(1, (t-release)/4), 4.0
    return {"case_id": CASES[condition], "condition": condition,
            "frame": frame, "time_s": t, "source_kind": "authored_native_request",
            "ego": {"phase": phase, "left_turn_progress": progress,
                    "speed_mps": speed, "left_indicator_requested": True,
                    "inside_intersection": t >= 5},
            "oncoming": {"actor_id": "opposite_vehicle",
                         "distance_to_conflict_m": round(100-8*t, 6),
                         "speed_mps": 8.0, "approach_lane_opposite": True},
            "conflict": {"point": "intersection_center",
                         "oncoming_pass_time_s": 12.5},
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
    return {"format": "c329654-left-turn-request-v1", "entries": entries,
            "duration_s": 30, "rate_hz": RATE_HZ, "native_executed": False}


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
    for i, row in enumerate(data):
        if row.get("frame") != i or abs(row.get("time_s", -1)-i/RATE_HZ) > 1e-6:
            raise ValueError("Source frame/time join differs")
        ego, opposite = row.get("ego", {}), row.get("oncoming", {})
        if ego.get("left_indicator_requested") is not True or (
                ego.get("inside_intersection") is not True and i >= 100):
            raise ValueError("Left-turn signal/intersection source absent")
        if opposite.get("actor_id") != "opposite_vehicle" or (
                opposite.get("approach_lane_opposite") is not True):
            raise ValueError("Opposing vehicle source absent")
        values = [ego.get("speed_mps"), ego.get("left_turn_progress"),
                  opposite.get("speed_mps"), opposite.get("distance_to_conflict_m")]
        if any(not isinstance(v, (int,float)) or not math.isfinite(v) for v in values):
            raise ValueError("Nonfinite or absent actor readback")
    start = next((r for r in data if r["ego"]["phase"] == "left_turn"), None)
    if start is None:
        raise ValueError("Left turn never starts")
    passed = next((r for r in data if r["oncoming"]["distance_to_conflict_m"] <= 0), None)
    if passed is None:
        raise ValueError("Opposing conflict passage absent")
    waits = [r for r in data if r["ego"]["phase"] == "yield_wait"]
    if not waits or max(r["frame"] for r in waits) >= start["frame"]:
        raise ValueError("Yield wait source order differs")
    return {"format": "c329654-left-turn-meter-v1", "case_id": data[0]["case_id"],
            "source_sha256": sha(source), "source_kind": data[0]["source_kind"],
            "frames": FRAMES, "duration_s": 30,
            "turn_start_frame": start["frame"],
            "oncoming_conflict_pass_frame": passed["frame"],
            "wait_frames": len(waits),
            "oncoming_passed_before_turn": passed["frame"] < start["frame"],
            "oncoming_ttc_at_turn_start_s": max(0, round(
                start["oncoming"]["distance_to_conflict_m"] / 8, 3)),
            "legal_immediate_hazard_threshold_asserted": False,
            "physical_completion_claimed": False, "legal_verdict_claimed": False}


def prove(output):
    manifest = build(output)
    output = Path(output)
    meters = {e["condition"]: meter(output / e["path"])
              for e in manifest["entries"]}
    if not meters["yield_then_turn"]["oncoming_passed_before_turn"]:
        raise AssertionError("Yielded diagnostic turns before opposing passage")
    if meters["turn_before_pass"]["oncoming_passed_before_turn"]:
        raise AssertionError("Early diagnostic waits past opposing passage")
    negatives = {}
    for label, mutate, expected in (
        ("missing_opposite", lambda r: r[0]["oncoming"].clear(),
         "Opposing vehicle source absent"),
        ("missing_signal", lambda r: r[0]["ego"].update(left_indicator_requested=False),
         "Left-turn signal/intersection source absent"),
        ("forged_original", lambda r: r[0].update(source_kind="original_native"),
         "Unknown or unsealed source provenance")):
        changed = rows(output / "yield_then_turn.jsonl")
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
    return {"format": "c329654-left-turn-diagnostic-proof-v1",
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
