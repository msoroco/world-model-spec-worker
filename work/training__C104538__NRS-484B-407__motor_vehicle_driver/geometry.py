"""Work-owned C104538 curve/crest proposal. This is not a Native map survey."""
from __future__ import annotations

import hashlib
import math
import xml.etree.ElementTree as ET

ROAD_LENGTH_M = 400.0
TURN_STATION_M = 200.0
RADIUS_M = 500.0
CREST_HEIGHT_M = 3.2
LANE_WIDTH_M = 3.5
FT_M = 0.3048
OBSERVER_DISTANCES_FT = {"below_500_ft": 450, "at_500_ft": 500,
                         "above_500_ft": 550}
def obstruction_radius_for_limit(limit_ft: float) -> float:
    if not math.isfinite(limit_ft) or limit_ft <= 0 or limit_ft * FT_M >= ROAD_LENGTH_M / 2:
        raise ValueError("Invalid authored sight limit")
    # An inner obstruction is tangent to the center-reference ray at this
    # designed limit. Native object height and original pixels need a survey.
    return RADIUS_M * math.cos(limit_ft * FT_M / (2 * RADIUS_M))


def reference_limit_ft(obstruction_radius_m: float) -> float:
    if not 0 < obstruction_radius_m < RADIUS_M:
        raise ValueError("Invalid authored obstruction radius")
    return 2 * RADIUS_M * math.acos(obstruction_radius_m / RADIUS_M) / FT_M


def road_height(station_m: float) -> float:
    if not 0 <= station_m <= ROAD_LENGTH_M:
        raise ValueError("Road station outside authored crest")
    offset = station_m - TURN_STATION_M
    return CREST_HEIGHT_M * (1 - (offset / TURN_STATION_M) ** 2)


def center_xy(station_m: float) -> tuple[float, float]:
    if not 0 <= station_m <= ROAD_LENGTH_M:
        raise ValueError("Road station outside authored curve")
    angle = (station_m - TURN_STATION_M) / RADIUS_M
    return RADIUS_M * math.cos(angle), RADIUS_M * math.sin(angle)


def open_drive() -> str:
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4",
                  name="C104538-curve-crest-proposal", version="1",
                  date="2026-11-05", north="1000", south="-1000",
                  east="1000", west="-1000", vendor="full-train-worker")
    road = ET.SubElement(root, "road", id="1", name="crest_curve",
                         length=str(ROAD_LENGTH_M), junction="-1")
    ET.SubElement(road, "link")
    x0, y0 = center_xy(0)
    plan = ET.SubElement(road, "planView")
    segment = ET.SubElement(plan, "geometry", s="0", x=str(x0), y=str(y0),
                            hdg=str(math.pi / 2 - TURN_STATION_M / RADIUS_M),
                            length=str(ROAD_LENGTH_M))
    ET.SubElement(segment, "arc", curvature=str(1 / RADIUS_M))
    elevation = ET.SubElement(road, "elevationProfile")
    ET.SubElement(elevation, "elevation", s="0", a="0",
                  b=str(2 * CREST_HEIGHT_M / TURN_STATION_M),
                  c=str(-CREST_HEIGHT_M / TURN_STATION_M ** 2), d="0")
    lanes = ET.SubElement(road, "lanes")
    ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
    section = ET.SubElement(lanes, "laneSection", s="0")
    for group, ids in (("left", (1,)), ("center", (0,)), ("right", (-1,))):
        side = ET.SubElement(section, group)
        for ident in ids:
            lane = ET.SubElement(side, "lane", id=str(ident),
                                 type="none" if ident == 0 else "driving", level="false")
            if ident:
                ET.SubElement(lane, "width", sOffset="0", a=str(LANE_WIDTH_M),
                              b="0", c="0", d="0")
            ET.SubElement(lane, "roadMark", sOffset="0", type="solid",
                          color="yellow" if ident == 0 else "white", width="0.12")
    ET.SubElement(road, "objects")
    ET.SubElement(road, "signals")
    return ET.tostring(root, encoding="unicode")


def check() -> dict:
    parsed = ET.fromstring(open_drive())
    road = parsed.find("road")
    assert road is not None and road.attrib["length"] == str(ROAD_LENGTH_M)
    assert road.find("planView/geometry/arc") is not None
    assert road.find("elevationProfile/elevation") is not None
    assert math.isclose(road_height(TURN_STATION_M), CREST_HEIGHT_M)
    assert road_height(0) == road_height(ROAD_LENGTH_M) == 0
    assert all(TURN_STATION_M + direction * distance * FT_M >= 0 and
               TURN_STATION_M + direction * distance * FT_M <= ROAD_LENGTH_M
               for distance in OBSERVER_DISTANCES_FT.values()
               for direction in (-1, 1))
    assert all(math.isclose(reference_limit_ft(obstruction_radius_for_limit(distance)),
                            distance, abs_tol=1e-9)
               for distance in OBSERVER_DISTANCES_FT.values())
    xml = open_drive().encode()
    return {"passed": True, "road_xodr_sha256": hashlib.sha256(xml).hexdigest(),
            "curve_radius_m": RADIUS_M, "crest_height_m": CREST_HEIGHT_M,
            "turn_station_m": TURN_STATION_M,
            "inner_obstruction_radius_at_500_ft_m": obstruction_radius_for_limit(500),
            "native_loaded": False, "physical_visibility_measured": False}
