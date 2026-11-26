"""Exercise each alternative with 30-second source-shaped CPU packets."""

import copy
import hashlib
import json
from pathlib import Path

from branch_meter import BRANCH_SOURCES, measure


HERE = Path(__file__).resolve().parent


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def packet(branch):
    trace = [{"frame": n, "native_frame": 2000 + n, "video_frame": n,
              "time_s": n / 20, "ego_x_m": n * 0.2, "ego_y_m": 0.0,
              "ped_x_m": 52.0, "ped_y_m": 1.0, "ego_speed_mps": 5.0,
              "line_of_sight_clear": n >= 50,
              "driver_observed_pedestrian": None, "driver_observation_source": None,
              "branch_position_evidenced": n >= 30} for n in range(600)]
    return {"format": "worker-pedestrian-caution-branch-source-v1",
            "law_id": "NRS-484B-280-1c", "cell_id": "C230266",
            "actor": "motor_vehicle_driver", "branch": branch,
            "ego_id": "ego-1", "pedestrian_id": "ped-2",
            "pedestrian_classification_source": "synthetic Native actor metadata fixture",
            "survey": {key: f"synthetic source for {key}" for key in BRANCH_SOURCES[branch]},
            "trace": trace, "trace_sha256": digest(trace)}


def rejected(value, phrase):
    try:
        measure(value)
    except ValueError as exc:
        if phrase not in str(exc):
            raise AssertionError(f"Expected {phrase}, received {exc}") from exc
        return str(exc)
    raise AssertionError(f"Missing expected rejection: {phrase}")


def main():
    positive = {}
    negative = {}
    for branch in BRANCH_SOURCES:
        value = packet(branch)
        measured = measure(value)
        assert measured["branch"] == branch and measured["frames"] == 600
        assert measured["actual_driver_observation_unverified"]
        positive[branch] = {"frames": measured["frames"],
                            "source_kind": "synthetic_software_fixture",
                            "legal_verdict": measured["proper_caution_legal_verdict"]}
        broken = copy.deepcopy(value)
        key = BRANCH_SOURCES[branch][0]
        broken["survey"].pop(key)
        negative[branch] = rejected(broken, f"Missing original {key}")
    value = packet("road")
    bad = copy.deepcopy(value)
    bad["trace"][0]["video_frame"] = 4
    negative["bad_join"] = rejected(bad, "Stale trace hash")
    bad["trace_sha256"] = digest(bad["trace"])
    negative["bad_join_after_rehash"] = rejected(bad, "Frame/video/Native time join failed")
    bad = copy.deepcopy(value)
    bad["trace"] = bad["trace"][:599]
    negative["short_trace"] = rejected(bad, "Full 600-frame trace required")
    bad = copy.deepcopy(value)
    bad["trace"][100]["driver_observed_pedestrian"] = True
    bad["trace_sha256"] = digest(bad["trace"])
    negative["unproven_observation"] = rejected(bad, "Actual observation provenance missing")
    report = {"format": "worker-pedestrian-caution-branch-cpu-proof-v1",
              "positive": positive, "negative_rejections": negative,
              "positive_count": len(positive), "negative_count": len(negative),
              "physical_execution_proven": False}
    path = HERE / "branch-meter-proof.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"positive": len(positive), "negative": len(negative)}))


if __name__ == "__main__":
    main()
