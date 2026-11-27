"""CPU checks for exact source-shaped passenger curb construction requests."""

from copy import deepcopy

from loading_scene import CASES, request, validate


def reject(scene, phrase):
    try:
        validate(scene)
    except ValueError as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError("expected rejection: " + phrase)


for slug in CASES:
    scene = request(slug)
    checked = validate(scene)
    assert checked["camera_count"] == 4 and checked["planned_frames"] == 600
    assert scene["zone"]["civil_timestamp_start"].endswith("-08:00")
    assert scene["zone"]["curb_start_x_m"] < scene["ego"]["target_halt_center_x_m"] < scene["zone"]["curb_end_x_m"]
    assert scene["passenger"]["cross_doorway_requested"] is CASES[slug]
    assert ("19:00:00" in scene["zone"]["civil_timestamp_start"]) is slug.startswith("outside_hours")
    if slug in {"brief_stop_no_transfer", "extended_park_no_transfer"}:
        assert scene["controller"]["door_open_request_frame"] is None

scene = request("condition_a")
bad = deepcopy(scene)
bad["road_opendrive"] = bad["road_opendrive"].replace("passenger-zone-curb-149498", "missing-curb")
reject(bad, "marked passenger curb")
bad = deepcopy(scene)
bad["road_opendrive"] = bad["road_opendrive"].replace("passenger-loading-sign-149498", "missing-sign")
reject(bad, "effective-hours sign")
bad = deepcopy(scene)
bad["zone"]["legal_authority"] = "valid"
reject(bad, "authority cannot be presumed")
bad = deepcopy(scene)
bad["passenger"]["cross_doorway_requested"] = False
reject(bad, "comparison passenger request")
bad = deepcopy(scene)
bad["cameras"] = bad["cameras"][:-1]
reject(bad, "four-camera")
bad = deepcopy(scene)
bad["planned_frames"] = 599
reject(bad, "20 Hz")
bad = deepcopy(request("outside_hours_loading"))
bad["zone"]["civil_timestamp_start"] = scene["zone"]["civil_timestamp_start"]
reject(bad, "signed-hours contrast")
bad = deepcopy(request("brief_stop_no_transfer"))
bad["controller"]["resume_request_frame"] = 590
reject(bad, "action and duration")
print("PASS: six exact passenger curb source requests and nine negative checks")
