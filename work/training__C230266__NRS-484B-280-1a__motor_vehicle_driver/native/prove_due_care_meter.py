"""Run positive and negative source-shape checks for a 30-second encounter."""

import copy
import json
from pathlib import Path

from due_care_meter import FRAMES, digest, measure


def packet(brake):
    rows = []
    vehicle_x = -35.0
    for frame in range(FRAMES):
        speed = 6.0 if not brake or frame < 150 else 2.0
        vehicle_x += speed / 20
        pedestrian_x = 30.0
        pedestrian_y = 8.0 if frame < 130 else (8.0 - min(frame - 130, 80) * 0.1)
        rows.append({
            "frame": frame, "native_frame": frame + 1500, "video_frame": frame,
            "time_s": frame / 20, "vehicle_x_m": vehicle_x, "vehicle_y_m": 0.0,
            "pedestrian_x_m": pedestrian_x, "pedestrian_y_m": pedestrian_y,
            "vehicle_speed_mps": speed, "pedestrian_speed_mps": 0.0 if frame < 130 or frame > 210 else 2.0,
            "vehicle_radius_m": 2.2, "pedestrian_radius_m": 0.35,
            "contact_sensor": False, "contact_source": "synthetic_native_sample",
            "path_conflict_survey": 130 <= frame <= 250,
            "requested_brake": 0.45 if brake and frame >= 150 else 0.0,
        })
    return {
        "format": "worker-pedestrian-due-care-source-v1",
        "law_id": "NRS-484B-280-1a", "cell_id": "C230266",
        "source_kind": "synthetic_native_sample", "actor": "motor_vehicle_driver",
        "vehicle_id": "vehicle-1", "pedestrian_id": "pedestrian-1",
        "vehicle_classification_source": "synthetic_native_sample",
        "pedestrian_classification_source": "synthetic_native_sample",
        "path_survey_source": "synthetic_native_sample",
        "trace": rows, "trace_sha256": digest(rows),
    }


def rejects(packet_value, fragment):
    try:
        measure(packet_value)
    except ValueError as error:
        assert fragment in str(error), str(error)
        return str(error)
    raise AssertionError("Bad source accepted: " + fragment)


def changed(original, mutate):
    value = copy.deepcopy(original)
    mutate(value)
    value["trace_sha256"] = digest(value["trace"])
    return value


def main():
    slow, steady = packet(True), packet(False)
    positives = {"brake_request": measure(slow), "maintain_request": measure(steady)}
    assert positives["brake_request"]["frames"] == FRAMES
    assert positives["brake_request"]["requested_brake_frames"] > 0
    assert positives["maintain_request"]["requested_brake_frames"] == 0
    assert all(v["legal_due_care_verdict"] is None for v in positives.values())
    negatives = {
        "short": rejects(changed(slow, lambda p: p["trace"].pop()), "Full 600-frame trace required"),
        "stale_hash": rejects({**slow, "trace_sha256": "0" * 64}, "Trace hash mismatch"),
        "missing_pedestrian": rejects({**slow, "pedestrian_classification_source": None}, "classification"),
        "bad_video_join": rejects(changed(slow, lambda p: p["trace"][150].update(video_frame=149)), "time join"),
        "missing_contact": rejects(changed(slow, lambda p: p["trace"][150].update(contact_source=None)), "Contact source"),
        "no_conflict": rejects(changed(slow, lambda p: [r.update(path_conflict_survey=False) for r in p["trace"]]), "No surveyed"),
        "missing_path_source": rejects({**slow, "path_survey_source": None}, "path survey"),
    }
    proof = {
        "format": "worker-pedestrian-due-care-meter-proof-v1",
        "source_kind": "synthetic_native_sample", "positive": positives,
        "negative_rejections": negatives,
        "source_assignment_sha256": "4e7330100013939e3ba5860cd522cd6951e5a4e44db2bdede4f71e98fcc8c98e",
        "actual_native_observed": False, "legal_verdict": None,
    }
    Path(__file__).with_name("due-care-meter-proof.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"positive": len(positives), "negative": len(negatives), "physical": False}))


if __name__ == "__main__":
    main()
