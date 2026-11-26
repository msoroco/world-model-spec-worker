"""Independent source-bound audit for a future original Native delivery.

The audit request is a local review record. All referenced sources must be inside
one attempt and are rehashed. A successful CPU fixture test is not an acceptance.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

from observed_speed import CASES, FRAMES, RATE, measure

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1048576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def within(root, name):
    root = Path(root).resolve()
    target = (root / name).resolve()
    require(root in target.parents and target.is_file(), "Missing or escaping original source: " + name)
    return target


def audit_structure(attempt, request):
    """CPU-testable source integrity and joins; no physical outcome claim."""
    root = Path(attempt).resolve()
    case = request.get("case_id")
    require(case in CASES, "Exact selected case missing")
    require(request.get("source_kind") == "original_native_observation",
            "Original Native delivery required")
    source_hashes = request.get("source_sha256", {})
    required = {"result.json", "capture-seal.json", "video_frames.jsonl", "emergency_observations.jsonl",
                "trace.json", "primary.mkv", "pixel-review.json",
                *(name + ".mkv" for name in VIEWS)}
    require(required <= set(source_hashes), "Original source inventory incomplete")
    for name, expected in source_hashes.items():
        require(sha(within(root, name)) == expected, "Original source hash changed: " + name)
    result = json.loads(within(root, "result.json").read_text())
    require(result.get("case_id") == case and result.get("provenance_kind") ==
            "original_native", "Sealed Native result identity differs")
    require(within(root, "capture-seal.json").is_file(), "Native capture seal missing")
    measurement = measure(within(root, "emergency_observations.jsonl"))
    require(measurement["case_id"] == case and measurement["frames"] == FRAMES,
            "Original selected motion measurement incomplete")
    mapping = [json.loads(line) for line in within(root, "video_frames.jsonl").read_text().splitlines()]
    require(len(mapping) == FRAMES, "Original frame map duration differs")
    for index, row in enumerate(mapping):
        require(row.get("video_frame") == index and abs(row.get("time_s", -1) - index / RATE) < 1e-6,
                "Original frame and time join differs")
    trace = json.loads(within(root, "trace.json").read_text())
    require(len(trace.get("scenes", [])) == FRAMES and all(
        scene.get("t") == round(index * 1000 / RATE)
        for index, scene in enumerate(trace["scenes"])), "Core scene timestamp join differs")
    require(".runtime-work" in os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", ""),
            "SCENARIO_PIPELINE_OUTPUT_ROOT must be under .runtime-work")
    repo = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo / "runtime"))
    from scenario_pipeline.worker_exchange.media import verify_receipt
    decode_path = Path(request.get("source_decode_receipt_path", "")).resolve()
    scratch = repo / ".runtime-work"
    require(decode_path.is_file() and scratch in decode_path.parents,
            "Source decode receipt must live in independent local scratch")
    verify_receipt(within(root, "primary.mkv"), decode_path,
                   FRAMES, mapping_sha256=source_hashes["video_frames.jsonl"])
    review = json.loads(within(root, "pixel-review.json").read_text())
    require(review.get("source_video_sha256") == source_hashes["primary.mkv"]
            and review.get("camera_visibility_confirmed") is True
            and review.get("qualifying_flashing_pixels_confirmed") is True
            and review.get("moving_vehicle_pixels_confirmed") is True
            and review.get("reviewer") and review.get("review_method"),
            "Original camera pixel review missing")
    require(request.get("authorization_source_id")
            and request.get("flashing_equipment_source_id")
            and request.get("officer_direction_source_id")
            and request.get("road_context_source_id")
            and request.get("weather_context_source_id"),
            "Independent source qualification missing")
    require(request.get("officer_directed") is False,
            "Officer-directed exception requires separate branch review")
    physical = request.get("physical_review", {})
    require(physical.get("source_result_sha256") == source_hashes["result.json"]
            and physical.get("native_capture_seal_sha256") == source_hashes["capture-seal.json"]
            and physical.get("setup_confirmed") is True
            and physical.get("behavior_confirmed") is True
            and physical.get("maneuver_confirmed") is True
            and physical.get("reviewer") and physical.get("review_method"),
            "Independent physical completion review missing")
    return {"case_id": case, "frames": FRAMES,
            "source_hashes": source_hashes,
            "checks": {name: True for name in ("native_source", "all_participants",
                                               "time_join", "full_video_decode",
                                               "actual_pixels", "physical_completion")},
            "speed_measurement": measurement,
            "reasonable_and_proper_legally_determined": False,
            "legal_outcome_claimed": False}


def audit(attempt, request):
    value = audit_structure(attempt, request)
    root = Path(attempt).resolve()
    seal = json.loads(within(root, "capture-seal.json").read_text())
    original_names = {"video_frames.jsonl", "emergency_observations.jsonl",
                      "primary.mkv", *(name + ".mkv" for name in VIEWS)}
    require(seal.get("format") == "worker-sealed-capture"
            and seal.get("provenance_kind") == "native"
            and seal.get("diagnostic_fixture") is False
            and seal.get("frames") == FRAMES
            and seal.get("restoration", {}).get("restored") is True
            and set(seal.get("events", [])) ==
            {"capture_finished", "encoders_closed", "restoration_verified"}
            and all(code == 0 for code in seal.get("encoder_exit_codes", {}).values())
            and all(seal.get("sources", {}).get(name) == value["source_hashes"][name]
                    for name in original_names)
            and not json.loads(within(root, "result.json").read_text()).get("cpu_harness_only"),
            "Native capture seal does not verify original acquisition")
    require(request.get("auditor_mode") == "original_independent_review",
            "Synthetic or delegated review cannot establish delivery")
    require(request.get("job_id") and type(request.get("attempt")) is int
            and request["attempt"] > 0 and request.get("recording_id"),
            "Canonical job, attempt and recording identity missing")
    decode_path = Path(request["source_decode_receipt_path"]).resolve()
    decode = json.loads(decode_path.read_text())
    auditor = Path(__file__).resolve()
    value.update(format="worker-delivery-audit", passed=True,
                 job_id=request["job_id"], attempt=request["attempt"],
                 recording_id=request["recording_id"],
                 source_result_sha256=value["source_hashes"]["result.json"],
                 video="primary.mkv", video_sha256=value["source_hashes"]["primary.mkv"],
                 trace="trace.json", trace_sha256=value["source_hashes"]["trace.json"],
                 auditor_path=str(auditor), auditor_sha256=sha(auditor),
                 source_decode_receipt_path=str(decode_path),
                 source_decode_receipt_sha256=sha(decode_path),
                 source_decode_auditor_sha256=decode["auditor_sha256"])
    return value


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--review", required=True)
    args = parser.parse_args()
    record = json.loads(Path(args.review).read_text())
    require(args.case == record.get("case_id"), "Exact selected case differs")
    print(json.dumps(audit(args.attempt, record), indent=2, sort_keys=True))
