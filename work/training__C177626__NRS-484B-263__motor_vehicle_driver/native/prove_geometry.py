"""CPU proof of distinct access and highway geometry and merge connectivity."""

from copy import deepcopy
import xml.etree.ElementTree as ET

from geometry import open_drive, route_points, validate_topology


def reject(root, phrase):
    try:
        validate_topology(ET.tostring(root, encoding="unicode"))
    except ValueError as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError("expected rejection: " + phrase)


source = open_drive()
summary = validate_topology(source)
assert summary["route_kind"] == "entry"
assert not summary["controlled_access_designation_verified"]
assert summary["merge_centerline_gap_m"] == 0
assert summary["ego_waypoints"] > 400 and summary["highway_waypoints"] > 400
ego = route_points("ego_entry")
highway = route_points("highway_approach")
assert ego[0][1] < -35 and highway[0][1] == -1.75
assert ego[-1] == highway[-1]
try:
    route_points("exit")
except ValueError as exc:
    assert "unknown route" in str(exc)
else:
    raise AssertionError("exit route must not be silently represented by entry geometry")

root = ET.fromstring(source)
bad = deepcopy(root)
bad.find("junction/connection[@incomingRoad='3']").remove(
    bad.find("junction/connection[@incomingRoad='3']/laneLink"))
reject(bad, "driving lane link")
bad = deepcopy(root)
bad.find("road[@id='13']/link/successor").set("elementId", "4")
reject(bad, "join highway connector")
bad = deepcopy(root)
bad.find("road[@id='13']/planView/geometry").set("y", "-21.0")
reject(bad, "physical join")
bad = deepcopy(root)
bad.find("road[@id='3']/lanes/laneSection/right").clear()
reject(bad, "driving lane")
print("PASS: connected access-ramp/highway entry geometry, 4 negatives, no exit or legal-designation claim")
