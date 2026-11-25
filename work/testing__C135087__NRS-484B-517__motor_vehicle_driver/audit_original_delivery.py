"""Audit one saved original taxicab stand attempt after independent review.

The review packet records source and pixel inspection. Legal conclusions remain
for the local reviewer; no diagnostic fixture can satisfy this command.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from stand import SourceError
from stand_source_sweep import extract


HERE = Path(__file__).resolve().parent
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _review(root, ref):
    if not isinstance(ref, dict) or not isinstance(ref.get("path"), str):
        raise SourceError("sealed independent original review reference required")
    original = root / ref["path"]
    path = original.resolve()
    if original.is_symlink() or not path.is_relative_to(root) or not path.is_file():
        raise SourceError("independent original review source escapes attempt")
    if _sha(path) != ref.get("sha256"):
        raise SourceError("independent original review source hash changed")
    return json.loads(path.read_text(encoding="utf-8"))


def audit(case_id, attempt_path, review_ref):
    root = Path(attempt_path).resolve()
    manifest = json.loads((HERE / "execution-manifest.json").read_text(encoding="utf-8"))
    entry = next((row for row in manifest["cases"] if row["case_id"] == case_id), None)
    if entry is None:
        raise SourceError("case absent from selected manifest")
    selected = json.loads((root / "candidate-selection.json").read_text(encoding="utf-8"))
    candidate_id = selected.get("candidate_id")
    candidate = entry if candidate_id == "primary" else next(
        (row for row in entry["candidates"] if row["id"] == candidate_id), None)
    if (candidate is None or selected.get("format") != "worker-candidate-selection" or
            selected.get("case_id") != case_id or
            selected.get("construction_sha256") != candidate["construction_sha256"] or
            selected.get("manifest_sha256") != _sha(HERE / "execution-manifest.json")):
        raise SourceError("original candidate selection differs from selected manifest")
    review = _review(root, review_ref)
    if review.get("source") != "independent_original_site_vehicle_video_review":
        raise SourceError("independent original source and video review missing")
    if review.get("case_id") != case_id or review.get("reviewer") in (None, ""):
        raise SourceError("independent review case or reviewer missing")
    site_sha = _sha(root / "site-original.json")
    vehicle_sha = _sha(root / "vehicle-original.json")
    if (review.get("reviewed_site_sha256") != site_sha or
            review.get("reviewed_vehicle_sha256") != vehicle_sha or
            not review.get("official_stand_designation_source_reviewed") or
            not review.get("stand_sign_source_reviewed") or
            not review.get("subject_passenger_vehicle_source_reviewed") or
            not review.get("entrant_taxicab_source_reviewed")):
        raise SourceError("original stand, sign or vehicle classification review missing")
    sweep = extract(root, site_sha, vehicle_sha)
    if sweep["case_id"] != case_id or sweep["measurements"]["source_frame_count"] != 900:
        raise SourceError("original source observations do not match selected case")
    videos = {name: _sha(root / (name + ".mkv")) for name in CAMERAS}
    if (review.get("video_sha256") != videos or
            review.get("reviewed_frame_ids") != [0, 450, 899] or
            not review.get("subject_and_entrant_visible") or
            not review.get("passenger_loading_visible") or
            not review.get("stand_and_sign_visible") or
            not review.get("physical_motion_completed")):
        raise SourceError("original physical completion or pixel review missing")
    return {"format": "c135087-original-delivery-audit-v1", "case_id": case_id,
            "candidate_id": candidate_id, "attempt_source_sha256": sweep["attempt_source_sha256"],
            "review_sha256": review_ref["sha256"], "reviewed_site_sha256": site_sha,
            "reviewed_vehicle_sha256": vehicle_sha, "video_sha256": videos,
            "original_frame_count": 900, "decoded_camera_frames": sweep["decoded_camera_frames"],
            "measurements": sweep["measurements"], "actual_pixels": True,
            "physical_completion": True, "legal_verdict_claimed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--review-ref", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    ref = json.loads(Path(args.review_ref).read_text(encoding="utf-8"))
    result = audit(args.case, args.attempt, ref)
    Path(args.output).write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                                 encoding="utf-8")


if __name__ == "__main__":
    main()
