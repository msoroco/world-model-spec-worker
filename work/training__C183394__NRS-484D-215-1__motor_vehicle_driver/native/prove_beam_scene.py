"""Exercise both authored cases, threshold and rejected incomplete constructions."""
import copy
import xml.etree.ElementTree as ET

from beam_scene import MODES, beam_request, request, validate_request


def reject(action, phrase):
    try:
        action()
    except ValueError as error:
        assert phrase in str(error), str(error)
    else:
        raise AssertionError("expected rejection: " + phrase)


assert beam_request("dim_within_500", 152.4) == "low_beam"
assert beam_request("dim_within_500", 152.401) == "high_beam"
assert beam_request("retain_high", 152.4) == "high_beam"
reject(lambda: beam_request("retain_high", float("nan")), "measured")
for case in MODES:
    plan = request(case)
    assert validate_request(plan)["camera_count"] == 4
    assert plan["lighting"]["trigger_source"] == "NRS-484D-100-1"
    assert plan["ego"]["start_xyz_m"][1] < -3.5
    assert plan["oncoming"]["start_xyz_m"][1] > 0
    assert plan["lighting"]["lowermost_distribution_claimed"] is False
    bad = copy.deepcopy(plan)
    bad["oncoming"]["heading_deg"] = 0
    reject(lambda: validate_request(bad), "opposed")
    bad = copy.deepcopy(plan)
    bad["cameras"] = bad["cameras"][:-1]
    reject(lambda: validate_request(bad), "four distinct")
    bad = copy.deepcopy(plan)
    root = ET.fromstring(bad["road_opendrive"])
    shoulder = next(lane for lane in root.findall("road/lanes/laneSection/*/lane")
                    if lane.attrib["id"] == "-2")
    shoulder.attrib["type"] = "driving"
    bad["road_opendrive"] = ET.tostring(root, encoding="unicode")
    reject(lambda: validate_request(bad), "adjacent shoulder")
    bad = copy.deepcopy(plan)
    bad["lighting"]["lowermost_distribution_claimed"] = True
    reject(lambda: validate_request(bad), "cannot claim")
print("PASS: shoulder and opposed-vehicle scene requests, beam contrast and source negatives")
