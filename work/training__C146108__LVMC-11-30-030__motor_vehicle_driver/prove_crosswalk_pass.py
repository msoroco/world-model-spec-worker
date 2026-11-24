"""Synthetic source-shaped marked-crosswalk overtake comparison proof."""

import hashlib
import json
from pathlib import Path

from crosswalk_pass_scene import CASES, request, validate
from measure_crosswalk_pass import CAMERAS, FRAMES, HASHES, measure


def context():
    result = {"source_kind": "original_native_crosswalk_pass_readback",
              "marked_crosswalk": True, "same_direction_rear_approach": True,
              "lead_stopped_for_pedestrian_sourced": True,
              "crosswalk_near_x_m": -2, "crosswalk_far_x_m": 2,
              "lead_center_x_m": -6}
    for name in HASHES:
        result[name + "_sha256"] = hashlib.sha256(("synthetic-fixture:" + name).encode()).hexdigest()
    return result


def trace(case):
    rows = []
    for i in range(FRAMES):
        if case == "true":
            ego_x = -40 + 0.25 * i
            ego_y = -1.75 if i < 60 else (-1.75 - (i - 60) * 3.5 / 20 if i < 80 else -5.25)
        elif case == "false":
            ego_x, ego_y = -40 + min(i, 120) * 27 / 120, -1.75
        else:
            raise ValueError("Unknown fixture")
        ped_y = max(-8, min(8, -4 + (i - 120) * 0.08))
        rows.append({"video_frame": i, "native_frame": 950000 + i, "time_s": i / 20,
                     "source_cameras": {name: i for name in CAMERAS},
                     "ego_x_m": ego_x, "ego_y_m": ego_y, "ego_length_m": 4.5,
                     "lead_y_m": -1.75, "lead_length_m": 4.5, "lead_speed_mps": 0,
                     "pedestrian_y_m": ped_y})
    return rows


def reject(label, source, rows, expected):
    try:
        measure(source, rows)
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(label + " unexpectedly passed")


if __name__ == "__main__":
    scenes = {case: validate(request(case)) for case in CASES}
    hold = measure(context(), trace("false"))
    passing = measure(context(), trace("true"))
    assert hold["pass_observed"] is False and passing["pass_observed"] is True
    assert not hold["adjacent_longitudinal_overlap_frames"]
    assert passing["adjacent_longitudinal_overlap_frames"]
    assert passing["passed_lead_during_pedestrian_crossing_frames"]
    assert hold["legal_compliance"] == passing["legal_compliance"] == "unassessed"
    negative = []
    source = context()
    source.pop("crosswalk_marking_sha256")
    negative.append(reject("missing_crosswalk_source", source, trace("true"), "source hash"))
    source = context()
    source["lead_stopped_for_pedestrian_sourced"] = False
    negative.append(reject("unsourced_stop_purpose", source, trace("true"), "Purpose"))
    negative.append(reject("short_capture", context(), trace("true")[:-1], "Incomplete"))
    rows = trace("true")
    rows[200]["source_cameras"].pop("lead_rear")
    negative.append(reject("missing_camera", context(), rows, "camera"))
    rows = trace("true")
    rows[200]["native_frame"] = rows[199]["native_frame"]
    negative.append(reject("duplicate_native_frame", context(), rows, "Native frame"))
    rows = trace("true")
    rows[200]["lead_speed_mps"] = 2
    negative.append(reject("moving_lead", context(), rows, "Lead not stopped"))
    rows = trace("true")
    for row in rows:
        row["pedestrian_y_m"] = 20
    negative.append(reject("absent_pedestrian_crossing", context(), rows, "pedestrian crossing"))
    proof = {"format": "worker-cpu-crosswalk-pass-proof", "passed": True,
             "diagnostic_only": True, "original_native_observed": False,
             "scenes": scenes, "positive": {"hold_behind": hold, "pass_stopped_lead": passing},
             "negative": negative}
    path = Path(__file__).with_name("crosswalk-pass-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negative),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
