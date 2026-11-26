"""Pure geometry and control plan for the four same-direction pass cases.

Native readback and source review must confirm the plan before a recording can
support an availability or safety assertion. Importing this module needs no CARLA.
"""

from dataclasses import dataclass
import math
import xml.etree.ElementTree as ET


RATE_HZ = 20
FRAMES = 600
RIGHT_LANE = -2
IMMEDIATE_LEFT_LANE = -1
LANE_WIDTH_M = 3.5
RIGHT_CENTER_Y_M = -5.25
LEFT_CENTER_Y_M = -1.75
CASES = {
    "witness_1": (True, False),
    "witness_2": (False, False),
    "exception_1_1": (False, False),
    "exception_1_2": (False, True),
    "exception_unsafe_available": (False, True),
}


@dataclass(frozen=True)
class Target:
    frame: int
    ego_x_m: float
    ego_y_m: float
    cyclist_x_m: float
    cyclist_y_m: float
    left_blocker_x_m: float | None
    left_blocker_y_m: float | None


def open_drive():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4", name="C247014-cycle-pass",
                  version="1", north="30", south="-30", east="300", west="-100",
                  vendor="full-train-worker")
    road = ET.SubElement(root, "road", id="1", name="two-same-direction-lanes",
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
    ET.SubElement(section, "left")
    center = ET.SubElement(section, "center")
    ET.SubElement(center, "lane", id="0", type="none", level="false")
    right = ET.SubElement(section, "right")
    for lane_id in (IMMEDIATE_LEFT_LANE, RIGHT_LANE):
        lane = ET.SubElement(right, "lane", id=str(lane_id), type="driving", level="false")
        ET.SubElement(lane, "width", sOffset="0", a=str(LANE_WIDTH_M), b="0", c="0", d="0")
        ET.SubElement(lane, "roadMark", sOffset="0", type="broken" if lane_id == -1 else "solid",
                      color="white", width="0.12")
    ET.SubElement(road, "objects")
    ET.SubElement(road, "signals")
    return ET.tostring(root, encoding="unicode")


def target(case_suffix, frame):
    if case_suffix not in CASES:
        raise ValueError("Unknown exact case")
    if not isinstance(frame, int) or not 0 <= frame < FRAMES:
        raise ValueError("Frame outside 30-second plan")
    move_left, block_left = CASES[case_suffix]
    t = frame / RATE_HZ
    ego_x = -40 + 3 * t
    cycle_x = -15 + 1.5 * t
    # The lane-change target is complete before the expected abreast interval.
    phase = max(0.0, min(1.0, (frame - 180) / 80)) if move_left else 0.0
    smooth = phase * phase * (3 - 2 * phase)
    ego_y = RIGHT_CENTER_Y_M + smooth * (LEFT_CENTER_Y_M - RIGHT_CENTER_Y_M)
    blocker_x = (ego_x - 35 + 3 * t) if case_suffix == "exception_unsafe_available" else (ego_x + 2 if block_left else None)
    return Target(frame, ego_x, ego_y, cycle_x, RIGHT_CENTER_Y_M - 0.7,
                  blocker_x, LEFT_CENTER_Y_M if block_left else None)


def check():
    road = ET.fromstring(open_drive()).find("road")
    lanes = road.findall("lanes/laneSection/right/lane")
    if [int(l.attrib["id"]) for l in lanes] != [-1, -2]:
        raise ValueError("Immediate-left lane geometry changed")
    if [float(l.find("width").attrib["a"]) for l in lanes] != [3.5, 3.5]:
        raise ValueError("Lane widths changed")
    if not math.isclose(target("witness_1", 260).ego_y_m, LEFT_CENTER_Y_M):
        raise ValueError("Left move does not complete before pass")
    pass_frames = [i for i in range(FRAMES)
                   if abs(target("witness_1", i).ego_x_m - target("witness_1", i).cyclist_x_m) <= 4]
    if not pass_frames or pass_frames[0] <= 260 or pass_frames[-1] >= FRAMES:
        raise ValueError("Pass window does not follow lane change")
    for suffix in CASES:
        if target(suffix, 0).cyclist_x_m != -15:
            raise ValueError("Cycle trajectory differs across cases")
    return {"passed": True, "frames": FRAMES, "rate_hz": RATE_HZ,
            "lane_ids": [RIGHT_LANE, IMMEDIATE_LEFT_LANE],
            "pass_first_frame": pass_frames[0], "pass_last_frame": pass_frames[-1],
            "case_suffixes": list(CASES), "original_native_observed": False,
            "availability_or_safety_judged": False}
