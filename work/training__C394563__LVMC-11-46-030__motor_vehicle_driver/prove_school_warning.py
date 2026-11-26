"""CPU source-shaped school warning proof; sample motion is invented."""

import hashlib
import json
from pathlib import Path

from measure_school_warning import CAMERAS, FRAMES, FEET_PER_METRE, measure


def context():
    return {"source_kind": "original_native_school_warning_readback",
            "native_map_sha256": "1" * 64,
            "school_lane_geometry_sha256": "2" * 64,
            "vehicle_extent_sha256": "3" * 64,
            "warning_actor_sha256": "4" * 64,
            "warning_state_source_sha256": "5" * 64,
            "child_presence_source_sha256": "6" * 64,
            "school_pedestrian_lane_survey": True,
            "nearest_lane_side_x_m": 0.0,
            "vehicle_length_m": 4.0}


def trace(stop_center_ft=55, *, role="signal_device", release="signal_stopped", proceed_frame=250):
    stop_x = -stop_center_ft / FEET_PER_METRE
    rows = []
    for i in range(FRAMES):
        if i < 120:
            center = -60 + (stop_x + 60) * i / 120
            speed = (stop_x + 60) / 6
        elif i < proceed_frame:
            center, speed = stop_x, 0.0
        elif i < 400:
            center = stop_x + (20 - stop_x) * (i - proceed_frame) / (400 - proceed_frame)
            speed = (20 - stop_x) / ((400 - proceed_frame) / 20)
        else:
            center, speed = 20.0, 0.0
        rows.append({"video_frame": i, "native_frame": 50000 + i, "time_s": i / 20,
                     "source_cameras": {name: i for name in CAMERAS},
                     "vehicle_center_x_m": center, "observed_speed_mps": speed,
                     "warning_role": role, "warning_active": i < 250,
                     "children_about_to_cross_or_crossing": i < 250,
                     "release_event": release if i == 250 else None})
    return rows


def reject(label, source, rows, expected):
    try:
        measure(source, rows)
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label} unexpectedly passed")


if __name__ == "__main__":
    far = measure(context(), trace())
    near = measure(context(), trace(40))
    flagman = measure(context(), trace(role="flagman", release="flagman_go"))
    releases = {
        "signal_stopped": ("signal_device", "signal_stopped"),
        "signal_raised": ("signal_device", "signal_raised"),
        "signal_removed": ("signal_device", "signal_removed"),
        "flagman_go": ("flagman", "flagman_go"),
        "flagman_left": ("flagman", "flagman_left"),
        "person_go": ("other_person", "person_go"),
        "person_left": ("other_person", "person_left"),
    }
    release_proofs = {name: measure(context(), trace(role=role, release=event))
                      for name, (role, event) in releases.items()}
    assert all(value["first_release_event"] == key
               for key, value in release_proofs.items())
    early = measure(context(), trace(proceed_frame=200))
    assert 54.5 < far["stop_distance_to_nearest_school_lane_side_ft"]["centre"] < 55.5
    assert 39.5 < near["stop_distance_to_nearest_school_lane_side_ft"]["centre"] < 40.5
    assert far["proceeded_before_observed_release"] is False
    assert flagman["first_release_event"] == "flagman_go"
    assert early["proceeded_before_observed_release"] is True
    negatives = []
    source = context()
    source.pop("warning_actor_sha256")
    negatives.append(reject("missing_warning_actor", source, trace(), "source hash"))
    source = context()
    source["school_pedestrian_lane_survey"] = False
    negatives.append(reject("not_school_lane", source, trace(), "School pedestrian"))
    negatives.append(reject("short_capture", context(), trace()[:-1], "Incomplete 30-second"))
    rows = trace()
    rows[300]["source_cameras"].pop("approach")
    negatives.append(reject("missing_camera", context(), rows, "Four source camera"))
    rows = trace()
    rows[300]["native_frame"] = rows[299]["native_frame"]
    negatives.append(reject("duplicate_native_frame", context(), rows, "Native frame"))
    rows = trace()
    rows[100]["warning_role"] = "flagman"
    negatives.append(reject("role_changed", context(), rows, "actor changed"))
    rows = trace()
    rows[250]["release_event"] = "flagman_go"
    negatives.append(reject("wrong_release_role", context(), rows, "role differ"))
    rows = trace(role="other_person", release="signal_removed")
    negatives.append(reject("person_cannot_emit_device_release", context(), rows, "role differ"))
    rows = trace()
    rows[100]["children_about_to_cross_or_crossing"] = None
    negatives.append(reject("missing_child_warning", context(), rows, "Children warning"))
    proof = {"format": "worker-cpu-school-warning-proof", "passed": True,
             "diagnostic_only": True, "original_native_observed": False,
             "positive": {"requested_55_ft": far, "requested_40_ft": near,
                          "flagman_release": flagman, "early_proceed": early,
                          "statutory_release_variants": release_proofs},
             "negative": negatives}
    path = Path(__file__).with_name("school-warning-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negatives),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
