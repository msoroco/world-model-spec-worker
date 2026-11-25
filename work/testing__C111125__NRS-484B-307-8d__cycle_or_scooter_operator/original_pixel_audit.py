"""Bind independent bicycle, signal and participant review to original camera pixels.

The reviewer supplies frame, crop and label observations. Diagnostic mode tests
the software path but cannot establish physical visibility or legal compliance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from delivery_audit import ASSIGNMENT, CAMERAS, audit_processed


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def crop_rgb(video: Path, frame: int, box: list[int]) -> bytes:
    x, y, width, height = box
    command = ["ffmpeg", "-nostdin", "-v", "error", "-i", str(video),
               "-vf", f"select=eq(n\\,{frame}),crop={width}:{height}:{x}:{y},format=rgb24",
               "-frames:v", "1", "-f", "rawvideo", "-"]
    completed = subprocess.run(command, capture_output=True, check=False)
    if completed.returncode or len(completed.stdout) != width * height * 3:
        raise ValueError("original review crop decode failed")
    return completed.stdout


def audit(attempt: Path, processed: Path, case_id: str, review: Path, *,
          diagnostic: bool = False, authority: Path | None = None,
          site: Path | None = None, source_auditor=audit_processed,
          crop_decoder=crop_rgb) -> dict:
    attempt = attempt.resolve()
    processed = processed.resolve()
    review = review.resolve()
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("exact pixel review case differs")
    packet = json.loads(review.read_text(encoding="utf-8"))
    if (packet.get("case_id") != case_id or not packet.get("reviewer") or
            packet.get("diagnostic_fixture") is not diagnostic or
            packet.get("actual_original_pixels") is not (not diagnostic)):
        raise ValueError("independent original pixel review provenance missing")
    receipt_path = processed / "processing.json"
    result_path = processed / "analysis/result.json"
    if (packet.get("processing_sha256") != sha(receipt_path) or
            packet.get("result_sha256") != sha(result_path)):
        raise ValueError("pixel review differs from saved analysis revision")
    source = source_auditor(attempt, processed, case_id, diagnostic,
                            authority=authority, site_file=site)
    if source.get("software_checks_passed") is not True or source.get("joined_frames") != 900:
        raise ValueError("full original source audit missing")
    observations = packet.get("observations")
    if not isinstance(observations, list) or len(observations) < 4:
        raise ValueError("four original camera observations required")
    dimensions = {"overview": (1920, 1080), "approach": (1280, 720),
                  "reference_corner": (1280, 720), "driver_reference": (1280, 720)}
    seen = set()
    rider = set()
    device = set()
    directed = set()
    for item in observations:
        name = item.get("camera")
        frame = item.get("frame_index")
        box = item.get("crop_xywh")
        if name not in CAMERAS or type(frame) is not int or not 0 <= frame < 900:
            raise ValueError("original review camera or frame differs")
        if (not isinstance(box, list) or len(box) != 4 or
                any(type(value) is not int for value in box)):
            raise ValueError("original review crop missing")
        x, y, width, height = box
        sensor_width, sensor_height = dimensions[name]
        if (x < 0 or y < 0 or width < 8 or height < 8 or
                x + width > sensor_width or y + height > sensor_height):
            raise ValueError("original review crop outside camera")
        if packet.get("original_camera_sha256", {}).get(name) != sha(attempt / (name + ".mkv")):
            raise ValueError("reviewed original camera source differs")
        pixels = crop_decoder(attempt / (name + ".mkv"), frame, box)
        if hashlib.sha256(pixels).hexdigest() != item.get("rgb24_sha256"):
            raise ValueError("original reviewed pixel hash differs")
        for label in ("bicycle_rider_visible", "official_device_visible", "directed_participant_visible"):
            if item.get(label) not in (True, False, "unknown"):
                raise ValueError("independent visibility label missing: " + label)
        if not diagnostic and len(set(pixels)) <= 1:
            raise ValueError("uniform original pixel crop cannot verify bicycle rider")
        seen.add(name)
        if item["bicycle_rider_visible"] is True:
            rider.add((name, frame))
        if item["official_device_visible"] is True:
            device.add((name, frame))
        if item["directed_participant_visible"] is True:
            directed.add((name, frame))
    if seen != set(CAMERAS):
        raise ValueError("independent four-camera pixel review incomplete")
    if not diagnostic:
        if (len({frame for _, frame in rider}) < 2 or
                not {"overview", "approach"} <= {name for name, _ in rider} or
                "reference_corner" not in {name for name, _ in device}):
            raise ValueError("original rider or official device visibility missing")
        if case_id.endswith("__fails_to_yield") and not directed:
            raise ValueError("original directed participant visibility missing")
    return {"format": "c111125-independent-original-pixel-review-v1",
            "case_id": case_id, "review_sha256": sha(review),
            "processing_sha256": sha(receipt_path), "observed_cameras": sorted(seen),
            "status": "software_diagnostic_only" if diagnostic else "original_pixels_reviewed",
            "diagnostic_fixture": diagnostic, "physical_acceptance": False,
            "legal_verdict": None}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--processed", required=True, type=Path)
    parser.add_argument("--case", required=True)
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--authority-root", type=Path)
    parser.add_argument("--site", type=Path)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(args.attempt.resolve()):
        raise ValueError("review output must remain outside original attempt")
    receipt = audit(args.attempt, args.processed, args.case, args.review,
                    diagnostic=args.diagnostic, authority=args.authority_root,
                    site=args.site)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"case_id": args.case, "status": receipt["status"]}))


if __name__ == "__main__":
    main()
