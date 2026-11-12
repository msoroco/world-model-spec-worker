"""CPU shape and rejection checks for the original-source delivery auditor."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from delivery_audit import CAMERAS, DIRECTIONS, FIXED, audit, check_fixed_review, check_pixel_review, joined_observer_distances

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + "__below_500_ft"
ATTEMPT = ROOT/".runtime-work/c104538-final-below-primary-compat"
SAVED = ROOT/".runtime-work/c104538-final-below-primary-saved/v0001"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rejects(call, expected: str) -> None:
    try:
        call()
    except ValueError as error:
        assert expected in str(error), str(error)
    else:
        raise AssertionError("Expected rejection: " + expected)


def run() -> dict:
    def rows(name):
        return [json.loads(line) for line in
                (ATTEMPT/name).read_text().splitlines() if line]
    mapping = rows("video_frames.jsonl")
    hashes = {name: sha(ATTEMPT/name) for name in
        ("video_frames.jsonl", "capture/evidence.jsonl", "road.xodr",
         "trace.jsonl", "driver_eye_rays.jsonl",
         *(camera + ".mkv" for camera in CAMERAS))}
    pixel = {"format": "c104538-original-pixel-review-v1", "case_id": CASE,
             "frames": 480, "source_kind": "source_shaped_unit_test",
             "reviewer": "CPU shape test", "method": "schema exercise only",
             "legal_verdict_claimed": False,
             "frame_map_sha256": hashes["video_frames.jsonl"],
             "source_sha256": {name: hashes[name] for name in
                               ("trace.jsonl", "capture/evidence.jsonl",
                                "driver_eye_rays.jsonl")},
             "views": {camera: {"video_sha256": hashes[camera + ".mkv"],
                                "reviewed_frame_ids": list(range(480)),
                                "subjects_visible": ["ego_body", "opposing_vehicle",
                                                     "obstruction"],
                                "limitations": "Synthetic colors"}
                       for camera in CAMERAS},
             "directions": {direction: {"video_frame": index,
                 "native_frame": mapping[index]["native_frame"],
                 "camera": "overview", "observer_distance_ft": 500,
                 "ego_body_visible": False, "driver_eye_visible": False,
                 "obstruction_visible": False, "method": "CPU shape test",
                 "limitations": "No actual pixel observation"}
                 for index, direction in enumerate(DIRECTIONS)}}
    fixed = {"format": "c104538-original-fixed-condition-review-v1",
             "source_kind": "source_shaped_unit_test", "case_id": CASE,
             "reviewer": "CPU shape test", "method": "schema exercise only",
             "source_sha256": {name: hashes[name] for name in
                               ("capture/evidence.jsonl", "road.xodr")},
             "observations": {name: "unverified synthetic fixture" for name in FIXED},
             "legal_verdict_claimed": False}
    check_pixel_review(pixel, hashes, mapping, CASE, diagnostic=True)
    check_fixed_review(fixed, hashes, CASE, diagnostic=True)
    trace, evidence, rays = (rows(name) for name in
                             ("trace.jsonl", "capture/evidence.jsonl",
                              "driver_eye_rays.jsonl"))
    distances = joined_observer_distances(mapping, trace, evidence, rays)
    assert set(distances) == set(DIRECTIONS)
    assert all(len(values) == 480 for values in distances.values())
    negatives = []
    for name, change, error in [
        ("synthetic as original", lambda p: None,
         "Original two-direction pixel review missing"),
        ("wrong camera hash", lambda p: p["views"]["overview"].update(video_sha256="x"*64),
         "Original camera pixels unreviewed"),
        ("missing direction", lambda p: p["directions"].pop("reference_right"),
         "Original opposing approaches"),
        ("wrong frame join", lambda p: p["directions"]["reference_left"].update(native_frame=-1),
         "500-foot source pixel observation missing"),
        ("wrong distance", lambda p: p["directions"]["reference_left"].update(observer_distance_ft=498),
         "500-foot source pixel observation missing")]:
        damaged = copy.deepcopy(pixel)
        if name == "synthetic as original":
            rejects(lambda: check_pixel_review(damaged, hashes, mapping, CASE,
                                               diagnostic=False), error)
        else:
            change(damaged)
            rejects(lambda damaged=damaged: check_pixel_review(
                damaged, hashes, mapping, CASE, diagnostic=True), error)
        negatives.append(name)
    damaged = copy.deepcopy(fixed)
    damaged["source_sha256"]["road.xodr"] = "x"*64
    rejects(lambda: check_fixed_review(damaged, hashes, CASE, diagnostic=True),
            "Original fixed-condition review incomplete")
    negatives.append("wrong fixed source hash")
    damaged = copy.deepcopy(rays)
    damaged[0]["views"]["reference_left"]["driver_viewpoint_xyz_m"][0] += 5
    rejects(lambda: joined_observer_distances(mapping, trace, evidence, damaged),
            "Original approaching driver viewpoint differs")
    negatives.append("wrong original driver-eye join")
    rejects(lambda: check_pixel_review(pixel, hashes, mapping, CASE,
                                       diagnostic=True,
                                       observed_distances=distances),
            "Pixel review distance differs from original driver-eye/body sources")
    negatives.append("declared 500-foot distance differs from joined diagnostic source")
    rejects(lambda: audit(ATTEMPT, SAVED, ATTEMPT/"owner-release.json", CASE,
                          "primary", sha(ATTEMPT/"construction.json"),
                          HERE/"missing-pixel-review.json",
                          HERE/"missing-fixed-review.json", ATTEMPT/"raw.mkv",
                          ATTEMPT/"core-trace.json", HERE/"update020-decode"),
            "Original Native seal, exit, owner release")
    negatives.append("synthetic attempt cannot pass delivery")
    report = {"format": "c104538-delivery-cpu-proof-v1",
              "source_shaped_unit_test": True,
              "source_shaped_review_checks_passed": True,
              "source_shaped_480_frame_join_passed": True,
              "negative_checks": negatives,
              "original_delivery_audit_passed": False,
              "original_pixel_visibility_proven": False,
              "legal_verdict_claimed": False}
    path = HERE/"update021-delivery-source-join.json"
    path.write_text(json.dumps(report, indent=2)+"\n")
    return {"negative_checks": len(negatives), "proof_sha256": sha(path),
            "original_delivery_audit_passed": False}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
