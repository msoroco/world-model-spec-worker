"""CPU construction for the frozen C177008 change-lane maneuver.

The generated map and trajectory are engineering inputs. Native motion, lamp
pixels, district classification, and legal acceptance require separate review.
"""

import argparse
import json
import math
from pathlib import Path
from xml.etree import ElementTree as ET


ROAD_ID = 177008
LANE_WIDTH_M = 3.6
ROAD_LENGTH_M = 160.0
SAMPLE_HZ = 20
SPEED_MPS = 5.0
SIGNAL_START_S_M = 82.0
LATERAL_START_S_M = 115.0
LATERAL_END_S_M = 135.0


def build_opendrive():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4", name="C177008 two-lane course change",
                  version="1", north="8", south="-10", east="40", west="-120",
                  vendor="scenario-worker-demo CPU construction")
    road = ET.SubElement(root, "road", name="two marked same-direction lanes",
                         length=str(ROAD_LENGTH_M), id=str(ROAD_ID), junction="-1", rule="RHT")
    geometry = ET.SubElement(ET.SubElement(road, "planView"), "geometry", s="0", x="-120", y="0",
                             hdg="0", length=str(ROAD_LENGTH_M))
    ET.SubElement(geometry, "line")
    ET.SubElement(road, "elevationProfile")
    ET.SubElement(road, "lateralProfile")
    lanes = ET.SubElement(road, "lanes")
    ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
    section = ET.SubElement(lanes, "laneSection", s="0")
    ET.SubElement(section, "left")
    ET.SubElement(ET.SubElement(section, "center"), "lane", id="0", type="none", level="false")
    right = ET.SubElement(section, "right")
    for lane_id in (-1, -2):
        lane = ET.SubElement(right, "lane", id=str(lane_id), type="driving", level="false")
        ET.SubElement(lane, "width", sOffset="0", a=str(LANE_WIDTH_M), b="0", c="0", d="0")
        ET.SubElement(lane, "roadMark", sOffset="0", type="broken" if lane_id == -1 else "solid",
                      weight="standard", color="standard", width="0.12")
    return ET.tostring(root, encoding="unicode") + "\n"


def lateral_fraction(station_m):
    if station_m <= LATERAL_START_S_M:
        return 0.0
    if station_m >= LATERAL_END_S_M:
        return 1.0
    u = (station_m - LATERAL_START_S_M) / (LATERAL_END_S_M - LATERAL_START_S_M)
    return u * u * (3.0 - 2.0 * u)


def course_sample(station_m):
    """Return a rightward course-change target and right-signal request."""
    if not 0.0 <= station_m <= ROAD_LENGTH_M:
        raise ValueError("station outside authored road")
    fraction = lateral_fraction(station_m)
    if LATERAL_START_S_M < station_m < LATERAL_END_S_M:
        u = (station_m - LATERAL_START_S_M) / (LATERAL_END_S_M - LATERAL_START_S_M)
        dyds = -LANE_WIDTH_M * 6.0 * u * (1.0 - u) / (LATERAL_END_S_M - LATERAL_START_S_M)
    else:
        dyds = 0.0
    return {
        "road_id": ROAD_ID,
        "station_m": station_m,
        "x_m": station_m - 120.0,
        "y_m": -LANE_WIDTH_M * (0.5 + fraction),
        "yaw_deg": math.degrees(math.atan(dyds)),
        "requested_right_indicator": station_m >= SIGNAL_START_S_M,
        "source_lane_id": -1,
        "target_lane_id": -2,
        "target_speed_mps": SPEED_MPS,
    }


def plan():
    count = int(ROAD_LENGTH_M * SAMPLE_HZ / SPEED_MPS)
    samples = [course_sample(i * SPEED_MPS / SAMPLE_HZ) for i in range(count + 1)]
    validate_plan(samples)
    return {
        "format": "worker-native-lane-change-course-plan",
        "cell_id": "C177008", "road_id": ROAD_ID,
        "course": "change_lane", "direction": "right",
        "cameras": ["overview", "approach", "reference_corner", "driver_reference"],
        "other_vehicle": {"road_id": ROAD_ID, "lane_id": -2, "station_m": 150.0},
        "physical_acceptance_claimed": False, "legal_acceptance_claimed": False,
        "samples": samples,
    }


def validate_plan(samples):
    if not samples or samples[0]["requested_right_indicator"]:
        raise ValueError("no observed pre-signal course")
    if any(a["station_m"] >= b["station_m"] for a, b in zip(samples, samples[1:])):
        raise ValueError("non-increasing road station")
    first_signal = next(s for s in samples if s["requested_right_indicator"])
    first_motion = next(s for s in samples if s["y_m"] < -LANE_WIDTH_M / 2 - 1e-9)
    if first_signal["station_m"] >= first_motion["station_m"]:
        raise ValueError("signal does not precede lateral course change")
    if first_motion["station_m"] - first_signal["station_m"] < 30.48:
        raise ValueError("authored business-district lead is below 100 feet")
    if abs(samples[-1]["y_m"] + 1.5 * LANE_WIDTH_M) > 1e-9:
        raise ValueError("course does not reach target lane center")
    if any(s["road_id"] != ROAD_ID for s in samples):
        raise ValueError("lane change left the authored road")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "road.xodr").write_text(build_opendrive())
    result = plan()
    (args.output / "course-plan.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"course": result["course"], "samples": len(result["samples"]),
                      "first_signal_s_m": next(s["station_m"] for s in result["samples"] if s["requested_right_indicator"]),
                      "lateral_start_s_m": LATERAL_START_S_M,
                      "lead_m": LATERAL_START_S_M - SIGNAL_START_S_M,
                      "native_execution": "pending", "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    main()
