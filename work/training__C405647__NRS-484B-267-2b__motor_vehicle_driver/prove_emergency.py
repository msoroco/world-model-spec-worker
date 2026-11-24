"""CPU source-shaped diagnostics; fixture motion and source hashes are invented."""

import hashlib
import json
from pathlib import Path

from measure_emergency import CAMERAS, FRAMES, measure


def context():
    source = {"source_kind": "original_native_emergency_readback", "emergency_role": "authorized_emergency",
              "lamps_meet_nrs_484a_480_3": True, "moving_branch": True}
    for i, name in enumerate(("native_map", "ego_blueprint", "emergency_actor", "emergency_role_source",
                              "flashing_lamp_source", "vehicle_extent", "visibility_source", "officer_direction_source"), 1):
        source[name + "_sha256"] = f"{i:x}" * 64
    return source


def trace(*, ego_speed=8.0, lateral_gap=2.4, officer="none"):
    rows = []
    for i in range(FRAMES):
        time = i / 20
        rows.append({"video_frame": i, "native_frame": 100000 + i, "time_s": time,
                     "source_cameras": {name: i for name in CAMERAS},
                     "ego_center_x_m": -70 + ego_speed * time,
                     "emergency_center_x_m": -15 + 1.5 * time,
                     "ego_speed_mps": ego_speed, "emergency_speed_mps": 1.5,
                     "surface_gap_m": lateral_gap, "ego_deceleration_mps2": 0.0,
                     "emergency_visible": True, "flashing_lamps_visible": True,
                     "officer_direction": officer})
    return rows


def rejects(label, source, rows, expected):
    try:
        measure(source, rows)
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label} unexpectedly passed")


if __name__ == "__main__":
    slow = measure(context(), trace(ego_speed=5.0, lateral_gap=2.4))
    fast = measure(context(), trace(ego_speed=8.0, lateral_gap=0.8))
    directed = measure(context(), trace(officer="stop"))
    assert slow["minimum_passing_surface_gap_m"] == 2.4
    assert fast["minimum_passing_surface_gap_m"] == 0.8
    assert slow["ego_speed_at_first_pass_mps"] == 5.0
    assert fast["ego_speed_at_first_pass_mps"] == 8.0
    assert directed["officer_direction_states"] == ["stop"]
    assert all(item["legal_compliance"] == "unassessed" for item in (slow, fast, directed))
    negatives = []
    source = context()
    source.pop("flashing_lamp_source_sha256")
    negatives.append(rejects("missing_lamp_source", source, trace(), "source hash"))
    source = context()
    source["lamps_meet_nrs_484a_480_3"] = False
    negatives.append(rejects("unqualified_lamps", source, trace(), "flashing-lamp"))
    source = context()
    source["emergency_role"] = "ordinary_vehicle"
    negatives.append(rejects("ordinary_vehicle", source, trace(), "role"))
    negatives.append(rejects("short_capture", context(), trace()[:-1], "Incomplete"))
    rows = trace()
    rows[100]["source_cameras"].pop("passing_gap")
    negatives.append(rejects("missing_camera", context(), rows, "Four source camera"))
    rows = trace()
    rows[100]["native_frame"] = rows[99]["native_frame"]
    negatives.append(rejects("duplicate_native_frame", context(), rows, "Native frame"))
    rows = trace()
    for row in rows:
        row["flashing_lamps_visible"] = False
    negatives.append(rejects("no_visible_lamps", context(), rows, "No sourced approach"))
    rows = trace()
    for row in rows:
        row["emergency_speed_mps"] = 0.0
    negatives.append(rejects("not_moving", context(), rows, "No sourced approach"))
    proof = {"format": "worker-cpu-emergency-approach-proof", "passed": True,
             "diagnostic_only": True, "original_native_observed": False,
             "positive": {"slow_wide": slow, "fast_narrow": fast, "officer_direction": directed},
             "negative": negatives}
    path = Path(__file__).with_name("emergency-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negatives),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
