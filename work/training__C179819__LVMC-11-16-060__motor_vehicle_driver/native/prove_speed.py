"""CPU source-shaped speed diagnostics, never original Native evidence."""

import copy
import hashlib
import json
from pathlib import Path

from measure_speed import CAMERAS, FRAMES, MPH_TO_MPS, measure


def context():
    return {"source_kind": "native_speed_and_complete_sign_survey",
            "native_map_sha256": "1" * 64, "street_status_sha256": "2" * 64,
            "sign_survey_sha256": "3" * 64, "street_status": "city_street",
            "surveyed_route_interval_m": [0, 500],
            "survey_complete_both_directions": True,
            "applicable_posted_signs": []}


def trace(speed_mph):
    speed_mps = speed_mph * MPH_TO_MPS
    return [{"video_frame": i, "native_frame": 11000 + i, "time_s": i / 20,
             "source_cameras": {name: i for name in CAMERAS},
             "route_position_m": speed_mps * i / 20,
             "observed_speed_mps": speed_mps} for i in range(FRAMES)]


def reject(label, source, rows, expected):
    try:
        measure(source, rows)
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label} unexpectedly passed")


if __name__ == "__main__":
    source = context()
    slow, at, fast = [measure(source, trace(mph)) for mph in (20, 25, 30)]
    assert slow["default_frames_above_25_mph"] == at["default_frames_above_25_mph"] == 0
    assert fast["default_frames_above_25_mph"] == FRAMES
    posted = copy.deepcopy(source)
    posted["applicable_posted_signs"] = [{"governs_from_m": 0, "governs_to_m": 500,
                                         "limit_mph": 35, "pixel_sha256": "4" * 64}]
    displaced = measure(posted, trace(30))
    assert displaced["default_governed_frames"] == 0 and displaced["posted_governed_frames"] == FRAMES
    negative = []
    bad = copy.deepcopy(source)
    bad.pop("sign_survey_sha256")
    negative.append(reject("missing_sign_survey", bad, trace(25), "Missing source hash"))
    bad = copy.deepcopy(source)
    bad["survey_complete_both_directions"] = False
    negative.append(reject("incomplete_survey", bad, trace(25), "Incomplete sign-survey"))
    bad = copy.deepcopy(source)
    bad["surveyed_route_interval_m"] = [0, 100]
    negative.append(reject("route_outside_survey", bad, trace(25), "outside surveyed route"))
    negative.append(reject("short_capture", source, trace(25)[:-1], "Incomplete 30-second"))
    bad_rows = trace(25)
    bad_rows[200]["source_cameras"].pop("roadside_sign")
    negative.append(reject("missing_camera", source, bad_rows, "Four source camera"))
    proof = {"format": "worker-cpu-default-speed-proof", "passed": True,
             "diagnostic_only": True, "original_native_observed": False,
             "positive": {"20_mph": slow, "25_mph": at, "30_mph": fast,
                          "posted_35_mph": displaced}, "negative": negative}
    path = Path(__file__).with_name("speed-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negative),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
