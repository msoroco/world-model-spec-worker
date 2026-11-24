"""CPU source-shaped district 90/100/110-foot and weather proof."""

import hashlib
import json
from pathlib import Path

from measure_district_signal import FRAMES, measure

HERE = Path(__file__).resolve().parent


def context(district="residential"):
    result = {"source_kind": "original_native_district_signal_readback",
              "district_class": district, "district_survey_verified": True,
              "turn_direction": "left"}
    for index, name in enumerate(("native_map", "land_use_survey", "frontage_evidence",
                                  "indicator_state_source", "ego_pose_source", "course_change_source",
                                  "weather_source"), 1):
        result[name + "_sha256"] = f"{index:x}" * 64
    return result


def trace(distance_ft=100, weather="clear_noon"):
    turn = 500
    onset = turn - round(distance_ft * 0.3048 / 0.2)
    return [{"video_frame": i, "native_frame": 300000 + i, "time_s": i / 20,
             "source_cameras": {name: i for name in ("overview", "approach", "reference_corner", "driver_reference")},
             "district_class": "residential", "indicator": "left" if onset <= i <= turn else "off",
             "course_change": i == turn, "ego_xy_m": [-80 + i * 0.2, 0], "weather": weather}
            for i in range(FRAMES)]


def reject(label, source, rows, expected):
    try:
        measure(source, rows)
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label} unexpectedly passed")


if __name__ == "__main__":
    positive = {str(feet): measure(context(), trace(feet)) for feet in (90, 100, 110)}
    rain = measure(context(), trace(100, "rain"))
    assert [positive[str(feet)]["continuous_signal_distance_ft"] for feet in (90, 100, 110)] == sorted(
        positive[str(feet)]["continuous_signal_distance_ft"] for feet in (90, 100, 110))
    assert positive["100"]["statutory_district_distance_ft"] == 100
    assert positive["100"]["continuous_signal_distance_ft"] == rain["continuous_signal_distance_ft"]
    assert rain["observed_weather_states"] == ["rain"]
    assert all(item["legal_compliance"] == "unassessed" and item["original_native_observed"] is False
               for item in [*positive.values(), rain])
    negative = []
    source = context()
    source.pop("frontage_evidence_sha256")
    negative.append(reject("missing_frontage_source", source, trace(), "source hash"))
    source = context()
    source["district_survey_verified"] = False
    negative.append(reject("unverified_district", source, trace(), "district not sourced"))
    source = context("any_other_area")
    negative.append(reject("wrong_area", source, trace(), "district not sourced"))
    negative.append(reject("short_capture", context(), trace()[:-1], "Incomplete"))
    rows = trace()
    rows[400]["source_cameras"].pop("driver_reference")
    negative.append(reject("missing_camera", context(), rows, "Four source camera"))
    rows = trace()
    rows[400]["native_frame"] = rows[399]["native_frame"]
    negative.append(reject("duplicate_native_frame", context(), rows, "Native frame"))
    rows = trace()
    rows[450]["indicator"] = "off"
    measured = measure(context(), rows)
    assert measured["continuous_signal_distance_ft"] < positive["100"]["continuous_signal_distance_ft"]
    negative.append({"test": "signal_gap_reduces_continuous_distance", "measured_distance_ft": measured["continuous_signal_distance_ft"]})
    proof = {"format": "worker-cpu-district-signal-proof", "passed": True,
             "diagnostic_only": True, "original_native_observed": False,
             "positive": {**positive, "100_rain": rain}, "negative": negative}
    path = HERE / "district-signal-proof.json"
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negative),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
