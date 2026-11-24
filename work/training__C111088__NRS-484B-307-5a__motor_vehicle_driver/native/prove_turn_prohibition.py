"""CPU source-shaped turn/straight diagnostics; no Native behavior inferred."""

import hashlib
import json
from pathlib import Path

from measure_turn_prohibition import CAMERAS, FRAMES, measure

HERE = Path(__file__).resolve().parent


def context(direction="left"):
    result = {"source_kind": "original_native_straight_arrow_turn_readback",
              "signal_face_verified": True, "sole_straight_arrow_verified": True,
              "ego_route_direction": direction, "intersection_x_bounds_m": [-10, 10]}
    for index, name in enumerate(("native_map", "intersection_geometry", "governing_signal_actor",
                                  "signal_phase_source", "ego_body_source", "ego_pose_source",
                                  "signal_pixel_review"), 1):
        result[name + "_sha256"] = f"{index:x}" * 64
    return result


def trace(direction="left"):
    rows = []
    for i in range(FRAMES):
        if direction == "straight":
            heading = 0.0
        else:
            turn = max(0.0, min(1.0, (i - 250) / 100))
            heading = (70 if direction == "left" else -70) * turn
        rows.append({"video_frame": i, "native_frame": 400000 + i, "time_s": i / 20,
                     "source_cameras": {name: i for name in CAMERAS},
                     "ego_center_x_m": -30 + 0.1 * i, "ego_heading_deg": heading,
                     "governing_phase": "sole_green_straight_arrow", "additional_turn_lamp_on": False})
    return rows


def reject(label, source, rows, expected):
    try:
        measure(source, rows)
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label} unexpectedly passed")


if __name__ == "__main__":
    straight = measure(context("straight"), trace("straight"))
    left = measure(context("left"), trace("left"))
    right = measure(context("right"), trace("right"))
    assert not straight["turn_observed_by_30_degree_diagnostic"]
    assert left["turn_observed_by_30_degree_diagnostic"]
    assert right["turn_observed_by_30_degree_diagnostic"]
    assert all(item["legal_compliance"] == "unassessed" for item in (straight, left, right))
    negative = []
    source = context()
    source.pop("signal_pixel_review_sha256")
    negative.append(reject("missing_pixel_review", source, trace(), "source hash"))
    source = context()
    source["sole_straight_arrow_verified"] = False
    negative.append(reject("unverified_sole_arrow", source, trace(), "not sourced"))
    negative.append(reject("short_capture", context(), trace()[:-1], "incomplete"))
    rows = trace()
    rows[300]["source_cameras"].pop("reference_corner")
    negative.append(reject("missing_camera", context(), rows, "Four source camera"))
    rows = trace()
    rows[300]["native_frame"] = rows[299]["native_frame"]
    negative.append(reject("duplicate_native_frame", context(), rows, "Native frame"))
    rows = trace()
    rows[300]["additional_turn_lamp_on"] = True
    negative.append(reject("turn_lamp_on", context(), rows, "Sole straight arrow"))
    rows = trace()
    rows[300]["governing_phase"] = "other"
    negative.append(reject("other_phase", context(), rows, "Sole straight arrow"))
    rows = trace()
    for row in rows:
        row["ego_center_x_m"] = -30
    negative.append(reject("no_intersection_entry", context(), rows, "No observed intersection"))
    proof = {"format": "worker-cpu-straight-arrow-turn-proof", "passed": True,
             "diagnostic_only": True, "original_native_observed": False,
             "positive": {"straight": straight, "left_turn": left, "right_turn": right},
             "negative": negative}
    path = HERE / "turn-prohibition-proof.json"
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negative),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
