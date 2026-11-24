"""Source-bound subsection-1 stopping/yielding reference hierarchy.

The ordered reference is geometry for measuring a response. Sign validity,
safe speed, immediate hazard and compliance remain unresolved judgments.
"""

import hashlib
import json
import math
from pathlib import Path

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inspect(root, context):
    root = Path(root)
    source = root / "site_review.json"
    if not source.is_file():
        raise ValueError("Missing original signed-entrance site review")
    review = json.loads(source.read_text())
    if review.get("intersection_context_sha256") != sha(root / "intersection_context.json"):
        raise ValueError("Signed-entrance context changed after review")
    if review.get("native_yield_sign_id") != context["native_yield_sign_id"]:
        raise ValueError("Signed-entrance yield actor differs")
    if review.get("sign_face_observed") not in ("yield", "unverified"):
        raise ValueError("Missing original yield-sign face review")
    if review.get("proper_sign_judgment") != "unresolved":
        raise ValueError("Proper-sign judgment must remain unresolved")
    expected = {name: sha(root / (name + ".mkv")) for name in CAMERAS}
    if review.get("camera_sha256") != expected:
        raise ValueError("Original site-review camera source changed")
    frames = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
    ids = [row.get("carla_frame") for row in frames]
    if (not ids or review.get("reviewed_carla_frames") != ids
            or review.get("reviewed_frame_count") != len(ids)):
        raise ValueError("Incomplete original site-review frame coverage")
    line, crossing = review.get("marked_stop_line_observed"), review.get("near_crosswalk_observed")
    if type(line) is not bool or type(crossing) is not bool:
        raise ValueError("Stop-line and near-crosswalk source review required")
    if line:
        reference = "marked_stop_line"
    elif crossing:
        reference = "near_crosswalk"
    else:
        point = review.get("nearest_view_point_xy_m")
        if (not isinstance(point, list) or len(point) != 2
                or any(type(value) not in (int, float) or not math.isfinite(value) for value in point)):
            raise ValueError("Nearest-view source point required")
        reference = "nearest_view_point"
    return {"reference_kind": reference,
            "reference_source": "site_review.json",
            "reference_review_sha256": sha(source),
            "proper_sign_judgment": "unresolved",
            "safe_speed_judgment": "unresolved",
            "nearest_view_judgment": "unresolved"}
