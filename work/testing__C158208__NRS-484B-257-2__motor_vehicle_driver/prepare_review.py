"""Prepare and apply original-camera site review after Native capture.

A template is a checklist, not a completed review. Applying it requires a
reviewer to fill findings from the exact original source cameras and frames.
"""

import argparse
import hashlib
import json
from pathlib import Path

from yield_capture import CAMERAS, bind_site_review


def template(attempt):
    attempt = Path(attempt)
    context_path = attempt / "intersection_context.json"
    frames_path = attempt / "video_frames.jsonl"
    context = json.loads(context_path.read_text())
    frames = [json.loads(line) for line in frames_path.read_text().splitlines()]
    if not frames:
        raise ValueError("No original Native frame joins to review")
    hashes = {}
    for name in CAMERAS:
        path = attempt / (name + ".mkv")
        if not path.is_file() or not path.stat().st_size:
            raise ValueError("Missing original camera " + name)
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"method": "original_source_camera_frame_review", "reviewer": None,
            "intersection_context_sha256": hashlib.sha256(context_path.read_bytes()).hexdigest(),
            "native_yield_sign_id": context["native_yield_sign_id"],
            "camera_sha256": hashes,
            "reviewed_carla_frames": [row["carla_frame"] for row in frames],
            "reviewed_frame_count": len(frames),
            "sign_face_observed": "unverified", "proper_sign_judgment": "unresolved",
            "marked_stop_line_observed": None, "near_crosswalk_observed": None,
            "nearest_view_point_xy_m": None, "reference_boundary": None,
            "review_note": "Fill from the cited original cameras; confirm reference against capture plan."
            }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--template", type=Path)
    parser.add_argument("--apply", type=Path)
    args = parser.parse_args()
    if bool(args.template) == bool(args.apply):
        raise ValueError("Choose exactly one of --template or --apply")
    if args.template:
        if args.template.exists():
            raise ValueError("Fresh review template path required")
        args.template.write_text(json.dumps(template(args.attempt), indent=2, sort_keys=True) + "\n")
    else:
        findings = json.loads(args.apply.read_text())
        bind_site_review(args.attempt, findings)


if __name__ == "__main__":
    main()
