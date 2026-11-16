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
    if config.get("selected_case_id") != case_id or result.get("case_id") != case_id:
        raise ValueError("Case identity mismatch")
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
        if m.get("speed_source") != "actor.get_velocity" or m.get("subject_actor_id") != context.get("subject_actor_id") or not isinstance(xyz, list) or len(xyz) != 3 or any(type(v) not in (int, float) or not math.isfinite(v) for v in xyz):
            raise ValueError("Original Native velocity missing")
        speed = math.sqrt(sum(v * v for v in xyz))
        if abs(speed - m.get("speed_mps", float("nan"))) > 1e-6 or abs(speed - t.get("speed_mps", float("nan"))) > 1e-6:
            raise ValueError("Original speed disagrees with velocity")
        road_s = m.get("road_s_m")
        if type(road_s) not in (int, float) or not math.isfinite(road_s):
            raise ValueError("Original road coordinate missing")
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
            "source_integrity_passed": True, "camera_decode_passed": True,
            "public_authority_verified": False, "sign_face_verified": False,
            "physical_delivery_ready": False, "legal_acceptance_claimed": False,
            "diagnostic_limit": "Authored sign/zone and reused source graph do not establish posting authority or physical target attainment."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = audit(args.attempt, args.case)
    Path(args.output).write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
