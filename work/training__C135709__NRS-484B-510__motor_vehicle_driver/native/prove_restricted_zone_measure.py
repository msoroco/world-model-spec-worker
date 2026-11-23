"""Adversarial 600-frame diagnostic of the draft saved measurement contract."""

import copy
import hashlib
import json
import tempfile
from pathlib import Path

from restricted_zone_measure import CAMERAS, FRAME_COUNT, derive


def make_frames(passenger: bool, waiting: bool) -> list[dict]:
    frames = []
    for i in range(FRAME_COUNT):
        parked = 180 <= i < 500
        frames.append({
            "frame": i, "elapsed_s": i / 20, "camera_ids": list(CAMERAS),
            "ego_footprint_m": [4, 1, 8, 3] if parked else [20, 1, 24, 3],
            "ego_speed_mps": 0.0 if parked else 4.0,
            "door_open": passenger and 260 <= i < 320,
            "occupant_count": 2 if passenger and i >= 280 else 1,
            "pedestrian_count": 1 if passenger and 260 <= i < 320 else 0,
            "other_vehicle_waiting": waiting and 300 <= i < 420,
            "other_vehicle_about_to_enter": False,
        })
    return frames


def write_bundle(root: Path, zone: dict, frames: list[dict]) -> None:
    root.mkdir()
    (root / "zone.json").write_text(json.dumps(zone, sort_keys=True))
    (root / "raw-frames.json").write_text(json.dumps(frames, sort_keys=True))


def rejected(root: Path, expected: str) -> None:
    try:
        derive(root)
    except ValueError as exc:
        assert expected in str(exc), str(exc)
    else:
        raise AssertionError(f"expected rejection containing {expected}")


def main() -> None:
    zone = {
        "source_kind": "synthetic_native_sample", "zone_bounds_m": [0, 0, 10, 4],
        "sign_text": "TAXI ONLY", "restricted_purpose": "taxi_pickup",
        "subject_purpose_declaration": "passenger_pickup", "sign_authority": "unverified",
    }
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        good = base / "passenger_no_interference"
        write_bundle(good, zone, make_frames(True, False))
        measured = derive(good)
        assert measured["frame_count"] == 600
        assert measured["stopped_in_zone_frames"] == 320
        assert measured["passenger_activity_frames_while_stopped"] == 60
        assert measured["waiting_or_entering_vehicle_frames_while_stopped"] == 0
        assert measured["legal_conclusion"] is None
        assert measured["subject_purpose_is_observed"] is False

        waiting_root = base / "passenger_interference"
        write_bundle(waiting_root, zone, make_frames(True, True))
        waiting_measure = derive(waiting_root)
        assert waiting_measure["waiting_or_entering_vehicle_frames_while_stopped"] == 120
        assert waiting_measure["passenger_activity_frames_while_stopped"] == 60

        unrelated_root = base / "unrelated"
        unrelated_zone = {**zone, "subject_purpose_declaration": "private_errand"}
        write_bundle(unrelated_root, unrelated_zone, make_frames(False, False))
        unrelated = derive(unrelated_root)
        assert unrelated["passenger_activity_frames_while_stopped"] == 0
        assert unrelated["subject_purpose_declaration"] == "private_errand"

        missing = base / "missing"
        write_bundle(missing, zone, make_frames(False, False))
        (missing / "raw-frames.json").unlink()
        rejected(missing, "missing required raw source")

        wrong_clock = base / "wrong_clock"
        clock_frames = make_frames(False, False)
        clock_frames[311]["elapsed_s"] = 999
        write_bundle(wrong_clock, zone, clock_frames)
        rejected(wrong_clock, "frame clock mismatch")

        missing_camera = base / "missing_camera"
        camera_frames = make_frames(False, False)
        camera_frames[311]["camera_ids"] = list(CAMERAS[:3])
        write_bundle(missing_camera, zone, camera_frames)
        rejected(missing_camera, "four camera identities absent")

        claimed_authority = base / "claimed_authority"
        write_bundle(claimed_authority, {**zone, "sign_authority": "verified"}, make_frames(False, False))
        rejected(claimed_authority, "synthetic fixture cannot establish sign authority")

        missing_pedestrian = base / "missing_pedestrian"
        pedestrian_frames = make_frames(True, False)
        del pedestrian_frames[280]["pedestrian_count"]
        write_bundle(missing_pedestrian, zone, pedestrian_frames)
        rejected(missing_pedestrian, "raw field pedestrian_count absent")

        proof = {
            "format": "restricted-zone-saved-measurement-proof-v1",
            "source_kind": "synthetic_native_sample",
            "positive_cases": ["passenger_no_interference", "passenger_interference", "unrelated"],
            "negative_cases": ["missing_raw_frames", "wrong_frame_clock", "missing_fourth_camera", "false_sign_authority", "missing_pedestrian_field"],
            "measurements": {"passenger_no_interference": measured,
                             "passenger_interference": waiting_measure,
                             "unrelated": unrelated},
            "physical_or_legal_acceptance": False,
        }
        print(json.dumps(proof, sort_keys=True))


if __name__ == "__main__":
    main()
