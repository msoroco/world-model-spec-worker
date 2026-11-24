"""Exercise the 30-second source meter and negative source gates."""

import copy
import json
from pathlib import Path

from caution_meter import FRAMES, digest, measure


def packet(policy):
    rows = []
    ego_x = -90.0
    for frame in range(FRAMES):
        observed = frame >= 100
        speed = 8.0 if frame < 100 or policy == "maintain" else max(3.0, 8.0 - (frame - 100) / 20)
        ego_x += speed / 20
        rows.append({"frame": frame, "native_frame": frame + 2000,
                     "video_frame": frame, "time_s": frame / 20,
                     "ego_x_m": ego_x, "ego_y_m": 0.0,
                     "ped_x_m": 28.0, "ped_y_m": 3.2,
                     "ego_speed_mps": speed,
                     "line_of_sight_clear": frame >= 90,
                     "driver_observed_pedestrian": observed,
                     "driver_observation_source": "synthetic_native_sample" if observed else None})
    return {"format": "worker-pedestrian-caution-source-packet-v1",
            "source_kind": "synthetic_native_sample", "law_id": "NRS-484B-280-1c",
            "cell_id": "C230266", "actor": "motor_vehicle_driver",
            "vehicle_id": "vehicle-1", "pedestrian_id": "pedestrian-1",
            "pedestrian_classification_source": "synthetic_native_sample",
            "road_survey_source": "synthetic_native_sample",
            "driver_control_source": "synthetic_native_sample",
            "road_y_bounds_m": [-3.5, 3.5], "trace": rows, "trace_sha256": digest(rows)}


def rejects(p, expected):
    try:
        measure(p)
    except ValueError as error:
        assert expected in str(error), str(error)
        return str(error)
    raise AssertionError("Invalid source was accepted: " + expected)


def main():
    slow = packet("slow")
    maintain = packet("maintain")
    positive = {"slow": measure(slow), "maintain": measure(maintain)}
    assert positive["slow"]["first_actual_observation_frame"] == 100
    assert positive["slow"]["speed_2s_after_observation_mps"] < positive["maintain"]["speed_2s_after_observation_mps"]
    assert positive["slow"]["proper_caution_legal_verdict"] is None
    missing_observation = copy.deepcopy(slow)
    for row in missing_observation["trace"]:
        row["driver_observed_pedestrian"] = False
    missing_observation["trace_sha256"] = digest(missing_observation["trace"])
    no_provenance = copy.deepcopy(slow)
    no_provenance["trace"][100]["driver_observation_source"] = None
    no_provenance["trace_sha256"] = digest(no_provenance["trace"])
    off_road = copy.deepcopy(slow)
    for row in off_road["trace"]:
        row["ped_y_m"] = 5.0
    off_road["trace_sha256"] = digest(off_road["trace"])
    short = copy.deepcopy(slow)
    short["trace"].pop()
    short["trace_sha256"] = digest(short["trace"])
    bad_join = copy.deepcopy(slow)
    bad_join["trace"][200]["video_frame"] = 199
    bad_join["trace_sha256"] = digest(bad_join["trace"])
    negatives = {
        "missing_observation": rejects(missing_observation, "No sourced actual observation"),
        "missing_observation_provenance": rejects(no_provenance, "Actual observation provenance missing"),
        "off_road": rejects(off_road, "Pedestrian never on surveyed road"),
        "short_trace": rejects(short, "Full 600-frame source trace required"),
        "bad_video_join": rejects(bad_join, "Native and video frame identities required"),
        "stale_source_hash": rejects({**slow, "trace_sha256": "0" * 64}, "Source trace hash mismatch"),
    }
    result = {"format": "worker-pedestrian-caution-meter-proof-v1",
              "source_kind": "synthetic_native_sample", "positive": positive,
              "negative_rejections": negatives,
              "source_law_sha256": "0827867669d245099cb8da3a6ccdc3c6220b1f802f70118d25d63a6a4e675d84",
              "actual_native_observed": False, "legal_verdict": None}
    Path(__file__).with_name("caution-meter-proof.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"positive_cases": len(positive), "negative_rejections": len(negatives),
                      "first_observation_frame": 100, "physical_execution": False}))


if __name__ == "__main__":
    main()
