"""Independent original Native safety-zone source and completion audit."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

CHECKS = ("native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion")
SOURCES = ("zone_raw.json", "context-survey.json", "video_frames.jsonl",
           "trace.jsonl", "capture/evidence.jsonl", "road.xodr", "authored-road.xodr")
VIDEOS = ("overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def check_result(result, case):
    if (result.get("case_id") != case or result.get("provenance_kind") != "native" or
            result.get("diagnostic_fixture") is not False):
        raise ValueError("Missing original source: exact Native result")
    if (result.get("setup_confirmed") is not True or
            result.get("maneuver_completed") is not True or
            result.get("physical_checks", {}).get("maneuver", {}).get("status") != "met"):
        raise ValueError("Original safety-zone motion or sustained rest incomplete")
    measured = result.get("measured_values", {})
    if measured.get("frames") != 600 or not result.get("target_checks"):
        raise ValueError("Missing original 600-frame safety-zone footprint measurement")
    if result.get("accepted") is not False or result.get("physical_acceptance_claimed") is True:
        raise ValueError("Saved finalizer preaccepted physical or legal outcome")


def check_review(survey, case, hashes):
    if (survey.get("case_id") != case or survey.get("review_kind") != "original_source_review" or
            not survey.get("independent_reviewer") or survey.get("actual_pixels_reviewed") is not True):
        raise ValueError("Missing independent original zone review")
    if (survey.get("zone_raw_sha256") != hashes["zone_raw.json"] or
            survey.get("road_sha256") != hashes["road.xodr"] or
            survey.get("video_frames_sha256") != hashes["video_frames.jsonl"] or
            survey.get("video_sha256") != {name: hashes[name] for name in VIDEOS}):
        raise ValueError("Original review differs from sealed zone, road or cameras")
    required = ("safety_zone_official_status", "zone_marker_readback",
                "adjacent_curb_readback", "halt_purpose", "traffic_conflict",
                "applicable_law_direction", "officer_direction", "device_direction")
    if any(survey.get(key) is None for key in required):
        raise ValueError("Original safety-zone or exception context unreviewed")


def audit(args):
    root, output = Path(args.attempt).resolve(), Path(args.output).resolve()
    if output == root or root in output.parents:
        raise ValueError("Independent audit output must be outside original capture")
    result = read(root / "result.json")
    check_result(result, args.case)
    seal = read(root / "capture-seal.json")
    if (seal.get("format") != "worker-sealed-capture" or
            seal.get("provenance_kind") != "native" or
            not seal.get("restoration", {}).get("restored") or
            seal.get("frames") != 600):
        raise ValueError("Original Native capture seal invalid")
    hashes = {name: sha(root / name) for name in (*SOURCES, *VIDEOS)}
    for name, digest in hashes.items():
        if name != "context-survey.json" and seal.get("sources", {}).get(name) != digest:
            raise ValueError("Original sealed source changed: " + name)
    check_review(read(root / "context-survey.json"), args.case, hashes)
    frames = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
    trace = [json.loads(line) for line in (root / "trace.jsonl").read_text().splitlines()]
    raw = read(root / "zone_raw.json").get("frames", [])
    if len(frames) != len(trace) or len(trace) != len(raw) or len(raw) != 600:
        raise ValueError("Original source frame count differs")
    for index, (frame, row, sample) in enumerate(zip(frames, trace, raw)):
        if (frame.get("video_frame") != index or row.get("frame") != frame.get("carla_frame") or
                sample.get("native_frame") != frame.get("carla_frame") or
                abs(row["time_s"] - frame["time_s"]) > 1e-6):
            raise ValueError("Original zone trace and camera time join differs")
    runtime = Path(__file__).resolve().parents[2] / "runtime"
    sys.path[:0] = [str(runtime), str(runtime / "scenario_pipeline")]
    from scenario_pipeline.worker_exchange import media
    receipts = {}
    for name in VIDEOS:
        receipt_path = output.with_name(output.stem + "-" + name + ".json")
        media.audit(root / name, 600, mapping_sha256=hashes["video_frames.jsonl"],
                    receipt=receipt_path)
        receipts[name] = {"path": str(receipt_path), "sha256": sha(receipt_path)}
    proof = {"format": "worker-delivery-audit", "passed": True, "case_id": args.case,
             "job_id": args.job, "attempt": args.attempt_number,
             "recording_id": args.recording_id, "frames": 600,
             "source_result_sha256": sha(root / "result.json"),
             "checks": {name: True for name in CHECKS},
             "source_sha256": hashes, "decode_receipts": receipts,
             "auditor_path": str(Path(__file__).resolve()),
             "auditor_sha256": sha(Path(__file__).resolve()),
             "physical_or_legal_acceptance_claimed": False}
    output.write_text(json.dumps(proof, indent=2) + "\n")
    return proof


def selftest(case, negative):
    sample = {"case_id": case, "provenance_kind": "native", "diagnostic_fixture": False,
              "setup_confirmed": True, "maneuver_completed": True,
              "physical_checks": {"maneuver": {"status": "met"}},
              "measured_values": {"frames": 600}, "target_checks": [{"matched": True}],
              "accepted": False, "physical_acceptance_claimed": False}
    if negative:
        sample["provenance_kind"] = "synthetic_fixture"
        check_result(sample, case)
        raise AssertionError("Synthetic source accepted")
    check_result(sample, case)
    hashes = {name: name for name in (*SOURCES, *VIDEOS)}
    survey = {"case_id": case, "review_kind": "original_source_review",
              "independent_reviewer": "CPU predicate test", "actual_pixels_reviewed": True,
              "zone_raw_sha256": hashes["zone_raw.json"],
              "road_sha256": hashes["road.xodr"],
              "video_frames_sha256": hashes["video_frames.jsonl"],
              "video_sha256": {name: hashes[name] for name in VIDEOS}}
    for key in ("safety_zone_official_status", "zone_marker_readback",
                "adjacent_curb_readback", "halt_purpose", "traffic_conflict",
                "applicable_law_direction", "officer_direction", "device_direction"):
        survey[key] = "reviewed in CPU predicate"
    check_review(survey, case, hashes)
    changed = dict(survey, road_sha256="changed")
    try:
        check_review(changed, case, hashes)
    except ValueError:
        pass
    else:
        raise AssertionError("Changed original review source accepted")
    return {"case_id": case, "source_predicates_tested": True,
            "original_capture_attested": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--negative", action="store_true")
    parser.add_argument("--attempt")
    parser.add_argument("--output")
    parser.add_argument("--job", type=int)
    parser.add_argument("--attempt-number", type=int)
    parser.add_argument("--recording-id")
    args = parser.parse_args()
    print(json.dumps(selftest(args.case, args.negative) if args.self_test else audit(args)))
