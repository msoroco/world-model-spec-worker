"""Verify a human review against exported original bus and signal pixels.

The review records what a person could see. It never supplies a legal verdict.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pixel_frame_index import CAMERAS, REPO, index_attempt, sha
from pixel_review_export import selected_frames


QUESTIONS = ("bus_visible", "green_arrow_legible", "lane_association_visible")
ANSWERS = {"yes", "no", "uncertain"}


def validate(export_dir, review_path, attempt, pixel_index_path, *, diagnostic=False):
    export_dir = Path(export_dir).resolve()
    review_path = Path(review_path).resolve()
    attempt = Path(attempt).resolve()
    pixel_index_path = Path(pixel_index_path).resolve()
    scratch = (REPO / ".runtime-work").resolve()
    if any(not path.is_relative_to(scratch) for path in
           (export_dir, review_path, attempt, pixel_index_path)):
        raise ValueError("original pixel review must stay under .runtime-work")
    sheet_path = export_dir / "review-sheet.json"
    if sheet_path.is_symlink() or not sheet_path.is_file():
        raise ValueError("source-bound review sheet missing")
    sheet = json.loads(sheet_path.read_text())
    if sheet.get("format") != "worker-original-pixel-review-export":
        raise ValueError("original pixel review sheet format invalid")
    index = json.loads(pixel_index_path.read_text())
    actual = index_attempt(attempt, diagnostic=diagnostic)
    if index != actual or sheet.get("pixel_index_sha256") != sha(pixel_index_path) or (
            sheet.get("capture_seal_sha256") != actual["capture_seal_sha256"] or
            sheet.get("case_id") != actual["case_id"]):
        raise ValueError("human pixel sheet differs from sealed original attempt")
    frame_numbers = selected_frames(actual["decoded_original_frames"])
    if sheet.get("selected_video_frames") != frame_numbers:
        raise ValueError("human pixel sheet frame selection differs")
    samples = sheet.get("samples")
    if not isinstance(samples, list) or len(samples) != len(CAMERAS) * len(frame_numbers):
        raise ValueError("original pixel review samples missing")
    expected = {}
    for row in samples:
        name = row.get("image")
        if not isinstance(name, str) or Path(name).name != name or name in expected:
            raise ValueError("original pixel review image identity invalid")
        camera = row.get("camera")
        number = row.get("video_frame")
        if camera not in CAMERAS or number not in frame_numbers or name != f"{camera}-frame-{number:06d}.ppm":
            raise ValueError("original pixel review sample identity differs")
        original = actual["cameras"][camera]["frames"][number]
        if any(row.get(key) != original[key] for key in
               ("rgb24_sha256", "carla_frame", "time_s")):
            raise ValueError("human pixel sample differs from sealed original frame")
        image = export_dir / name
        if image.is_symlink() or not image.is_file() or sha(image) != row.get("image_sha256"):
            raise ValueError("original pixel review image missing or changed")
        expected[name] = row
    if set(expected) != {f"{camera}-frame-{number:06d}.ppm" for camera in CAMERAS
                         for number in frame_numbers}:
        raise ValueError("human pixel review samples omit an original camera frame")
    review = json.loads(review_path.read_text())
    if review.get("review_sheet_sha256") != sha(sheet_path):
        raise ValueError("human review does not bind original pixel sheet")
    if review.get("case_id") != sheet.get("case_id"):
        raise ValueError("human review case identity differs")
    reviewer = review.get("reviewer")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("human pixel reviewer identity missing")
    observations = review.get("observations")
    if not isinstance(observations, list) or len(observations) != len(expected):
        raise ValueError("human pixel review must cover every exported frame")
    seen = set()
    for item in observations:
        name = item.get("image")
        if name not in expected or name in seen:
            raise ValueError("human pixel review frame identity missing or duplicated")
        seen.add(name)
        if item.get("image_sha256") != expected[name]["image_sha256"]:
            raise ValueError("human pixel review image hash differs")
        if set(item.get("answers", {})) != set(QUESTIONS) or any(
                item["answers"][key] not in ANSWERS for key in QUESTIONS):
            raise ValueError("human pixel review answers incomplete")
        note = item.get("note")
        if not isinstance(note, str) or not note.strip():
            raise ValueError("human pixel review frame note missing")
    if sheet.get("diagnostic_fixture") is True and not diagnostic:
        raise ValueError("synthetic pixel review cannot establish original Native visibility")
    return {"format": "worker-human-original-pixel-review-audit",
            "case_id": sheet["case_id"], "reviewer": reviewer,
            "review_sheet_sha256": sha(sheet_path), "review_sha256": sha(review_path),
            "reviewed_frames": len(seen),
            "all_visible": all(all(item["answers"][key] == "yes" for key in QUESTIONS)
                               for item in observations),
            "legal_verdict": None, "physical_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--export", required=True)
    parser.add_argument("--review", required=True)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--pixel-index", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    if not output.is_relative_to((REPO / ".runtime-work").resolve()) or output.exists():
        raise ValueError("fresh human review audit output must be under .runtime-work")
    report = validate(args.export, args.review, args.attempt, args.pixel_index)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(report["case_id"], report["reviewed_frames"], "source-bound human pixel frames audited")


if __name__ == "__main__":
    main()
