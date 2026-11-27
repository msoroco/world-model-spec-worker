"""Pure requested one-lane scooter pass plans; original Native readback is required."""

from dataclasses import dataclass
import math
import xml.etree.ElementTree as ET

HZ = 20
FRAMES = 600
LANE_WIDTH_M = 3.5
RIGHT_CENTER_M = -1.75
OPPOSING_CENTER_M = 1.75
SCOOTER_Y_M = -2.3
EGO_HALF_WIDTH_M = 0.9
SCOOTER_HALF_WIDTH_M = 0.35
FOOT_M = 0.3048
PASS_TARGETS_M = {
    "witness_1": 1.2,
    "witness_2": 0.8,
    "exception_1_1": 1.2,
    "exception_1_2": 1.2,
    "numeric_1_0": 2.9 * FOOT_M,
    "numeric_1_1": 3.0 * FOOT_M,
    "numeric_1_2": 3.1 * FOOT_M,
    "ordering_1": 1.2,
    "ordering_2": 1.2,
}


@dataclass(frozen=True)
class Target:
    frame: int
    ego_x_m: float
    ego_y_m: float
    scooter_x_m: float
    scooter_y_m: float
    center_crossing_requested: bool
    no_passing_marking_requested: bool


def _smooth(v):
    v = max(0.0, min(1.0, v))
    return v * v * (3 - 2 * v)


def target(suffix, frame):
    if suffix not in PASS_TARGETS_M:
        raise ValueError("Unknown selected case")
    if type(frame) is not int or not 0 <= frame < FRAMES:
        raise ValueError("Frame outside 600-frame plan")
    t = frame / HZ
    # The measured body clearance is a target, never an observed value.
    pass_y = SCOOTER_Y_M + SCOOTER_HALF_WIDTH_M + EGO_HALF_WIDTH_M + PASS_TARGETS_M[suffix]
    ego_x = -30 + 4 * t
    scooter_x = -10 + 2 * t
    return_begin = 190 if suffix == "ordering_1" else 340
    return_end = return_begin + 60
    if frame < 100:
        y = RIGHT_CENTER_M + _smooth(frame / 100) * (pass_y - RIGHT_CENTER_M)
    elif frame < return_begin:
        y = pass_y
    elif frame < return_end:
        y = pass_y + _smooth((frame - return_begin) / 60) * (RIGHT_CENTER_M - pass_y)
    else:
        y = RIGHT_CENTER_M
    return Target(frame, ego_x, y, scooter_x, SCOOTER_Y_M, y > 0.0,
                  suffix == "exception_1_2")


def open_drive(no_passing=False):
    """A straight road with exactly one driving lane in each direction."""
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4", name="C272412-scooter-pass",
                  version="1", north="30", south="-30", east="300", west="-100",
                  vendor="full-train-worker")
    road = ET.SubElement(root, "road", id="1", name="opposing-single-lanes",
                         length="400", junction="-1")
    ET.SubElement(road, "link")
    geometry = ET.SubElement(ET.SubElement(road, "planView"), "geometry",
                             s="0", x="-100", y="0", hdg="0", length="400")
    ET.SubElement(geometry, "line")
    ET.SubElement(ET.SubElement(road, "elevationProfile"), "elevation",
                  s="0", a="0", b="0", c="0", d="0")
    lanes = ET.SubElement(road, "lanes")
    ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
    section = ET.SubElement(lanes, "laneSection", s="0")
    for side, lane_id in (("left", 1), ("right", -1)):
        element = ET.SubElement(section, side)
        lane = ET.SubElement(element, "lane", id=str(lane_id), type="driving", level="false")
        ET.SubElement(lane, "width", sOffset="0", a=str(LANE_WIDTH_M), b="0", c="0", d="0")
        ET.SubElement(lane, "roadMark", sOffset="0", type="solid" if no_passing else "broken",
                      color="yellow", width="0.12")
    center = ET.SubElement(section, "center")
    ET.SubElement(center, "lane", id="0", type="none", level="false")
    ET.SubElement(road, "objects")
    ET.SubElement(road, "signals")
    return ET.tostring(root, encoding="unicode")


def check():
    for marking in (False, True):
        root = ET.fromstring(open_drive(marking))
        lanes = root.findall("road/lanes/laneSection/left/lane") + root.findall("road/lanes/laneSection/right/lane")
        if [int(lane.attrib["id"]) for lane in lanes] != [1, -1]:
            raise ValueError("One lane per direction changed")
        if any(float(lane.find("width").attrib["a"]) != LANE_WIDTH_M for lane in lanes):
            raise ValueError("Lane width changed")
        if any(lane.find("roadMark").attrib["type"] != ("solid" if marking else "broken") for lane in lanes):
            raise ValueError("No-passing marking construction changed")
    for suffix in PASS_TARGETS_M:
        rows = [target(suffix, frame) for frame in range(FRAMES)]
        overlap = [row for row in rows if abs(row.ego_x_m - row.scooter_x_m) <= 2.95]
        if not overlap or min(row.ego_y_m for row in overlap) <= SCOOTER_Y_M:
            raise ValueError("Left pass absent")
        returning = next(i for i in range(1, FRAMES) if rows[i].ego_y_m < rows[i - 1].ego_y_m - 1e-8)
        if suffix != "ordering_1" and returning <= overlap[-1].frame:
            raise ValueError("Return starts before longitudinal clearance")
        if suffix == "ordering_1" and returning >= overlap[-1].frame:
            raise ValueError("Early return does not occur while abreast")
        expected_gap = PASS_TARGETS_M[suffix]
        actual_gap = overlap[0].ego_y_m - SCOOTER_Y_M - EGO_HALF_WIDTH_M - SCOOTER_HALF_WIDTH_M
        if suffix != "ordering_1" and not math.isclose(expected_gap, actual_gap, abs_tol=1e-9):
            raise ValueError("Requested body-gap geometry differs")
    return {"case_suffixes": list(PASS_TARGETS_M), "frame_count": FRAMES,
            "rate_hz": HZ, "same_direction_lane_count_authored": 1,
            "native_map_readback_pending": True, "physical_pass_observed": False,
            "safe_pass_legally_determined": False}
