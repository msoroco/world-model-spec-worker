"""Verify provenance of a human review of original crossing camera frames.

This checks exact decoded pixels, frame identities and source citations. It does
not decide whether the depicted geometry meets NRS 484B.560(3).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from native_camera import VIEWS
from owner_release import verify_release


FEATURES = ("crossing_device", "stop_line", "rail_crossing", "lane_markings",
            "highway_right_edge", "ego_body")
SOURCE_FOR_FEATURE = {
    "crossing_device": "crossing_authority",
    "stop_line": "crossing_authority",
    "rail_crossing": "opendrive",
    "lane_markings": "lane_markings",
    "highway_right_edge": "highway_boundary",
    "ego_body": "camera_poses",
    "companion_body": "camera_poses",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _contained(root: Path, name: str) -> Path:
    relative = Path(name)
    if not name or relative.is_absolute() or ".." in relative.parts:
        raise ValueError("review source path escapes original attempt")
    path = (root / relative).resolve()
    if root not in path.parents or not path.is_file():
        raise ValueError("review source missing from original attempt")
    return path


def _frame(video: Path, index: int, width: int, height: int) -> bytes:
    completed = subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i",
         str(video), "-vf", f"select=eq(n\\,{index})", "-frames:v", "1",
         "-f", "rawvideo", "-pix_fmt", "bgra", "pipe:1"],
        capture_output=True, check=True)
    raw = completed.stdout
    if len(raw) != width * height * 4:
        raise ValueError("review frame missing or dimensions differ")
    return raw


def verify(attempt: Path, review_path: Path, *, frame_reader=_frame) -> dict:
    attempt = Path(attempt).resolve()
    if not any(parent.name == ".runtime-work" for parent in attempt.parents):
        raise ValueError("review requires private original attempt")
    verify_release(attempt)
    review_path = Path(review_path).resolve()
    if review_path.parent != attempt:
        raise ValueError("review must stay with original attempt")
    review = json.loads(review_path.read_text(encoding="utf-8"))
    packet_path = attempt / "site/packet.json"
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    native = json.loads((attempt / "native-run-status.json").read_text(encoding="utf-8"))
    mapping_path = attempt / "video_frames.jsonl"
    rows = [json.loads(line) for line in mapping_path.read_text(encoding="utf-8").splitlines()]
    media = json.loads((attempt / "media-receipt.json").read_text(encoding="utf-8"))
    views = {name: (width, height) for name, width, height in VIEWS}
    expected_features = set(FEATURES)
    if packet.get("companion_slot") is not None:
        expected_features.add("companion_body")
    if (review.get("format") != "c202480-original-feature-review-v1" or
            review.get("case_id") != packet.get("case_id") or
            review.get("native_status_sha256") != sha(attempt / "native-run-status.json") or
            review.get("site_packet_sha256") != sha(packet_path) or
            review.get("frame_map_sha256") != sha(mapping_path) or
            review.get("media_receipt_sha256") != sha(attempt / "media-receipt.json") or
            native.get("case_id") != packet.get("case_id") or len(rows) != 900 or
            native.get("site_packet_sha256") != sha(packet_path) or
            media.get("frames") != 900 or
            set(media.get("video_sha256", {})) != set(views)):
        raise ValueError("original review identity or source hashes differ")
    if any("synthetic" in str(item.get("pose_source_citation", "")).lower()
           for item in packet.get("cameras", [])):
        raise ValueError("diagnostic camera poses cannot support original feature review")
    annotations = review.get("annotations")
    if not isinstance(annotations, list) or len(annotations) != len(expected_features):
        raise ValueError("one annotation per required crossing feature is required")
    seen = set()
    verified = []
    for item in annotations:
        feature = item.get("feature")
        view = item.get("view")
        index = item.get("video_frame")
        reviewer = item.get("reviewer")
        if (feature not in expected_features or feature in seen or view not in views or
                type(index) is not int or not 0 <= index < 900 or
                not isinstance(reviewer, str) or not reviewer.strip() or
                "fixture" in reviewer.lower() or
                item.get("observation") not in ("visible", "not_visible", "uncertain")):
            raise ValueError("crossing feature annotation identity is invalid")
        seen.add(feature)
        source_key = SOURCE_FOR_FEATURE[feature]
        source = packet["sources"][source_key]
        source_path = _contained(packet_path.parent, source["path"])
        if (source.get("sha256") != sha(source_path) or
                item.get("site_source_sha256") != sha(source_path)):
            raise ValueError("crossing feature source citation differs")
        row = rows[index]
        if (item.get("carla_frame") != row.get("carla_frame") or
                item.get("camera_source_sha256") != row.get("camera_source_sha256", {}).get(view)):
            raise ValueError("crossing feature original frame join differs")
        width, height = views[view]
        box = item.get("bbox_xyxy")
        if (not isinstance(box, list) or len(box) != 4 or
                any(type(value) is not int for value in box) or
                not (0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height)):
            raise ValueError("crossing feature pixel region is invalid")
        video = attempt / (view + ".mkv")
        if media["video_sha256"][view] != sha(video):
            raise ValueError("crossing feature original video bytes differ")
        raw = _contained(attempt, f"raw/{view}/{row['carla_frame']:08d}.bgra")
        if sha(raw) != row["camera_source_sha256"][view]:
            raise ValueError("crossing feature original raw camera hash differs")
        pixels = frame_reader(video, index, width, height)
        if (len(pixels) != width * height * 4 or pixels != raw.read_bytes() or
                item.get("bgra_frame_sha256") != hashlib.sha256(pixels).hexdigest()):
            raise ValueError("crossing feature decoded frame bytes differ")
        crop = b"".join(pixels[(y * width + box[0]) * 4:(y * width + box[2]) * 4]
                        for y in range(box[1], box[3]))
        if item.get("bgra_crop_sha256") != hashlib.sha256(crop).hexdigest():
            raise ValueError("crossing feature crop bytes differ")
        verified.append({"feature": feature, "view": view, "video_frame": index,
                         "observation": item["observation"], "reviewer": reviewer,
                         "bgra_crop_sha256": item["bgra_crop_sha256"]})
    if seen != expected_features:
        raise ValueError("required crossing feature annotation missing")
    return {"format": "c202480-feature-review-provenance-v1",
            "case_id": packet["case_id"], "review_sha256": sha(review_path),
            "annotations": verified, "all_features_annotated_visible": all(
                item["observation"] == "visible" for item in verified),
            "feature_visibility_verified": False,
            "legal_judgment": "unresolved", "physical_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.attempt, args.review), indent=2))
