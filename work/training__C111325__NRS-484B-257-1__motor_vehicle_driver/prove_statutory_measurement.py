"""Source-shaped tests for every planned branch; fixtures are not recordings."""

from copy import deepcopy

from measure_statutory import CAMERAS, SOURCE_NAMES, diagnostic_hash, measure
from stop_yield_scene import CASES, request


def packet(case):
    scene = request(case)
    context = {
        "case_id": "training__C111325__NRS-484B-257-1__motor_vehicle_driver__" + case,
        "source_kind": "synthetic_diagnostic",
        "sign_kind": "yield" if case.startswith("yield_sign_") else "stop",
        "reference_kind": scene["stopping_reference"],
        "reference_x_m": -6 if scene["stopping_reference"] == "stop_line" else -5.5 if scene["stopping_reference"] == "crosswalk" else -4.1,
        "marked_line_present": scene["stop_line_marking"] is not None,
        "crosswalk_present": scene["crosswalk_marking"] is not None,
        "sight_ray_source": "synthetic sight-ray fixture" if scene["stopping_reference"] == "nearest_viewpoint" else None,
        "police_controlling": scene["police_controlling"],
        "signal_controlling": scene["signal_controlling"],
        "controlling_direction_source": "synthetic exception fixture" if scene["control_exception_source_required"] else None,
        "intersection_near_x_m": -3.5, "intersection_far_x_m": 3.5,
        "through_conflict_halfwidth_m": 3.5,
    }
    context.update({name + "_sha256": diagnostic_hash(name + case) for name in SOURCE_NAMES})
    rolling = case in {"roll_through_conflict", "yield_sign_no_slow_conflict", "through_occupancy_during_crossing"}
    rows = []
    for i in range(600):
        native = 800000 + i
        if rolling:
            x, speed = -45 + i * .25, 5.0
        else:
            x = -45 + min(i, 100) * .3575 if i <= 100 else (-9.25 if i < 250 else -9.25 + (i - 250) * .25)
            speed = 0.0 if 100 <= i < 250 else (7.15 if i < 100 else 5.0)
        rows.append({"video_frame": i, "native_frame": native, "time_s": i / 20,
                     "source_cameras": {name: native for name in CAMERAS},
                     "ego_x_m": x, "ego_length_m": 4.5, "ego_speed_mps": speed,
                     "through_y_m": -50 + i * .25, "through_length_m": 4.5,
                     "through_speed_mps": 5.0})
    return context, rows


def rejects(context, rows, case, fragment):
    try:
        measure(context, rows, context["case_id"] if case is None else case)
    except ValueError as error:
        if fragment not in str(error):
            raise AssertionError(str(error)) from error
        return
    raise AssertionError("Invalid saved source passed")


def main():
    for case in sorted(CASES):
        context, rows = packet(case)
        result = measure(context, rows, context["case_id"])
        assert result["sample_count"] == 600 and result["legal_verdict"] is None
        assert result["physical_acceptance_claimed"] is False
        assert result["intersection_entry_frame"] <= result["intersection_last_frame"]
        if case == "complete_stop_then_yield":
            assert len(result["rest_frames_before_reference"]) >= 100
            assert not result["simultaneous_occupancy_frames"]
        if case == "roll_through_conflict":
            assert not result["rest_frames_before_reference"]
            assert result["simultaneous_occupancy_frames"]
    context, rows = packet("complete_stop_then_yield")
    changed = deepcopy(context)
    changed.pop("reference_sha256")
    rejects(changed, rows, None, "source SHA-256")
    changed = deepcopy(context)
    changed["sign_kind"] = "yield"
    rejects(changed, rows, None, "Governing sign")
    changed = deepcopy(context)
    changed["signal_controlling"] = True
    rejects(changed, rows, None, "Control exception")
    changed_rows = deepcopy(rows)
    changed_rows[200]["source_cameras"].pop("approach")
    rejects(context, changed_rows, None, "source-camera")
    changed_rows = deepcopy(rows)
    changed_rows[200]["native_frame"] = changed_rows[199]["native_frame"]
    rejects(context, changed_rows, None, "identity join")
    rejects(context, rows[:-1], None, "Incomplete")
    context, rows = packet("stop_at_viewpoint_no_line_crosswalk")
    context["sight_ray_source"] = None
    rejects(context, rows, None, "sight-ray")
    print("10 statutory source-shaped measurements and 7 negative checks passed; no legal verdict")


if __name__ == "__main__":
    main()
