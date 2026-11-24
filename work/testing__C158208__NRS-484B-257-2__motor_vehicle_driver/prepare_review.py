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


def officer_template(attempt):
    attempt = Path(attempt)
    context_path = attempt / "intersection_context.json"
    context = json.loads(context_path.read_text())
    if not str(context.get("case_id", "")).endswith("__officer_control_exception"):
        raise ValueError("Officer review template requires the exact exception case")
    candidate_path = attempt / "officer-candidate.json"
    candidate = json.loads(candidate_path.read_text())
    if (candidate.get("format") != "worker-officer-candidate-construction"
            or type(candidate.get("actor_id")) is not int
            or candidate.get("police_authority_judgment") != "unresolved"):
        raise ValueError("Missing source-identified Native person candidate")
    frames = [json.loads(line) for line in (attempt / "video_frames.jsonl").read_text().splitlines()]
    if not frames:
        raise ValueError("No original officer-camera frames")
    cameras = {name: hashlib.sha256((attempt / (name + ".mkv")).read_bytes()).hexdigest()
               for name in CAMERAS}
    return {"method": "original_source_camera_officer_review", "reviewer": None,
            "intersection_context_sha256": hashlib.sha256(context_path.read_bytes()).hexdigest(),
            "officer_candidate_sha256": hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
            "officer_actor_id": candidate["actor_id"], "camera_sha256": cameras,
            "reviewed_carla_frames": [row["carla_frame"] for row in frames],
            "control_observed_at_entry": None, "authority_judgment": "unresolved",
            "review_note": "Verify visible person, actual direction and authority from original cameras; do not infer either from the blueprint."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--template", type=Path)
    parser.add_argument("--officer-template", type=Path)
    parser.add_argument("--apply", type=Path)
    args = parser.parse_args()
    if sum(bool(value) for value in (args.template, args.officer_template, args.apply)) != 1:
        raise ValueError("Choose exactly one review operation")
    if args.template:
        if args.template.exists():
            raise ValueError("Fresh review template path required")
        args.template.write_text(json.dumps(template(args.attempt), indent=2, sort_keys=True) + "\n")
    elif args.officer_template:
        if args.officer_template.exists():
            raise ValueError("Fresh officer review template path required")
        args.officer_template.write_text(json.dumps(officer_template(args.attempt), indent=2,
                                                    sort_keys=True) + "\n")
    else:
        findings = json.loads(args.apply.read_text())
        bind_site_review(args.attempt, findings)


if __name__ == "__main__":
    main()
