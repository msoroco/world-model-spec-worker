"""Independent original-source delivery review for the exact red-X lane cases.

Source-shaped CPU diagnostics exercise structure only. Local acceptance requires
sealed Native acquisition, full decode, actual pixels, and a reviewer decision.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

from lane_red_x_meter import measure
from signal_source import map_inventory

ASSIGNMENT = "training__C230247__NRS-484B-307-12b__motor_vehicle_driver"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
REQUIRED = ("native-signal-rows.jsonl", "native-map-readback.xodr", "video_frames.jsonl",
            "trace.jsonl", "capture/evidence.jsonl", *(name + ".mkv" for name in CAMERAS))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1048576), b""):
            digest.update(block)
    return digest.hexdigest()


def source(root, name):
    root = Path(root).resolve()
    path = (root / name).resolve()
    require(root in path.parents and path.is_file(), "Missing original source: " + name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit_structure(attempt, case_id, expected_hashes):
    """Remeasure original streams without accepting diagnostic physical claims."""
    root = Path(attempt).resolve()
    require(case_id in (ASSIGNMENT + "__probe_1",
                        ASSIGNMENT + "__probe_2"),
            "Exact red-X lane case missing")
    require(set(REQUIRED) <= set(expected_hashes), "Original source inventory incomplete")
    for name, expected in expected_hashes.items():
        require(sha(source(root, name)) == expected, "Original source hash changed: " + name)
    config = json.loads(source(root, "config.json").read_text())
    require(config.get("case_id") == case_id and config.get("selected_case_id") == case_id,
            "Selected case identity differs")
    signal_rows = rows(source(root, "native-signal-rows.jsonl"))
    mapping = rows(source(root, "video_frames.jsonl"))
    traces = rows(source(root, "trace.jsonl"))
    evidence = rows(source(root, "capture/evidence.jsonl"))
    require(all(len(seq) == 600 for seq in (signal_rows, mapping, traces, evidence)),
            "Full 600-frame source join required")
    inventory = map_inventory(source(root, "native-map-readback.xodr").read_text())
    require(all(row["signal"]["id"] == inventory["id"] and
                row["signal"]["lane_id"] == inventory["lane_id"] and
                row["signal"]["mount_m"] == inventory["mount_m"] for row in signal_rows),
            "Original lane-control map binding differs")
    for index, (row, frame, trace, event) in enumerate(zip(signal_rows, mapping, traces, evidence)):
        native = row.get("native_frame")
        require(row.get("frame") == index and frame.get("carla_frame") == native and
                frame.get("native_frame") == native and trace.get("frame") == native and
                event.get("original_frame") == native and
                all(frame.get("camera_native_frames", {}).get(name) == native for name in CAMERAS),
                "Original actor, signal and camera frame join differs")
    measured = measure({"frames": signal_rows})
    lane = config["case"]["target_lane_id"]
    entered = measured["first_governed_lane_overlap_frame"] is not None
    require((lane == -1) == entered,
            "Original actor body does not match declared lane entry condition")
    require(measured["red_x_facing_frames"] == 600,
            "Original driver did not face the red-X signal across the source window")
    return {"case_id": case_id, "frames": 600, "target_lane_id": lane,
            "governed_lane_id": inventory["lane_id"],
            "red_x_facing_frames": measured["red_x_facing_frames"],
            "governed_lane_overlap_frames": measured["governed_lane_overlap_frames"],
            "first_governed_lane_overlap_frame": measured["first_governed_lane_overlap_frame"],
            "source_sha256": expected_hashes, "physical_acceptance_claimed": False,
            "legal_verdict": None}


def audit_delivery(attempt, case_id, review):
    root = Path(attempt).resolve()
    require(review.get("case_id") == case_id and review.get("source_kind") == "original_native",
            "Original Native delivery review required")
    structure = audit_structure(root, case_id, review.get("source_sha256", {}))
    result = json.loads(source(root, "result.json").read_text())
    seal = json.loads(source(root, "capture-seal.json").read_text())
    require(result.get("case_id") == case_id and result.get("provenance_kind") in
            ("native", "original_native"), "Original Native result identity differs")
    require(seal.get("provenance_kind") == "native" and seal.get("diagnostic_fixture") is False
            and seal.get("frames") == 600 and
            seal.get("events") == ["capture_finished", "encoders_closed", "restoration_verified"] and
            seal.get("restoration", {}).get("restored") is True,
            "Sealed original acquisition or lifecycle incomplete")
    require(all(seal.get("sources", {}).get(name) == review["source_sha256"][name]
                for name in REQUIRED), "Original capture seal does not bind every source")
    require(review.get("capture_seal_sha256") == sha(root / "capture-seal.json") and
            review.get("result_sha256") == sha(root / "result.json"),
            "Independent review is stale")
    require(review.get("source_sha256", {}).get("raw.mkv") == sha(source(root, "raw.mkv")),
            "Composed original video missing from independent review")
    decode = Path(review.get("source_decode_receipt_path", ""))
    require(decode.is_file() and review.get("source_decode_receipt_sha256") == sha(decode),
            "Full original video decode receipt missing")
    decoded = json.loads(decode.read_text())
    require(decoded.get("passed") is True and decoded.get("frames") == 600 and
            decoded.get("mapping_sha256") == review["source_sha256"]["video_frames.jsonl"] and
            decoded.get("video_sha256") == review["source_sha256"].get("raw.mkv"),
            "Original video bytes or frame map differ from decode")
    output_root = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
    repository = Path(__file__).resolve().parents[3]
    require(repository / ".runtime-work" in output_root.parents,
            "Runtime audit output root must be under .runtime-work")
    sys.path.insert(0, str(repository / "runtime"))
    from scenario_pipeline.worker_exchange.media import verify_receipt
    verify_receipt(source(root, "raw.mkv"), decode, 600,
                   mapping_sha256=review["source_sha256"]["video_frames.jsonl"])
    require(review.get("official_device_source_id") and review.get("signal_asset_source_id") and
            review.get("camera_pixels_confirm_red_x") is True and
            review.get("camera_pixels_confirm_facing_driver") is True and
            review.get("camera_pixels_confirm_actor_lane") is True and
            review.get("physical_motion_confirmed") is True and
            review.get("reviewer_id") and review.get("review_method"),
            "Independent official device, pixel and physical review incomplete")
    auditor = Path(__file__).resolve()
    structure.update({"format": "worker-delivery-audit", "passed": True,
        "job_id": review.get("job_id"), "attempt": review.get("attempt"),
        "recording_id": review.get("recording_id"),
        "source_result_sha256": sha(root / "result.json"),
        "video": "raw.mkv", "video_sha256": review["source_sha256"].get("raw.mkv"),
        "trace": "trace.jsonl", "trace_sha256": review["source_sha256"]["trace.jsonl"],
        "auditor_path": str(auditor), "auditor_sha256": sha(auditor),
        "source_decode_receipt_path": str(decode.resolve()),
        "source_decode_receipt_sha256": sha(decode),
        "source_decode_auditor_sha256": decoded.get("auditor_sha256")})
    require(structure["job_id"] and type(structure["attempt"]) is int and
            structure["attempt"] > 0 and structure["recording_id"],
            "Canonical recording identity absent")
    return structure


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--review", required=True)
    parser.add_argument("--structure-only", action="store_true")
    args = parser.parse_args()
    review = json.loads(Path(args.review).read_text())
    if args.structure_only:
        value = audit_structure(args.attempt, args.case, review.get("source_sha256", {}))
    else:
        value = audit_delivery(args.attempt, args.case, review)
    print(json.dumps(value, sort_keys=True))


if __name__ == "__main__":
    main()
