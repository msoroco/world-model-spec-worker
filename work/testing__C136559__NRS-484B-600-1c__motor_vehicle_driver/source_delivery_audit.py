"""Independent read-only audit of original posted-speed diagnostic sources."""

import argparse
import hashlib
import json
import math
from pathlib import Path


CAMERAS = ("overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit(attempt, case_id):
    from worker_exchange.media import audit as decode

    attempt = Path(attempt)
    config = json.loads((attempt / "config.json").read_text())
    result = json.loads((attempt / "result.json").read_text())
    context = json.loads((attempt / "sign_context.json").read_text())
    provenance = json.loads((attempt / "fixture-provenance.json").read_text())
    derived = provenance.get("derivation") == "constant-speed x(t), 20 Hz"
    if config.get("selected_case_id") != case_id or result.get("case_id") != case_id:
        raise ValueError("Case identity mismatch")
    completion = result.get("physical_checks", {}).get("maneuver", {})
    if (result.get("provenance_kind") != "synthetic_fixture"
            or result.get("diagnostic_fixture") is not True
            or result.get("physical_acceptance_claimed") is not False
            or completion.get("status") not in ("not_met", "unverified")
            or result.get("maneuver_completed") is not False):
        raise ValueError("Diagnostic physical boundary changed")
    if sorted(result.get("video_references", [])) != sorted(CAMERAS):
        raise ValueError("Four original cameras not bound")
    for name in ("subject_motion.jsonl", "video_frames.jsonl", "sign_context.json"):
        if _sha(attempt / name) != result.get("source_hashes", {}).get(name):
            raise ValueError("Original source hash mismatch: " + name)
    if _sha(attempt / "capture/evidence.jsonl") != result.get("capture_evidence_sha256"):
        raise ValueError("Capture evidence hash mismatch")
    motion = _rows(attempt / "subject_motion.jsonl")
    frames = _rows(attempt / "video_frames.jsonl")
    trace = _rows(attempt / "trace.jsonl")
    if derived and (not provenance.get("seed_sha256") or provenance.get("frames") != len(motion)):
        raise ValueError("Synthetic derivation provenance incomplete")
    if len(motion) < 2 or len(motion) != len(frames) or len(trace) != len(frames):
        raise ValueError("Original frame streams incomplete")
    observed = []
    previous = (-1, -math.inf)
    for index, (m, f, t) in enumerate(zip(motion, frames, trace)):
        frame, time = m.get("frame"), m.get("time_s")
        if type(frame) is not int or type(time) not in (int, float) or frame <= previous[0] or time <= previous[1]:
            raise ValueError("Original motion nonmonotone")
        previous = frame, time
        if f.get("video_frame") != index or f.get("carla_frame") != frame or f.get("time_s") != time or t.get("frame") != frame or t.get("time_s") != time:
            raise ValueError("Original frame join mismatch")
        xyz = m.get("velocity_mps")
        expected_source = "synthetic_kinematic_derivation" if derived else "actor.get_velocity"
        if m.get("speed_source") != expected_source or m.get("subject_actor_id") != context.get("subject_actor_id") or not isinstance(xyz, list) or len(xyz) != 3 or any(type(v) not in (int, float) or not math.isfinite(v) for v in xyz):
            raise ValueError("Original Native velocity missing")
        speed = math.sqrt(sum(v * v for v in xyz))
        if abs(speed - m.get("speed_mps", float("nan"))) > 1e-6 or abs(speed - t.get("speed_mps", float("nan"))) > 1e-6:
            raise ValueError("Original speed disagrees with velocity")
        road_s = m.get("road_s_m")
        if type(road_s) not in (int, float) or not math.isfinite(road_s):
            raise ValueError("Original road coordinate missing")
        if derived:
            x = trace[0]["position_m"][0] + speed * (time - motion[0]["time_s"])
            if (abs(t["position_m"][0] - x) > 1e-6
                    or abs(road_s - x) > 1e-6):
                raise ValueError("Synthetic speed and displacement disagree")
        inside = m.get("road_id") == context.get("governed_road_id") and context["zone_start_s_m"] <= road_s <= context["zone_end_s_m"]
        observed.append({"frame": frame, "in_zone": inside, "speed_mph": speed / 0.44704})
    selected = [row for row in observed if row["in_zone"]]
    if not selected:
        raise ValueError("No original motion in diagnostic signed interval")
    peak = max(row["speed_mph"] for row in selected)
    if abs(peak - result.get("measured_values", {}).get("sampled_peak_in_zone_mph", float("nan"))) > 1e-5:
        raise ValueError("Finalized peak differs from original velocity")
    decoded = {name: decode(attempt / name, len(frames), mapping_sha256=_sha(attempt / "video_frames.jsonl")) for name in CAMERAS}
    if any(not receipt.get("passed", True) for receipt in decoded.values()):
        raise ValueError("Original camera decode failed")
    return {"format": "worker-c136559-source-audit", "case_id": case_id,
            "original_frames": len(frames), "inside_frames": len(selected),
            "outside_frames": len(frames) - len(selected), "sampled_peak_in_zone_mph": peak,
            "posted_limit_mph": context["posted_limit_value"],
            "requested_speed_mph": config["requested_speed_mph"],
            "target_matched": abs(peak - config["requested_speed_mph"]) <= config.get("engineering_target_tolerance_mph", 0.5),
            "physical_completion_status": completion["status"],
            "source_integrity_passed": True, "camera_decode_passed": True,
            "public_authority_verified": False, "sign_face_verified": False,
            "physical_delivery_ready": False, "legal_acceptance_claimed": False,
            "measurement_provenance": ("synthetic_kinematic_derivation" if derived else "actor.get_velocity"),
            "diagnostic_limit": "Authored sign/zone and reused source graph do not establish posting authority or physical target attainment."}


def compare(comparison_id, attempts_index):
    plan = json.loads((Path(__file__).resolve().parent / "case-plan.json").read_text())
    comparison = next((item for item in plan["comparisons"]
                       if item["comparison_id"] == comparison_id), None)
    if comparison is None:
        raise ValueError("Unknown exact comparison")
    rows = json.loads(Path(attempts_index).read_text())
    selected = {}
    for case in comparison["case_ids"]:
        matches = [row for row in rows if row["case"] == case
                   and row["candidate"] == "primary" and row["exit_code"] == 0]
        if len(matches) != 1:
            raise ValueError("Comparison lacks one current primary source: " + case)
        path = Path(matches[0]["output"])
        selected[case] = {"attempt": str(path), "config": json.loads((path / "config.json").read_text()),
                          "context": json.loads((path / "sign_context.json").read_text()),
                          "audit": audit(path, case)}
    values = list(selected.values())
    if any(item["config"]["actor"] != values[0]["config"]["actor"]
           or item["context"]["posted_limit_value"] != values[0]["context"]["posted_limit_value"]
           or item["context"]["governed_road_id"] != values[0]["context"]["governed_road_id"]
           for item in values):
        raise ValueError("Comparison fixed vehicle, road or posting differs")
    if comparison_id == "posted_rate_boundary":
        requested = [item["config"]["requested_speed_mph"] for item in values]
        if requested != sorted(requested) or len(set(requested)) != 3:
            raise ValueError("Boundary targets are not distinct and ordered")
        if any((item["context"]["zone_start_s_m"], item["context"]["zone_end_s_m"])
               != (values[0]["context"]["zone_start_s_m"], values[0]["context"]["zone_end_s_m"])
               for item in values):
            raise ValueError("Boundary zone was not fixed")
        observed_difference = (len({round(item["audit"]["sampled_peak_in_zone_mph"], 5)
                                    for item in values}) == 3)
    elif comparison_id == "governed_portion_extent":
        # A full route eventually leaves both diagnostic intervals. Compare the
        # sourced intervals and the number of frames governed by each, not an
        # all-inside shortcut that only holds for the nine-frame seed.
        intervals = [(item["context"]["zone_start_s_m"], item["context"]["zone_end_s_m"])
                     for item in values]
        observed_difference = (intervals[0] != intervals[1]
                               and values[0]["audit"]["inside_frames"] > values[1]["audit"]["inside_frames"]
                               and values[0]["audit"]["outside_frames"] < values[1]["audit"]["outside_frames"])
        if not observed_difference:
            raise ValueError("Diagnostic inside/outside extent did not differ")
    else:
        raise ValueError("Comparison has no independent implementation")
    return {"format": "worker-c136559-comparison-audit", "comparison_id": comparison_id,
            "case_ids": comparison["case_ids"], "passed": True,
            "fixed_conditions_checked": ["vehicle class", "candidate posted value", "governed road"],
            "diagnostic_difference_observed": observed_difference,
            "source_audits": {case: value["audit"] for case, value in selected.items()},
            "comparison_delivery_ready": False, "physical_acceptance_claimed": False,
            "unresolved": ["public-authority posting and signed highway portion",
                           "actual Native requested-speed attainment", "actual Native camera pixels"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt")
    parser.add_argument("--case")
    parser.add_argument("--comparison")
    parser.add_argument("--attempts-index")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.comparison:
        if not args.attempts_index or args.attempt or args.case:
            raise ValueError("Comparison requires only an attempts index")
        report = compare(args.comparison, args.attempts_index)
    else:
        if not args.attempt or not args.case or args.attempts_index:
            raise ValueError("Exact source audit requires attempt and case")
        report = audit(args.attempt, args.case)
    Path(args.output).write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
