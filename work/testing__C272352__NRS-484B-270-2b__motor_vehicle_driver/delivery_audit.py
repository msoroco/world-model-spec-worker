"""Independent source, pixel and physical completion review for saved passes."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from passing_capture_audit import AID, CAMERAS, audit as capture_audit


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decoded_pixel_sha(video, frame):
    result = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i",
                             str(video), "-vf", "select=eq(n\\," + str(frame) + ")",
                             "-frames:v", "1", "-pix_fmt", "rgb24", "-f",
                             "rawvideo", "-"], check=True, capture_output=True)
    need(result.stdout, "reviewed frame has no decoded pixels")
    return hashlib.sha256(result.stdout).hexdigest()


def assess(case, capture, review, physical, *, diagnostic=False, attempt=None):
    need(case.startswith(AID + "__"), "exact delivery case required")
    need(capture.get("case_id") == case and capture.get("frame_count") == 900 and
         capture.get("full_decode") is True,
         "original full capture audit missing")
    bindings = capture.get("source_bindings", {})
    need({name + ".mkv" for name in CAMERAS} <= set(bindings),
         "four original video sources missing")
    need(review.get("case_id") == case and
         review.get("capture_receipt_sha256") == capture.get("receipt_sha256"),
         "independent review has wrong source")
    views = review.get("views")
    need(isinstance(views, dict) and set(views) == set(CAMERAS),
         "independent four-view pixel review missing")
    need(all(review.get(key) is None for key in
             ("legal_due_care", "legal_safe_distance", "legal_safely_clear",
              "legal_exception_213_217")),
         "delivery audit cannot assert legal judgment")
    for name in CAMERAS:
        item = views[name]
        need(item.get("video_sha256") == bindings[name + ".mkv"] and
             isinstance(item.get("reviewer"), str) and item["reviewer"].strip(),
             "independent pixel review source/reviewer missing: " + name)
        samples = item.get("samples")
        need(isinstance(samples, list) and samples,
             "independent participant pixel samples missing: " + name)
        for sample in samples:
            frame = sample.get("frame")
            need(type(frame) is int and 0 <= frame < 900 and
                 sample.get("ego_visible") is True and
                 sample.get("qualifying_rider_visible") is True and
                 isinstance(sample.get("decoded_rgb_sha256"), str) and
                 len(sample["decoded_rgb_sha256"]) == 64,
                 "participant pixel review incomplete: " + name)
            if not diagnostic:
                need(decoded_pixel_sha(Path(attempt) / (name + ".mkv"), frame) ==
                     sample["decoded_rgb_sha256"],
                     "independent pixel source changed: " + name)
    maneuver = physical.get("physical_checks", {}).get("maneuver", {})
    need(physical.get("case_id") == case and
         physical.get("maneuver_completed") is True and
         maneuver.get("status") == "met" and maneuver.get("sources") and
         physical.get("realized_observables"),
         "source-measured physical completion missing")
    if not diagnostic:
        need(physical.get("provenance_kind") == "native" and
             physical.get("diagnostic_fixture") is False,
             "Native physical provenance required")
    return {"format": "passing-independent-delivery-audit", "case_id": case,
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "capture_receipt_sha256": capture["receipt_sha256"],
            "source_verified": not diagnostic, "diagnostic_fixture": diagnostic,
            "canonical_acceptance": False, "legal_verdict": None}


def audit(case, attempt, review_path, physical_path):
    attempt = Path(attempt).resolve()
    review_path = Path(review_path).resolve()
    physical_path = Path(physical_path).resolve()
    need(review_path.is_file() and physical_path.is_file(),
         "independent review and physical result required")
    capture = capture_audit(attempt, case)
    review = json.loads(review_path.read_text(encoding="utf-8"))
    physical = json.loads(physical_path.read_text(encoding="utf-8"))
    result = assess(case, capture, review, physical, attempt=attempt)
    result["pixel_review_sha256"] = sha(review_path)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--review", required=True)
    parser.add_argument("--physical", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.attempt, args.review, args.physical), indent=2))
