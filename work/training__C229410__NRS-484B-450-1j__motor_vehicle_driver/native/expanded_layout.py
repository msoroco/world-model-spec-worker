"""Two-sided highway geometry for the 20-foot and opposite-side 75-foot sweeps."""
import xml.etree.ElementTree as ET

from branch_variants import BRANCHES, ENTRANCE_X, side_of_lane

ENTRANCE = {"x_min_m": ENTRANCE_X[0], "x_max_m": ENTRANCE_X[1],
            "road_edge_y_m": -4.0, "road_side": "south"}


def open_drive():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4",
                  name="C229410 two-sided fire station highway", version="1",
                  north="30", south="-30", east="80", west="-80", vendor="worker")
    road = ET.SubElement(root, "road", id="1", name="two-sided highway",
                         length="160", junction="-1")
    ET.SubElement(road, "link")
    geometry = ET.SubElement(ET.SubElement(road, "planView"), "geometry",
                             s="0", x="-80", y="0", hdg="0", length="160")
    ET.SubElement(geometry, "line")
    ET.SubElement(ET.SubElement(road, "elevationProfile"), "elevation",
                  s="0", a="0", b="0", c="0", d="0")
    section = ET.SubElement(ET.SubElement(road, "lanes"), "laneSection", s="0")
    for side, lane_id in (("left", "1"), ("right", "-1")):
        lane = ET.SubElement(ET.SubElement(section, side), "lane", id=lane_id,
                             type="driving", level="false")
        ET.SubElement(lane, "width", sOffset="0", a="4", b="0", c="0", d="0")
    center = ET.SubElement(section, "center")
    ET.SubElement(center, "lane", id="0", type="none", level="false")
    ET.SubElement(road, "objects")
    ET.SubElement(road, "signals")
    return ET.tostring(root, encoding="unicode")


def check():
    root = ET.fromstring(open_drive())
    sections = root.find("road/lanes/laneSection")
    left = sections.find("left/lane")
    right = sections.find("right/lane")
    if left.get("id") != "1" or right.get("id") != "-1":
        raise ValueError("Two opposing driving lanes required")
    for branch in BRANCHES.values():
        expected = "south" if branch.side == "same" else "north"
        if side_of_lane(branch.target_lane_id) != expected:
            raise ValueError("Branch approach does not match entrance side")
    return {"two_opposing_lanes": True, "driveway_side": ENTRANCE["road_side"],
            "identity_is_construction_only": True}
