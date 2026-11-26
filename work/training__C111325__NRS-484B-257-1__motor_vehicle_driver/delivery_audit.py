"""Independent source audit for an exact NRS 484B.257 selected attempt."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

CASE = "training__C111325__NRS-484B-257-1__motor_vehicle_driver__complete_stop_then_yield"
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCES = ("trace.jsonl", "video_frames.jsonl", "ego_body.jsonl", "through_body.jsonl",
           "interaction_history.jsonl", "governing_sign.json", "governing_controls.json",
           "stopping_reference.json", "through_road.json", "road.xodr")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    require(path.is_file(), "Missing original source: " + path.name)
    return json.loads(path.read_text())


def rows(path):
    require(path.is_file(), "Missing original source: " + path.name)
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit(case, attempt, receipt, diagnostic, missing_source=None):
    require(case == CASE, "Different exact selected case")
    attempt = Path(attempt)
    receipt = read(Path(receipt))
    require(receipt.get("case_id") == case and receipt.get("candidate_id") == "primary"
            and receipt.get("passed") is True and receipt.get("recorded_only") is True
            and receipt.get("originals_preserved") is True, "Recorded-only original receipt incomplete")
    hashes = receipt.get("original_source_hashes", {})
    for name in SOURCES:
        path = attempt / name
        if name == missing_source:
            path = attempt / "missing-original-source"
        require(path.is_file(), "Missing original source: " + name)
        require(hashes.get(name) == digest(path), "Original source hash differs: " + name)
    traces = rows(attempt / "trace.jsonl")
    frame_rows = rows(attempt / "video_frames.jsonl")
    egos = rows(attempt / "ego_body.jsonl")
    through = rows(attempt / "through_body.jsonl")
    interactions = rows(attempt / "interaction_history.jsonl")
    require(all(len(seq) == 600 for seq in (traces, frame_rows, egos, through, interactions)),
            "Six hundred original samples required for every participant")
    require(receipt.get("timestamp_joins", {}).get("frames") == 600
            and receipt["timestamp_joins"].get("passed") is True,
            "Original frame time join incomplete")
    require(receipt.get("final_video_checks", {}).get("frames") == 600
            and receipt["final_video_checks"].get("passed") is True,
            "Final video decode receipt incomplete")
    for view in VIEWS:
        video = attempt / (view + ".mkv")
        require(hashes.get(video.name) == digest(video), "Original view hash differs: " + view)
        probe = subprocess.run(("ffprobe", "-v", "error", "-select_streams", "v:0",
                                "-count_frames", "-show_entries", "stream=nb_read_frames",
                                "-of", "default=nokey=1:noprint_wrappers=1", str(video)),
                               capture_output=True, text=True, check=True)
        require(probe.stdout.strip() == "600", "Full original video decode differs: " + view)
    result = read(attempt / "result.json")
    require(result.get("case_id") == case and result.get("legal_verdict_claimed") is False
            and result.get("physical_acceptance_claimed") is False,
            "Finalizer asserted legal or physical acceptance")
    require(result.get("physical_checks", {}).get("maneuver", {}).get("status") in
            {"met", "not_met", "unverified"}, "Physical completion is not source assessed")
    provenance = read(attempt / "acquisition-provenance.json")
    if diagnostic:
        require(provenance.get("diagnostic_fixture") is True
                and result.get("provenance_kind") == "synthetic_fixture",
                "Diagnostic fixture provenance changed")
        compatibility = read(attempt / "compatibility.json")
        require(compatibility.get("passed") is True and compatibility.get("case_id") == case
                and compatibility.get("negative_removed") == "governing_sign.json",
                "Public positive and negative compatibility missing")
    else:
        require(provenance.get("diagnostic_fixture") is False
                and provenance.get("native_executed") is True,
                "Original Native acquisition required")
        review = read(attempt / "independent-original-review.json")
        require(review.get("case_id") == case and review.get("source_kind") ==
                "independent_original_capture_review", "Independent original review missing")
        for check in ("native_source", "all_participants", "time_join", "full_video_decode",
                      "actual_pixels", "physical_completion"):
            require(review.get(check) is True, "Independent original check missing: " + check)
    return {"case_id": case, "diagnostic_only": diagnostic,
            "source_count": len(SOURCES), "joined_frames": 600, "decoded_views": len(VIEWS),
            "physical_status": result["physical_checks"]["maneuver"]["status"],
            "legal_or_physical_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--processing", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--missing-source")
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.attempt, args.processing,
                           args.diagnostic, args.missing_source), sort_keys=True))
