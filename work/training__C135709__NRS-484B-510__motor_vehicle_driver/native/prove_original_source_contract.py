"""Controlled source-shape proof; video bytes here are placeholders, not recordings."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile

from original_source_contract import AID, CAMERAS, FRAME_COUNT, FPS, REVIEW_FINDINGS, sha, validate
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
        rows(attempt / "trace.jsonl", [
            {"frame": 1000 + i, "time_s": i / FPS,
             "position_m": [5.0, 2.0],
             "position": {"x": 5.0, "y": 2.0, "z": 1.0},
             "heading_deg": 0.0, "velocity_mps": [0.0, 0.0, 0.0],
             "speed_mps": 0.0, "speed_mph": 0.0}
            for i in range(FRAME_COUNT)])
        rows(attempt / "video_frames.jsonl", [
            {"video_frame": i, "carla_frame": 1000 + i,
             "native_frame": 1000 + i, "time_s": i / FPS,
             "camera_native_frames": {name: 1000 + i for name in CAMERAS}}
            for i in range(FRAME_COUNT)])
        names = ("capture-manifest.json", "road.xodr", "zone-survey.json", "actor-frames.jsonl",
                 "camera-frames.jsonl", "trace.jsonl", "video_frames.jsonl") + tuple(f"{name}.mkv" for name in CAMERAS)
        write(attempt / "capture-seal.json", {
            "format": "worker-sealed-capture", "provenance_kind": "native",
            "frames": FRAME_COUNT, "restoration": {"restored": True},
            "encoder_exit_codes": {name: 0 for name in CAMERAS},
            "events": ["capture_finished", "encoders_closed", "restoration_verified"],
            "sources": {name: sha(attempt / name) for name in names}})
        names += ("capture-seal.json",)
        review = attempt / "original-review.json"
        review_content = {"case_id": case_id,
                          "source_sha256": {name: sha(attempt / name) for name in names},
                          "reviewer": "controlled-fixture", "restricted_purpose": "test-purpose",
                          "sign_authority": "unverified", "sign_pixel_status": "unverified",
                          "original_findings": {name: {"status": "unverified", "source_refs": []}
                                                for name in REVIEW_FINDINGS}}
        write(review, review_content)
        positive = validate(attempt, review)
        assert positive["stopped_in_zone_frames"] == FRAME_COUNT
        assert positive["nearby_passenger_identity_change_frames_with_door_request"] == 1
        assert positive["actual_passenger_loading"]["status"] == "unverified"
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
        episode_proofs = {}
        for suffix, departure in (("stop_only", 300), ("stand_only", 500)):
            episode_actors = copy.deepcopy(actors)
            episode_trace = []
            for i, row in enumerate(episode_actors):
                x = 5.0 + max(0, i - departure) * 0.05
                moving = i > departure
                row["ego_body_m"] = [x - 2, 1, x + 2, 3]
                row["ego_speed_mps"] = 1.0 if moving else 0.0
                row["departure_requested"] = i >= departure
                center_x = (row["ego_body_m"][0] + row["ego_body_m"][2]) / 2
                episode_trace.append({"frame": 1000 + i, "time_s": i / FPS,
                    "position_m": [center_x, 2.0],
                    "position": {"x": x, "y": 2.0, "z": 1.0},
                    "heading_deg": 0.0, "velocity_mps": [1.0 if moving else 0.0, 0.0, 0.0],
                    "speed_mps": row["ego_speed_mps"],
                    "speed_mph": row["ego_speed_mps"] / 0.44704})
            rows(attempt / "actor-frames.jsonl", episode_actors)
            rows(attempt / "trace.jsonl", episode_trace)
            capture["case_id"] = AID + "__" + suffix
            write(attempt / "capture-manifest.json", capture)
            seal = json.loads((attempt / "capture-seal.json").read_text())
            seal["sources"] = {name: sha(attempt / name) for name in names if name != "capture-seal.json"}
            write(attempt / "capture-seal.json", seal)
            episode_review = copy.deepcopy(review_content)
            episode_review["case_id"] = capture["case_id"]
            episode_review["source_sha256"] = {name: sha(attempt / name) for name in names}
            write(review, episode_review)
            measured = validate(attempt, review)
            assert measured["departure_requested_frames"] == FRAME_COUNT - departure
            assert measured["moving_after_departure_frames"] == FRAME_COUNT - departure - 1
            episode_proofs[suffix] = {
                "departure_requested_frames": measured["departure_requested_frames"],
                "moving_after_departure_frames": measured["moving_after_departure_frames"],
                "stopped_in_zone_frames": measured["stopped_in_zone_frames"]}
        rows(attempt / "actor-frames.jsonl", actors)
        rows(attempt / "trace.jsonl", [
            {"frame": 1000 + i, "time_s": i / FPS, "position_m": [5.0, 2.0],
             "position": {"x": 5.0, "y": 2.0, "z": 1.0}, "heading_deg": 0.0,
             "velocity_mps": [0.0, 0.0, 0.0], "speed_mps": 0.0,
             "speed_mph": 0.0}
            for i in range(FRAME_COUNT)])
        capture["case_id"] = case_id
        write(attempt / "capture-manifest.json", capture)
        seal = json.loads((attempt / "capture-seal.json").read_text())
        seal["sources"] = {name: sha(attempt / name) for name in names if name != "capture-seal.json"}
        write(attempt / "capture-seal.json", seal)
        review_content["source_sha256"] = {name: sha(attempt / name) for name in names}
        write(review, review_content)
        negatives = {}
        negatives["wrong_case_review"] = expect_rejection(
            attempt, review, review,
            lambda path: write(path, dict(review_content, case_id=AID + "__witness_2")))
        incomplete_review = copy.deepcopy(review_content)
        del incomplete_review["original_findings"]["interference"]
        negatives["missing_interference_review"] = expect_rejection(
            attempt, review, review,
            lambda path: write(path, incomplete_review))
        unsourced_review = copy.deepcopy(review_content)
        unsourced_review["original_findings"]["actual_passenger_loading"]["status"] = "verified"
        negatives["unsourced_loading_claim"] = expect_rejection(
            attempt, review, review,
            lambda path: write(path, unsourced_review))
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
        assert len(negatives) == 11
        return {"format": "restricted-zone-original-source-fixture-proof-v1",
                "positive": {"stopped_in_zone_frames": positive["stopped_in_zone_frames"],
                             "nearby_passenger_identity_change_frames_with_door_request": positive["nearby_passenger_identity_change_frames_with_door_request"],
                             "requested_waiting_or_entering_overlap_frames": positive["requested_waiting_or_entering_overlap_frames"]},
                "episode_proofs": episode_proofs,
                "negative_rejections": negatives,
                "fixture_video_bytes": "four 600-frame FFV1 color videos fully decoded; no physical visibility claim",
                "finalizer": {"original_source_join": True, "frames": FRAME_COUNT,
                              "channels": 10, "physical_or_legal_acceptance": False},
                "original_native_observed": False}


if __name__ == "__main__":
    print(json.dumps(prove(), sort_keys=True))
