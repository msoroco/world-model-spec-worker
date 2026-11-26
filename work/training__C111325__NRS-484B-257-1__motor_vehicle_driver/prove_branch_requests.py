"""Check source-distinct scene requests without claiming CARLA realization."""

from copy import deepcopy

from stop_yield_scene import CASES, request, validate


def rejects(payload, fragment):
    try:
        validate(payload)
    except ValueError as error:
        if fragment not in str(error):
            raise AssertionError(str(error)) from error
        return
    raise AssertionError("Invalid scene request was accepted")


def main():
    for case in sorted(CASES):
        payload = request(case)
        proof = validate(payload)
        assert proof["case"] == case and proof["planned_frames"] == 600
        assert proof["native_geometry_verified"] is False
        assert len(payload["cameras"]) == 4
        assert payload["police_controlling"] != payload["signal_controlling"] or not payload["police_controlling"]
        if case.startswith("yield_sign_"):
            assert payload["governing_sign"] == "yield-111325"
        if case == "stop_at_viewpoint_no_line_crosswalk":
            assert payload["stop_line_marking"] is None and payload["crosswalk_marking"] is None
        if case == "stop_before_crosswalk_no_line":
            assert payload["stop_line_marking"] is None and payload["crosswalk_marking"] is not None
    missing = deepcopy(request("stop_before_crosswalk_no_line"))
    missing["crosswalk_marking"] = None
    rejects(missing, "crosswalk hierarchy")
    missing = deepcopy(request("stop_at_viewpoint_no_line_crosswalk"))
    missing["nearest_viewpoint_candidate"] = None
    rejects(missing, "Nearest-viewpoint hierarchy")
    missing = deepcopy(request("police_directed_control"))
    missing["control_exception_source_required"] = None
    rejects(missing, "Control exception source")
    missing = deepcopy(request("yield_sign_slow_then_yield"))
    missing["governing_sign"] = "stop-111325"
    rejects(missing, "Governing sign")
    missing = deepcopy(request("complete_stop_then_yield"))
    missing["through_vehicle"]["start_xyz"][0] = -2
    rejects(missing, "Actors not placed")
    missing = deepcopy(request("complete_stop_then_yield"))
    missing["cameras"].append(deepcopy(missing["cameras"][0]))
    rejects(missing, "Four camera")
    print("10 branch scene requests and 6 negative checks passed; physical realization unverified")


if __name__ == "__main__":
    main()
