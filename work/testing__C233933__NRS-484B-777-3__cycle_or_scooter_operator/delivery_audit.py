"""Independent source, pixel and physical review for an exact saved pass.

The diagnostic mode tests rejection logic. Only a sealed original Native
attempt can yield a source-verified delivery result. Legal conclusions remain
outside this audit.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from package_spec import AID, CAMERA_NAMES


def need(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decoded_frame_sha(video, frame):
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-nostdin", "-i", str(video), "-vf",
         "select=eq(n\\," + str(frame) + ")", "-frames:v", "1",
         "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
        check=True, capture_output=True)
    need(result.stdout, "reviewed original frame has no decoded pixels")
    return hashlib.sha256(result.stdout).hexdigest()


def assess(case, capture, review, physical, *, diagnostic=False, attempt=None):
    need(case.startswith(AID + "__"), "exact delivery case required")
    need(capture.get("case_id") == case and capture.get("frame_count") == 900 and
         capture.get("full_decode") is True, "original full capture audit missing")
    bindings = capture.get("source_bindings", {})
    need(set(name + ".mkv" for name in CAMERA_NAMES) <= set(bindings),
         "four original video sources missing")
    need(review.get("case_id") == case and
         review.get("capture_receipt_sha256") == capture.get("receipt_sha256"),
         "independent pixel review has wrong source")
    views = review.get("views")
    need(isinstance(views, dict) and set(views) == set(CAMERA_NAMES),
         "independent pixel review missing four views")
    need(review.get("legal_abreast_judgment") is None and
         review.get("legal_exclusive_use_judgment") is None and
         review.get("legal_moped_inclusion_judgment") is None,
         "delivery audit cannot assert legal judgment")
    for name in CAMERA_NAMES:
        item = views[name]
        need(item.get("video_sha256") == bindings[name + ".mkv"] and
             isinstance(item.get("reviewer"), str) and item["reviewer"].strip(),
             "independent pixel review missing: " + name)
        samples = item.get("samples")
        need(isinstance(samples, list) and samples,
             "independent pixel review missing: " + name)
        for sample in samples:
            frame = sample.get("frame")
            need(type(frame) is int and 0 <= frame < 900 and
                 sample.get("all_riders_visible") is True and
                 sample.get("surface_visible") is True and
                 sample.get("formation_visible") is True and
                 isinstance(sample.get("decoded_rgb_sha256"), str) and
                 len(sample["decoded_rgb_sha256"]) == 64,
                 "independent participant pixel review incomplete: " + name)
            if not diagnostic:
                need(decoded_frame_sha(Path(attempt) / (name + ".mkv"), frame) ==
                     sample["decoded_rgb_sha256"],
                     "independent pixel source changed: " + name)
    maneuver = physical.get("physical_checks", {}).get("maneuver", {})
    need(physical.get("case_id") == case and physical.get("maneuver_completed") is True and
         maneuver.get("status") == "met" and maneuver.get("sources") and
         physical.get("realized_observables"),
         "source-measured physical completion missing")
    if not diagnostic:
        need(physical.get("provenance_kind") == "native" and
             physical.get("diagnostic_fixture") is False,
             "Native physical provenance required")
    return {"format": "rider-formation-independent-delivery-audit", "case_id": case,
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "capture_receipt_sha256": capture["receipt_sha256"],
            "pixel_review_sha256": None,
            "source_verified": not diagnostic, "diagnostic_fixture": diagnostic,
            "canonical_acceptance": False, "legal_verdict": None}


def audit(case, attempt, review_path, physical_path, *, diagnostic_fixture=False):
    attempt = Path(attempt).resolve()
    review_path = Path(review_path).resolve()
    physical_path = Path(physical_path).resolve()
    need(review_path.is_file(), "independent pixel review missing")
    need(physical_path.is_file(), "physical result missing")
    if diagnostic_fixture:
        capture_path = attempt / "diagnostic-capture-audit.json"
        need(capture_path.is_file(), "diagnostic capture protocol missing")
        capture = json.loads(capture_path.read_text())
    else:
        from rider_capture_audit import audit as capture_audit
        native = capture_audit(attempt, case)
        receipt = json.loads((attempt / "original-source-receipt.json").read_text())
        capture = {"case_id": case, "frame_count": native["frame_count"],
                   "full_decode": native["full_decode"],
                   "receipt_sha256": native["receipt_sha256"],
                   "source_bindings": {name + ".mkv": item["sha256"]
                                       for name, item in receipt["cameras"].items()}}
    review = json.loads(review_path.read_text())
    physical = json.loads(physical_path.read_text())
    result = assess(case, capture, review, physical,
                    diagnostic=diagnostic_fixture, attempt=attempt)
    result["pixel_review_sha256"] = sha(review_path)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--review", required=True)
    parser.add_argument("--physical", required=True)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.attempt, args.review, args.physical,
                           diagnostic_fixture=args.diagnostic_fixture), indent=2))
