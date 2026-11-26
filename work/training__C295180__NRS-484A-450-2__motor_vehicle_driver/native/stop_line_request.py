"""Thirty-second stop-line requests and source-only diagnostic meter."""
import argparse
import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = 'training__C295180__NRS-484A-450-2__motor_vehicle_driver'
CASES = {"full_stop": ASSIGNMENT + "__selected_ef239a06__condition_a",
         "rolling": ASSIGNMENT + "__selected_ef239a06__condition_b"}
FRAMES = 600
RATE_HZ = 20
STOP_LINE_X_M = 0.0
EGO_FRONT_OFFSET_M = 2.0


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def motion(t, condition):
    if t <= 5:
        return -50 + 8 * t, 8.0
    if condition == "full_stop":
        if t < 6.875:
            u = t - 5
            return -10 + 8 * u - 0.5 * (8 / 1.875) * u * u, 8 - (8 / 1.875) * u
        if t < 9:
            return -2.5, 0.0
        if t < 13:
            u = t - 9
            return -2.5 + u * u, 2 * u
        return 13.5 + 8 * (t - 13), 8.0
    if t < 7:
        u = t - 5
        return -10 + 8 * u - 1.5 * u * u, 8 - 3 * u
    return 0 + 2 * (t - 7), 2.0


def request_row(frame, condition):
    t = frame / RATE_HZ
    x, speed = motion(t, condition)
    return {"case_id": CASES[condition], "condition": condition,
            "frame": frame, "time_s": t, "source_kind": "authored_native_request",
            "ego": {"center_x_m": round(x, 6), "center_y_m": 0.0,
                    "front_x_m": round(x + EGO_FRONT_OFFSET_M, 6),
                    "speed_mps": round(speed, 6)},
            "intersection": {"layout": "t_intersection", "near_boundary_x_m": 5.0},
            "control": {"stop_sign_present": True, "governs_ego_lane": True,
                        "near_crosswalk_present": False, "marked_stop_line_x_m": STOP_LINE_X_M},
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
    return {"format": "c295180-stop-line-request-v1", "entries": entries,
            "rate_hz": RATE_HZ, "duration_s": 30.0, "native_executed": False}


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
        if row.get("frame") != i or abs(row.get("time_s", -1) - i / RATE_HZ) > 1e-6:
            raise ValueError("Source frame/time join differs")
        control = row.get("control", {})
        if not (control.get("stop_sign_present") is True and
                control.get("governs_ego_lane") is True and
                control.get("near_crosswalk_present") is False and
                control.get("marked_stop_line_x_m") == STOP_LINE_X_M):
            raise ValueError("Applicable stop sign and line source absent")
        ego = row.get("ego", {})
        values = [ego.get("center_x_m"), ego.get("front_x_m"), ego.get("speed_mps")]
        if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
            raise ValueError("Nonfinite or absent ego readback")
        if abs(ego["front_x_m"] - ego["center_x_m"] - EGO_FRONT_OFFSET_M) > 1e-4:
            raise ValueError("Ego body/center source differs")
    crossing = next((r for r in data if r["ego"]["front_x_m"] >= STOP_LINE_X_M), None)
    if crossing is None:
        raise ValueError("No stop-line crossing in source window")
    prior = [r for r in data if r["frame"] < crossing["frame"]]
    stopped = [r for r in prior if r["ego"]["front_x_m"] < STOP_LINE_X_M and
               r["ego"]["speed_mps"] <= 0.1]
    runs = 0
    longest = 0
    stopped_frames = {r["frame"] for r in stopped}
    for i in range(crossing["frame"]):
        runs = runs + 1 if i in stopped_frames else 0
        longest = max(longest, runs)
    return {"format": "c295180-stop-line-meter-v1", "case_id": data[0]["case_id"],
            "source_kind": data[0]["source_kind"], "source_sha256": sha(source),
            "frames": FRAMES, "duration_s": 30.0,
            "first_front_crossing_frame": crossing["frame"],
            "pre_crossing_stopped_frames": len(stopped),
            "longest_pre_crossing_stop_frames": longest,
            "engineering_full_stop_span_frames": 20,
            "full_stop_before_line_diagnostic": longest >= 20,
            "legal_verdict_claimed": False, "physical_completion_claimed": False}


def prove(output):
    manifest = build(output)
    output = Path(output)
    meters = {e["condition"]: meter(output / e["path"])
              for e in manifest["entries"]}
    if not meters["full_stop"]["full_stop_before_line_diagnostic"]:
        raise AssertionError("Authored full stop was not measured")
    if meters["rolling"]["full_stop_before_line_diagnostic"]:
        raise AssertionError("Authored rolling entry was measured as full stop")
    negatives = {}
    for label, mutate, expected in (
        ("missing_sign", lambda r: r[0]["control"].update(stop_sign_present=False),
         "Applicable stop sign and line source absent"),
        ("missing_line", lambda r: r[0]["control"].pop("marked_stop_line_x_m"),
         "Applicable stop sign and line source absent"),
        ("forged_original", lambda r: r[0].update(source_kind="original_native"),
         "Unknown or unsealed source provenance")):
        changed = rows(output / "full_stop.jsonl")
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
            raise AssertionError("Missing/forged source accepted: " + label)
    return {"format": "c295180-stop-line-diagnostic-proof-v1",
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
