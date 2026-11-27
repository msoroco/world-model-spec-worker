"""Independent original-source audit for a lowered-surface excavation variant."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

CHECKS = ("native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion")
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
SUFFIX_REQUESTS = {"excavation_kind": ("park", "opposite")}


def requests(case: str) -> tuple[str, str]:
    prefix = "training__C135702__NRS-484B-450-1k__motor_vehicle_driver__selected_statutory_"
    if not case.startswith(prefix) or case.removeprefix(prefix) not in SUFFIX_REQUESTS:
        raise ValueError("Exact selected statutory case required")
    return SUFFIX_REQUESTS[case.removeprefix(prefix)]


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inside(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if root.resolve() not in path.parents or not path.is_file():
        raise ValueError("Missing original source: " + relative)
    return path


def check_result(result: dict, case: str) -> None:
    activity, placement = requests(case)
    if (result.get("case_id") != case or result.get("provenance_kind") != "native"
            or result.get("diagnostic_fixture") is not False):
        raise ValueError("Missing exact original Native result")
    measured = result.get("measured_values", {})
    minimum = {"stop": 40, "stand": 300, "park": 400}[activity]
    if (result.get("setup_confirmed") is not True or result.get("maneuver_completed") is not True
            or measured.get("frames") != 600 or measured.get("rest_frames_at_requested_position", 0) < minimum
            or measured.get("activity_request") != activity or measured.get("placement_request") != placement
            or not measured.get("source_sha256")):
        raise ValueError("Original requested activity, placement or measurement incomplete")
    expected = {"exception_authority", "drv.standing_or_parked", "st.obstruction", "rel.bearing",
                "rel.centre_distance", "st.lane_width", "drv.hard_deceleration",
                "kin.velocity", "drv.forced_halt"}
    if expected != {entry.get("name") for entry in result.get("recording_evidence", [])}:
        raise ValueError("Original observation channels incomplete")
    if measured.get("obstruction_kind") != "excavation":
        raise ValueError("Original excavation kind unmeasured")
    if result.get("accepted") is not False or result.get("legal_verdict_claimed") is not False:
        raise ValueError("Recorded-only result preaccepted legal or delivery outcome")


def check_review(review: dict, case: str, sources: dict[str, Path]) -> None:
    activity, placement = requests(case)
    if (review.get("format") != "c135702-obstruction-original-review-v1"
            or review.get("case_id") != case or not review.get("reviewer_id")):
        raise ValueError("Missing independent original obstruction review")
    for name, path in sources.items():
        if review.get(name + "_sha256") != sha(path):
            raise ValueError("Original review source changed: " + name)
    flags = ("road_and_obstruction_reviewed", "excavation_surface_reviewed", "parked_body_reviewed",
             "passing_body_and_response_reviewed", "authority_sources_reviewed",
             "actual_pixels_reviewed")
    if not all(review.get(name) is True for name in flags):
        raise ValueError("Original geometry, traffic, authority or pixels unreviewed")
    if review.get("activity_request") != activity or review.get("placement_request") != placement:
        raise ValueError("Original activity or placement review differs")
    frames = review.get("reviewed_frames")
    if not isinstance(frames, list) or not frames or any(type(index) is not int or index < 0 or index >= 600 for index in frames):
        raise ValueError("Decisive original pixel frames unreviewed")
    if review.get("legal_verdict_claimed") is not False:
        raise ValueError("Original review must not prelabel a legal outcome")


def audit(args) -> dict:
    from scenario_pipeline.worker_exchange import media
    from source_join import check as source_join
    from excavation_runner import reviewed_context, confirm_depressed_surface

    attempt = Path(args.attempt).resolve()
    operations = Path(args.operations).resolve()
    output = Path(args.output).resolve()
    if operations not in Path(__file__).resolve().parents or operations not in output.parents:
        raise ValueError("Independent audit must run in local operations")
    result_path = inside(attempt, "result.json")
    result = json.loads(result_path.read_text())
    check_result(result, args.case)
    names = {"samples": "native_samples.jsonl", "frame_map": "video_frames.jsonl",
             "camera": "camera-frames.jsonl", "inventory": "obstruction-inventory.json",
             "exception_context": "exception-context.json", "trace": args.trace}
    sources = {name: inside(attempt, relative) for name, relative in names.items()}
    reviewed_context(sources["exception_context"], args.case)
    inventory = json.loads(sources["inventory"].read_text())
    if inventory.get("obstruction_kind") != "excavation":
        raise ValueError("Original excavated surface inventory absent")
    confirm_depressed_surface(inventory.get("trench_waypoint_elevations_m", {}))
    if not inventory.get("excavation_design_sources"):
        raise ValueError("Original excavation design source absent")
    source_join(attempt, "original_native")
    check_review(json.loads(inside(attempt, args.review).read_text()), args.case, sources)
    for entry in result["recording_evidence"]:
        inside(attempt, entry["reference"])
    for name in VIEWS:
        inside(attempt, name + ".mkv")
    video = inside(attempt, args.video)
    decode = output.with_name("source-decode-" + args.case.rsplit("__", 1)[-1] + ".json")
    media.audit(video, 600, mapping_sha256=sha(sources["frame_map"]), receipt=decode)
    verified = media.verify_receipt(video, decode, 600,
                                    mapping_sha256=sha(sources["frame_map"]))
    proof = {"format": "worker-delivery-audit", "passed": True,
             "case_id": args.case, "job_id": args.job, "attempt": args.attempt_number,
             "recording_id": args.recording_id, "source_result_sha256": sha(result_path),
             "frames": 600, "video_sha256": sha(video), "trace_sha256": sha(sources["trace"]),
             "checks": {name: True for name in CHECKS},
             "auditor_sha256": sha(Path(__file__).resolve()),
             "source_decode_receipt_sha256": sha(decode),
             "source_decode_auditor_sha256": verified["auditor_sha256"],
             "human_review_sha256": sha(inside(attempt, args.review))}
    output.write_text(json.dumps(proof, indent=2) + "\n")
    return proof


def selftest(case: str, negative: bool) -> dict:
    activity, placement = requests(case)
    sample = {"case_id": case, "provenance_kind": "native", "diagnostic_fixture": False,
              "setup_confirmed": True, "maneuver_completed": True,
              "accepted": False, "legal_verdict_claimed": False,
              "measured_values": {"frames": 600, "rest_frames_at_requested_position": 450,
                                  "activity_request": activity, "placement_request": placement,
                                  "obstruction_kind": "excavation",
                                  "source_sha256": "a" * 64},
              "recording_evidence": [{"name": name} for name in (
                  "exception_authority", "drv.standing_or_parked", "st.obstruction", "rel.bearing",
                  "rel.centre_distance", "st.lane_width", "drv.hard_deceleration",
                  "kin.velocity", "drv.forced_halt")]}
    if negative:
        sample["provenance_kind"] = "synthetic_fixture"
        check_result(sample, case)
        raise AssertionError("Synthetic source accepted")
    check_result(sample, case)
    for key, value in (("maneuver_completed", False), ("measured_values", {}),
                       ("recording_evidence", []), ("legal_verdict_claimed", True)):
        changed = json.loads(json.dumps(sample))
        changed[key] = value
        try:
            check_result(changed, case)
        except ValueError:
            pass
        else:
            raise AssertionError("Damaged result accepted: " + key)
    return {"case_id": case, "source_predicates_tested": True,
            "original_capture_attested": False, "legal_verdict_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--negative", action="store_true")
    parser.add_argument("--attempt")
    parser.add_argument("--operations")
    parser.add_argument("--output")
    parser.add_argument("--trace", default="converted/trace.json")
    parser.add_argument("--video", default="primary.mkv")
    parser.add_argument("--review", default="obstruction-review.json")
    parser.add_argument("--job", type=int)
    parser.add_argument("--attempt-number", type=int)
    parser.add_argument("--recording-id")
    args = parser.parse_args()
    print(json.dumps(selftest(args.case, args.negative) if args.self_test else audit(args)))
