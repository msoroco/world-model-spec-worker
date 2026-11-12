"""CPU shape and rejection checks for the original-source delivery auditor."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace

from delivery_audit import CAMERAS, DIRECTIONS, FIXED, audit, check_fixed_review, check_pixel_review, check_rgb_frame, joined_observer_distances

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
                                "subjects_visible": [],
                                "limitations": "Synthetic colors"}
                       for camera in CAMERAS},
             "directions": {direction: {"video_frame": index,
                 "native_frame": mapping[index]["native_frame"],
                 "camera": "overview", "observer_distance_ft": 500,
                 "original_rgb_sha256": mapping[index]["original_rgb_sha256"]["overview"],
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
    rgb_shape = SimpleNamespace(index=0, pixels=b"source-shaped RGB bytes")
    rgb_mapping = [{"original_rgb_sha256": {"overview":
                    hashlib.sha256(rgb_shape.pixels).hexdigest()}}]
    check_rgb_frame(rgb_shape, rgb_mapping, "overview")
    trace, evidence, rays = (rows(name) for name in
                             ("trace.jsonl", "capture/evidence.jsonl",
                              "driver_eye_rays.jsonl"))
    distances = joined_observer_distances(mapping, trace, evidence, rays)
    assert set(distances) == set(DIRECTIONS)
    assert all(len(values) == 480 for values in distances.values())
    # Separate synthetic 500-foot source shape. No bound diagnostic or Native
    # source is changed, and no pixel visibility is asserted.
    shape = ROOT/".runtime-work/c104538-update021-500ft-shape"
    shape.mkdir(parents=True, exist_ok=True)
    trace_500, rays_500 = copy.deepcopy(trace), copy.deepcopy(rays)
    for movement, capture, viewpoint in zip(trace_500, evidence, rays_500):
        body = capture["ego"]["body_vertices_m"]
        center = [sum(vertex[axis] for vertex in body)/len(body) for axis in range(3)]
        for role, sign in (("reference_left", -1), ("reference_right", 1)):
            eye = viewpoint["views"][role]
            z = 4.0
            horizontal = math.sqrt(152.4**2-(z-center[2])**2)
            eye["driver_viewpoint_xyz_m"] = [center[0], center[1]+sign*horizontal, z]
            movement["approaching_driver_views"][role] = copy.deepcopy(eye)
    for name, values in (("trace.jsonl", trace_500),
                         ("driver_eye_rays.jsonl", rays_500)):
        (shape/name).write_text("".join(json.dumps(row, separators=(",", ":"))+"\n"
                                        for row in values))
    (shape/"provenance.json").write_text(json.dumps({
        "provenance_kind": "source_shaped_unit_test", "diagnostic_fixture": True,
        "original_native_claimed": False})+"\n")
    distances_500 = joined_observer_distances(mapping, trace_500, evidence, rays_500)
    assert all(abs(distance-500) < 1e-7 for values in distances_500.values()
               for distance in values)
    hashes_500 = dict(hashes)
    hashes_500["trace.jsonl"] = sha(shape/"trace.jsonl")
    hashes_500["driver_eye_rays.jsonl"] = sha(shape/"driver_eye_rays.jsonl")
    pixel_500 = copy.deepcopy(pixel)
    pixel_500["source_sha256"] = {name: hashes_500[name] for name in
                                   pixel_500["source_sha256"]}
    check_pixel_review(pixel_500, hashes_500, mapping, CASE, diagnostic=True,
                       observed_distances=distances_500)
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
        ("wrong selected RGB hash", lambda p: p["directions"]["reference_left"].update(original_rgb_sha256="x"*64),
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
    damaged = copy.deepcopy(pixel)
    damaged["source_sha256"]["driver_eye_rays.jsonl"] = "x"*64
    rejects(lambda: check_pixel_review(damaged, hashes, mapping, CASE,
                                       diagnostic=True),
            "Pixel review frame map differs")
    negatives.append("wrong driver-eye source hash")
    rejects(lambda: check_rgb_frame(SimpleNamespace(index=0, pixels=b"changed"),
                                    rgb_mapping, "overview"),
            "Decoded original RGB frame differs from frame map")
    negatives.append("decoded RGB bytes differ from frame map")
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
              "source_shaped_500_foot_join_passed": True,
              "source_shaped_500_foot_source_sha256": {
                  name: sha(shape/name) for name in
                  ("trace.jsonl", "driver_eye_rays.jsonl", "provenance.json")},
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
