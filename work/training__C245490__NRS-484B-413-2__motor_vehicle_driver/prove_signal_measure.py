"""Synthetic source-shaped tests; no Native observation or legal verdict."""
from __future__ import annotations

import json
from measure_signal import measure


def rows(distance_ft: int, *, interruption: bool = False,
         side: str = 'left', weather: str = 'clear') -> list[dict]:
    # 20 Hz; the event is frame 20. The indicator begins at frame 10.
    step_m = distance_ft * 0.3048 / 10
    result = [{"frame": i, "time_s": i / 20, "ego_xy_m": [i * step_m, 0],
               "turn_indicator": side if i >= 10 else "off",
               "original_weather": weather,
               "course_change": i == 20} for i in range(23)]
    if interruption:
        result[15]["turn_indicator"] = "off"
    return result


def reject(sample: list[dict], area: str, reason: str) -> None:
    try:
        measure(sample, area)
    except ValueError as error:
        assert reason in str(error), (reason, error)
    else:
        raise AssertionError("invalid saved source accepted: " + reason)


def main() -> None:
    tested = []
    for area, threshold in (("business_or_residential", 100), ("other", 300)):
        for offset in (-1, 0, 1):
            distance = threshold + offset
            proof = measure(rows(distance), area)
            assert abs(proof["observed_continuous_distance_ft"] - distance) < 1e-9
            assert proof["threshold_ft"] == threshold
            tested.append({"area": area, "requested_fixture_distance_ft": distance,
                           "measured_fixture_distance_ft": proof["observed_continuous_distance_ft"]})
        interrupted = measure(rows(threshold + 1, interruption=True), area)
        assert abs(interrupted["observed_continuous_distance_ft"] - (threshold + 1) * 0.4) < 1e-9
        for weather in ('clear', 'rain'):
            for side in ('left', 'right'):
                variant = measure(rows(threshold, side=side, weather=weather), area)
                assert variant['threshold_ft'] == threshold
                assert abs(variant['observed_continuous_distance_ft'] - threshold) < 1e-9
    sample = rows(100)
    reject(sample, "unknown", "verified area")
    reject(sample[:1], "other", "three saved")
    sample = rows(100); sample[13].pop("ego_xy_m")
    reject(sample, "other", "observed pose")
    sample = rows(100); sample[12]["frame"] = 13
    reject(sample, "other", "saved frame")
    sample = rows(100); sample[12]["time_s"] += 0.01
    reject(sample, "other", "time discontinuity")
    sample = rows(100); sample[20]["course_change"] = False
    reject(sample, "other", "course-change")
    sample = rows(100); sample[10]["turn_indicator"] = "right"
    assert measure(sample, "other")["onset_frame"] == 11
    print(json.dumps({"format": "c245490-signal-distance-cpu-proof-v1",
                      "passed": True, "boundary_probes": tested,
                      "interruption_probes": 2, "weather_direction_probes": 8,
                      "negative_source_probes": 6,
                      "source_kind": "synthetic_native_sample",
                      "physical_or_legal_result": None}, sort_keys=True))


if __name__ == "__main__":
    main()
