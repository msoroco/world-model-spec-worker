"""Controlled source-shape proof; video bytes here are placeholders, not recordings."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile

from original_source_contract import AID, CAMERAS, FRAME_COUNT, FPS, sha, validate
from geometry import SIGN_NAME, open_drive
from finalize import run as finalize


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def rows(path: Path, values: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(x, sort_keys=True) for x in values) + "\n",
                    encoding="utf-8")


def expect_rejection(attempt: Path, review: Path, changed: Path, mutator) -> str:
    old = changed.read_bytes()
    mutator(changed)
    try:
        validate(attempt, review)
    except (ValueError, KeyError, TypeError) as exc:
        return str(exc)
    finally:
        changed.write_bytes(old)
    raise AssertionError(f"accepted corrupt source: {changed.name}")


def prove() -> dict:
    scratch = Path(os.environ.get("TMPDIR", ".runtime-work"))
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="c135709-original-", dir=scratch) as temporary:
        attempt = Path(temporary)
        case_id = AID + "__witness_1"
        (attempt / "road.xodr").write_text(open_drive(), encoding="utf-8")
        map_sha256 = sha(attempt / "road.xodr")
        for camera in CAMERAS:
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                            "color=c=black:s=64x48:r=20", "-frames:v", "600",
                            "-c:v", "ffv1", str(attempt / f"{camera}.mkv")],
                           check=True, capture_output=True)
        capture = {"source_kind": "original_native", "frame_count": FRAME_COUNT,
                   "case_id": case_id,
                   "fps": FPS, "closed": True, "world_restored": True,
                   "map_sha256": map_sha256,
                   "video_sources": {name: {"path": f"{name}.mkv",
                                            "sha256": sha(attempt / f"{name}.mkv")}
                                     for name in CAMERAS}}
        write(attempt / "capture-manifest.json", capture)
        write(attempt / "zone-survey.json", {"bounds_m": [0, 0, 10, 4],
              "map_sha256": map_sha256, "sign_id": "510",
              "sign_text_readback": SIGN_NAME})
        actors = []
        joins = []
        for i in range(FRAME_COUNT):
            actors.append({"frame": i, "native_frame": 1000 + i,
                           "elapsed_s": i / FPS, "ego_body_m": [3, 1, 7, 3],
                           "ego_speed_mps": 0.0,
                           "passenger_actor_ids_near_vehicle": [7] if i < 100 else [7, 8],
                           "door_open_request": 95 <= i <= 105,
                           "other_vehicles": [{"actor_id": 91,
                               "body_m": [8, 1, 12, 3], "speed_mps": 0.0,
                               "requesting_zone_entry": True}] if 200 <= i < 210 else []})
            joins.append({"frame": i, "native_frame": 1000 + i,
                          "cameras": {name: i for name in CAMERAS}})
        rows(attempt / "actor-frames.jsonl", actors)
        rows(attempt / "camera-frames.jsonl", joins)
        names = ("capture-manifest.json", "road.xodr", "zone-survey.json", "actor-frames.jsonl",
                 "camera-frames.jsonl") + tuple(f"{name}.mkv" for name in CAMERAS)
        review = attempt / "source-review.json"
        review_content = {"case_id": case_id,
                          "source_sha256": {name: sha(attempt / name) for name in names},
                          "reviewer": "controlled-fixture", "restricted_purpose": "test-purpose",
                          "sign_authority": "unverified", "sign_pixel_status": "unverified"}
        write(review, review_content)
        positive = validate(attempt, review)
        assert positive["stopped_in_zone_frames"] == FRAME_COUNT
        assert positive["nearby_passenger_identity_change_frames_with_door_request"] == 1
        assert positive["actual_passenger_loading"] == "unverified"
        assert positive["requested_waiting_or_entering_overlap_frames"] == 10
        assert positive["legal_conclusion"] is None
        assert positive["case_id"] == case_id
        selected_config = Path(__file__).resolve().parent.parent / "cases/witness_1/config.json"
        (attempt / "config.json").write_bytes(selected_config.read_bytes())
        report = finalize(attempt, attempt / "analysis-report.json")
        finalized = json.loads((attempt / "result.json").read_text(encoding="utf-8"))
        assert report["measurements"]["restricted_zone_original_facts"]["value"] == positive
        assert finalized["case_id"] == case_id
        assert finalized["legal_verdict_claimed"] is False
        assert finalized["physical_acceptance_claimed"] is False
        assert len((attempt / "trace.jsonl").read_text().splitlines()) == FRAME_COUNT
        assert len((attempt / "video_frames.jsonl").read_text().splitlines()) == FRAME_COUNT
        assert all(len((attempt / "channels" / (name + ".jsonl")).read_text().splitlines()) == FRAME_COUNT
                   for name in ("st.curb_zone", "dev.regulatory_sign", "ru.occupant_count",
                                "sig.door_open", "ru.pedestrian", "ru.motor_vehicle"))
        negatives = {}
        negatives["wrong_case_review"] = expect_rejection(
            attempt, review, review,
            lambda path: write(path, dict(review_content, case_id=AID + "__witness_2")))
        negatives["stale_map"] = expect_rejection(
            attempt, review, attempt / "road.xodr",
            lambda path: path.write_text(path.read_text().replace("narrow-road", "changed-road"),
                                         encoding="utf-8"))
        negatives["stale_review"] = expect_rejection(
            attempt, review, attempt / "zone-survey.json",
            lambda path: path.write_text(path.read_text().replace(SIGN_NAME,
                                                           'changed purpose'), encoding="utf-8"))
        negatives["map_sign_mismatch"] = expect_rejection(
            attempt, review, attempt / "road.xodr",
            lambda path: path.write_text(path.read_text().replace(SIGN_NAME, "OTHER SIGN"),
                                         encoding="utf-8"))
        negatives["missing_camera"] = expect_rejection(
            attempt, review, attempt / "driver_reference.mkv", lambda path: path.unlink())
        negatives["unclosed"] = expect_rejection(
            attempt, review, attempt / "capture-manifest.json",
            lambda path: write(path, dict(capture, closed=False)))
        # Rebind source hashes to exercise structural checks after provenance checks.
        altered_join = copy.deepcopy(joins)
        altered_join[50]["native_frame"] = 9001
        rows(attempt / "camera-frames.jsonl", altered_join)
        review_content["source_sha256"]["camera-frames.jsonl"] = sha(attempt / "camera-frames.jsonl")
        write(review, review_content)
        try:
            validate(attempt, review)
        except ValueError as exc:
            negatives["wrong_join"] = str(exc)
        else:
            raise AssertionError("accepted wrong Native camera frame join")
        rows(attempt / "camera-frames.jsonl", joins)
        review_content["source_sha256"]["camera-frames.jsonl"] = sha(attempt / "camera-frames.jsonl")
        video_path = attempt / "approach.mkv"
        video_bytes = video_path.read_bytes()
        video_path.write_bytes(b"corrupt-video")
        capture["video_sources"]["approach"]["sha256"] = sha(video_path)
        write(attempt / "capture-manifest.json", capture)
        review_content["source_sha256"]["capture-manifest.json"] = sha(attempt / "capture-manifest.json")
        review_content["source_sha256"]["approach.mkv"] = sha(video_path)
        write(review, review_content)
        try:
            validate(attempt, review)
        except ValueError as exc:
            negatives["corrupt_video_after_rebind"] = str(exc)
        else:
            raise AssertionError("accepted corrupt original camera video")
        video_path.write_bytes(video_bytes)
        capture["video_sources"]["approach"]["sha256"] = sha(video_path)
        write(attempt / "capture-manifest.json", capture)
        review_content["source_sha256"]["capture-manifest.json"] = sha(attempt / "capture-manifest.json")
        review_content["source_sha256"]["approach.mkv"] = sha(video_path)
        malformed = copy.deepcopy(actors)
        del malformed[50]["passenger_actor_ids_near_vehicle"]
        rows(attempt / "actor-frames.jsonl", malformed)
        review_content["source_sha256"]["actor-frames.jsonl"] = sha(attempt / "actor-frames.jsonl")
        write(review, review_content)
        try:
            validate(attempt, review)
        except ValueError as exc:
            negatives["missing_original_occupant"] = str(exc)
        else:
            raise AssertionError("accepted missing original nearby passenger identity")
        assert len(negatives) == 9
        return {"format": "restricted-zone-original-source-fixture-proof-v1",
                "positive": {"stopped_in_zone_frames": positive["stopped_in_zone_frames"],
                             "nearby_passenger_identity_change_frames_with_door_request": positive["nearby_passenger_identity_change_frames_with_door_request"],
                             "requested_waiting_or_entering_overlap_frames": positive["requested_waiting_or_entering_overlap_frames"]},
                "negative_rejections": negatives,
                "fixture_video_bytes": "four 600-frame FFV1 color videos fully decoded; no physical visibility claim",
                "finalizer": {"original_source_join": True, "frames": FRAME_COUNT,
                              "channels": 10, "physical_or_legal_acceptance": False},
                "original_native_observed": False}


if __name__ == "__main__":
    print(json.dumps(prove(), sort_keys=True))
