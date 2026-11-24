"""Independent saved-source gate for parked-lamp delivery.

The reviewer supplies a separate source-hashed pixel and physical-completion
record. This script verifies bindings and decodes the promoted video. A CPU
fixture may exercise the checker but cannot set a physical acceptance claim.
"""

import argparse
import hashlib
import json
from pathlib import Path

from worker_exchange.media import audit as decode_video

from parked_lamps import ASSIGNMENT, require

CHECKS = ("native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def contained(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    require(path.is_relative_to(root) and path.is_file(), "missing contained source: " + str(relative))
    return path


def review(attempt, case_id, review_path, video, trace, decode_receipt, *, diagnostic=False):
    root = Path(attempt).resolve()
    require(case_id.startswith(ASSIGNMENT + "__"), "wrong delivery case")
    result_path = contained(root, "result.json")
    result = json.loads(result_path.read_text())
    require(result.get("recording_description") and result.get("trace_reference") and
            result.get("video_frame_map_reference"), "Native result incomplete")
    seal = json.loads(contained(root, "capture-seal.json").read_text())
    require(seal.get("format") == "worker-sealed-capture" and seal.get("provenance_kind") == "native" and
            seal.get("frames") == 900 and seal.get("restoration", {}).get("restored") is True and
            seal.get("events") == ["capture_finished", "encoders_closed", "restoration_verified"],
            "Native capture closure incomplete")
    require(seal.get("sources", {}).get("result.json") == sha(result_path),
            "sealed Native result changed")
    for name, expected in seal["sources"].items():
        require(sha(contained(root, name)) == expected, "sealed original changed: " + name)
    trace_path = contained(root, trace)
    video_path = contained(root, video)
    mapping = contained(root, result["video_frame_map_reference"])
    require(len(mapping.read_text().splitlines()) == 900, "original frame count differs")
    core = json.loads(trace_path.read_text())
    scenes = core.get("scenes", [])
    require(len(scenes) == 900, "Core trace frame count differs")
    for index, line in enumerate(mapping.read_text().splitlines()):
        frame = json.loads(line)
        require(frame.get("video_frame") == index and scenes[index].get("t") == round(frame["time_s"] * 1000),
                "original frame/Core time join differs")
    source_decode = decode_video(video_path, 900, mapping_sha256=sha(mapping), receipt=decode_receipt)
    pixel = json.loads(Path(review_path).read_text())
    require(pixel.get("case_id") == case_id and pixel.get("source_result_sha256") == sha(result_path) and
            pixel.get("video_sha256") == sha(video_path) and pixel.get("frame_map_sha256") == sha(mapping),
            "independent pixel review source binding differs")
    require(pixel.get("reviewer") and pixel.get("method") and pixel.get("source_frames_reviewed"),
            "independent pixel review incomplete")
    require(pixel.get("front_white_or_amber_500ft") in ("observed", "not_observed", "unknown") and
            pixel.get("rear_red_500ft") in ("observed", "not_observed", "unknown") and
            pixel.get("revelation_1000ft") in ("observed", "not_observed", "unknown") and
            pixel.get("traffic_side_installation") in ("observed", "not_observed", "unknown"),
            "independent statutory pixel observations missing")
    require(pixel.get("parked_interval_verified") is True,
            "independent physical completion missing")
    if not diagnostic:
        require(pixel.get("diagnostic_fixture") is False and pixel.get("actual_original_pixels") is True,
                "physical original-pixel review required")
        require(all(pixel[name] != "unknown" for name in
                    ("front_white_or_amber_500ft", "rear_red_500ft",
                     "revelation_1000ft", "traffic_side_installation")),
                "independent original-pixel observations remain unknown")
    return {"format": "worker-delivery-audit", "case_id": case_id,
            "passed": not diagnostic, "checks": {key: True for key in CHECKS},
            "source_result_sha256": sha(result_path), "video": video, "video_sha256": sha(video_path),
            "trace": trace, "trace_sha256": sha(trace_path), "frames": 900,
            "source_decode_receipt_path": str(Path(decode_receipt).resolve()),
            "source_decode_receipt_sha256": sha(decode_receipt),
            "source_decode_auditor_sha256": source_decode["auditor_sha256"],
            "pixel_review_sha256": sha(review_path),
            "physical_acceptance_claimed": False, "legal_verdict": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--review", required=True)
    parser.add_argument("--video", required=True)
    parser.add_argument("--trace", required=True)
    parser.add_argument("--decode-receipt", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--attempt-number", type=int, required=True)
    parser.add_argument("--recording-id", required=True)
    args = parser.parse_args()
    result = review(args.attempt, args.case, args.review, args.video, args.trace,
                    args.decode_receipt)
    result.update(job_id=args.job_id, attempt=args.attempt_number,
                  recording_id=args.recording_id, auditor_path=str(Path(__file__).resolve()),
                  auditor_sha256=sha(__file__))
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
