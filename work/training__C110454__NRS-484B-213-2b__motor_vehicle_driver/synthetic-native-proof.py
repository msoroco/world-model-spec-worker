"""480-frame saved measurement integration on authored CPU traces only."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("measure", HERE / "native/measure.py")
measure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure)
OUT = HERE / "../../.runtime-work/c110454-synthetic-native"


def rows(route):
    result = []
    for i in range(480):
        x, y = route[min(i * 2, len(route) - 1)]
        result.append({"video_frame": i, "native_frame": i,
                       "time_s": round(i * .05, 4),
                       "body_xy_m": [[x-2.6,y-1.1],[x-2.6,y+1.1],
                                     [x+2.6,y+1.1],[x+2.6,y-1.1]],
                       "speed_m_s": 4.0 if i < 450 else 0.0,
                       "two_way_native_survey": True})
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    outcomes = {}
    for case in ("reference", "contrast"):
        route = json.loads((HERE / "native/routes" / (case + ".json")).read_text())
        source = OUT / (case + "-native-samples.json")
        samples = rows(route)
        source.write_text(json.dumps(samples))
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        result = measure.measure(samples, source, digest)
        expected = "outside_100_ft" if case == "reference" else "within_100_ft"
        if result["sampled_relation"] != expected:
            raise ValueError("Controlled synthetic threshold relation differs")
        negative = [dict(row) for row in samples]
        negative[90]["native_frame"] = -1
        try:
            measure.measure(negative, source, digest)
        except ValueError as error:
            if "join" not in str(error):
                raise
        else:
            raise ValueError("Missing-source-frame negative was accepted")
        outcomes[case] = result
    if not (outcomes["reference"]["nearest_body_front_to_intersection_m"] > 30.48 >
            outcomes["contrast"]["nearest_body_front_to_intersection_m"]):
        raise ValueError("Measured synthetic pair does not bracket threshold")
    print(json.dumps({"passed": True, "frames_per_case": 480,
                      "case_measurements": outcomes,
                      "missing_join_negative_rejected": True,
                      "synthetic_only": True, "physical_claim": False}))


if __name__ == "__main__":
    main()
