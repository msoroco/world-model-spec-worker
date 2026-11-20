"""CPU construction for the frozen C177008 change-lane maneuver.

The generated map and trajectory are engineering inputs. Native motion, lamp
pixels, district classification, and legal acceptance require separate review.
"""

import argparse
import hashlib
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


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_diagnostic(root, signal_start_m=SIGNAL_START_S_M, district_type="business"):
    """Write a source-shaped synthetic trace for software checks only."""
    if district_type not in ("business", "residential", "other"):
        raise ValueError("Unsupported district branch")
    if not 0 < signal_start_m < LATERAL_START_S_M:
        raise ValueError("Signal start must precede course onset")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "road.xodr").write_text(build_opendrive())
    document = root / "district-site-source.txt"
    document.write_text(f"Synthetic C177008 {district_type}-area assumption for CPU branch testing; no actual site or legal district review.\n")
    map_hash, document_hash = _hash(root / "road.xodr"), _hash(document)
    packet = {"district_type": district_type, "authored_map_sha256": map_hash,
              "source_document_sha256": document_hash, "independent_review": False,
              "source_scope": "synthetic_diagnostic"}
    (root / "district-site-packet.json").write_text(json.dumps(packet, indent=2) + "\n")
    context = {"cell_id": "C177008", "course": "change_lane", "road_id": ROAD_ID,
               "source_lane_id": -1, "target_lane_id": -2,
               "source_lane_lower_y_m": -LANE_WIDTH_M,
               "district_type": district_type, "district_source_sha256": document_hash,
               "authored_map_sha256": map_hash, "source_scope": "synthetic_diagnostic",
               "district_review_verified": False}
    (root / "route_context.json").write_text(json.dumps(context, indent=2) + "\n")
    paths = {name: (root / name).open("w") for name in
             ("drive_history.jsonl", "body_history.jsonl", "video_frames.jsonl")}
    native = root / "capture/native/frames.jsonl"
    native.parent.mkdir(parents=True, exist_ok=True)
    try:
        with native.open("w") as native_file:
            for i, sample in enumerate(plan()["samples"]):
                frame, time = 1000 + i, i / SAMPLE_HZ
                x, y = sample["x_m"], sample["y_m"]
                indicator = sample["station_m"] >= signal_start_m
                drive = {"frame": frame, "time_s": time, "ego_position_xy_m": [x, y],
                         "ego_heading_deg": sample["yaw_deg"], "ego_speed_mps": SPEED_MPS,
                         "native_road_id": ROAD_ID, "ego_light_mask": 64 if indicator else 0,
                         "right_indicator": indicator, "requested_indicator": indicator}
                body = {"frame": frame, "time_s": time, "road_id": ROAD_ID,
                        "body_vertices_m": [[x + dx, y + dy, 0.0] for dx in (-1.0, 1.0)
                                            for dy in (-0.7, 0.7)]}
                video = {"video_frame": i, "carla_frame": frame, "time_s": time,
                         "cameras": ["overview", "approach", "reference_corner", "driver_reference"]}
                native_row = {"frame": frame, "simulation_time": time,
                              "source_scope": "synthetic_diagnostic"}
                for name, row in (("drive_history.jsonl", drive), ("body_history.jsonl", body),
                                  ("video_frames.jsonl", video)):
                    paths[name].write(json.dumps(row) + "\n")
                native_file.write(json.dumps(native_row) + "\n")
    finally:
        for handle in paths.values():
            handle.close()
    return root


def analyze_source_trace(root):
    """Measure original-shaped rows; never infer legal or physical acceptance."""
    root = Path(root)
    required = ("road.xodr", "drive_history.jsonl", "body_history.jsonl",
                "video_frames.jsonl", "capture/native/frames.jsonl", "route_context.json",
                "district-site-packet.json", "district-site-source.txt")
    hashes = {}
    for name in required:
        path = root / name
        if not path.is_file():
            raise ValueError("Missing required source: " + name)
        hashes[name] = _hash(path)
    context = json.loads((root / "route_context.json").read_text())
    packet = json.loads((root / "district-site-packet.json").read_text())
    if (context.get("course") != "change_lane" or context.get("road_id") != ROAD_ID
            or context.get("source_lane_id") != -1 or context.get("target_lane_id") != -2):
        raise ValueError("Lane-change context differs from frozen cell construction")
    if (context.get("authored_map_sha256") != hashes["road.xodr"]
            or packet.get("authored_map_sha256") != hashes["road.xodr"]
            or context.get("district_source_sha256") != hashes["district-site-source.txt"]
            or packet.get("source_document_sha256") != hashes["district-site-source.txt"]
            or packet.get("district_type") != context.get("district_type")):
        raise ValueError("District/map source binding changed")
    district = context["district_type"]
    if district not in ("business", "residential", "other"):
        raise ValueError("Missing district branch")
    map_root = ET.fromstring((root / "road.xodr").read_text())
    driving_lanes = {int(lane.attrib["id"]): lane for lane in
                     map_root.findall("./road/lanes/laneSection/right/lane")
                     if lane.attrib.get("type") == "driving"}
    if -1 not in driving_lanes or -2 not in driving_lanes:
        raise ValueError("Two same-direction driving lanes absent")
    widths = [float(driving_lanes[lane_id].find("width").attrib["a"])
              for lane_id in (-1, -2)]
    if (any(abs(width - LANE_WIDTH_M) > 1e-9 for width in widths)
            or abs(float(context.get("source_lane_lower_y_m", 0)) + widths[0]) > 1e-9):
        raise ValueError("Source lane boundary differs from authored map")
    drive, body, video, native = (_rows(root / name) for name in
                                  ("drive_history.jsonl", "body_history.jsonl",
                                   "video_frames.jsonl", "capture/native/frames.jsonl"))
    if len(drive) < 3 or len({len(drive), len(body), len(video), len(native)}) != 1:
        raise ValueError("Source frame counts differ")
    previous = None
    path_m = 0.0
    signal_start_path = None
    first_course_change = None
    first_body_exit = None
    ever_off = False
    lower_y = float(context["source_lane_lower_y_m"])
    initial_y = drive[0]["ego_position_xy_m"][1]
    for i, (row, shape, frame, native_row) in enumerate(zip(drive, body, video, native)):
        fid, time = row.get("frame"), row.get("time_s")
        if (type(fid) is not int or type(time) not in (float, int)
                or (previous and (fid <= previous[0] or time <= previous[1]))):
            raise ValueError("Nonmonotone source time/frame")
        if (shape.get("frame") != fid or shape.get("time_s") != time
                or frame.get("carla_frame") != fid or frame.get("time_s") != time
                or frame.get("video_frame") != i or native_row.get("frame") != fid
                or native_row.get("simulation_time") != time):
            raise ValueError("Original source frame join changed")
        if native_row.get("source_scope") != context.get("source_scope"):
            raise ValueError("Native frame scope differs from route context")
        if (row.get("native_road_id") != ROAD_ID or shape.get("road_id") != ROAD_ID
                or set(frame.get("cameras", [])) !=
                {"overview", "approach", "reference_corner", "driver_reference"}):
            raise ValueError("Road identity or four-camera coverage changed")
        xy = row.get("ego_position_xy_m")
        vertices = shape.get("body_vertices_m")
        if (not isinstance(xy, list) or len(xy) != 2 or not isinstance(vertices, list)
                or len(vertices) != 4 or any(len(v) < 2 for v in vertices)):
            raise ValueError("Incomplete original ego body/path")
        if previous:
            delta = math.dist(xy, previous[2])
            elapsed = time - previous[1]
            speed = row.get("ego_speed_mps")
            if type(speed) not in (int, float) or delta > max(speed, previous[3]) * elapsed + 0.1:
                raise ValueError("Path jump exceeds source speed")
            path_m += delta
        else:
            if min(v[1] for v in vertices) < lower_y:
                raise ValueError("First body is not in source lane")
        indicator = row.get("right_indicator")
        mask = row.get("ego_light_mask")
        if type(indicator) is not bool or type(mask) is not int or indicator != bool(mask & 64):
            raise ValueError("Right indicator differs from original light mask")
        if not indicator:
            ever_off = True
            signal_start_path = None
        elif ever_off and (previous is None or not previous[4]):
            signal_start_path = path_m
        if first_course_change is None and abs(xy[1] - initial_y) > 1e-6:
            if signal_start_path is None or not indicator:
                raise ValueError("No fully observed continuous pre-change right signal")
            first_course_change = {"frame": fid, "time_s": time, "path_m": path_m,
                                   "continuous_right_signal_distance_m": path_m - signal_start_path}
        if first_body_exit is None and min(v[1] for v in vertices) < lower_y - 1e-6:
            first_body_exit = {"frame": fid, "time_s": time, "path_m": path_m}
        previous = (fid, time, xy, float(row["ego_speed_mps"]), indicator)
    if first_course_change is None or first_body_exit is None:
        raise ValueError("No observed course change and source-lane exit")
    if first_body_exit["frame"] <= first_course_change["frame"]:
        raise ValueError("Body exit does not follow course onset")
    required_m = (300 if district == "other" else 100) * 0.3048
    return {"format": "worker-lane-change-source-measurement", "sources": hashes,
            "source_scope": context.get("source_scope"), "district_type": district,
            "district_review_verified": context.get("district_review_verified") is True,
            "required_distance_m": required_m,
            "first_course_change": first_course_change, "first_body_exit": first_body_exit,
            "observed_continuous_distance_meets_boundary":
                first_course_change["continuous_right_signal_distance_m"] >= required_m,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--write-diagnostic", action="store_true")
    parser.add_argument("--analyze", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "road.xodr").write_text(build_opendrive())
    result = plan()
    (args.output / "course-plan.json").write_text(json.dumps(result, indent=2) + "\n")
    if args.write_diagnostic:
        write_diagnostic(args.output / "diagnostic")
    if args.analyze:
        print(json.dumps(analyze_source_trace(args.analyze), indent=2))
        return
    print(json.dumps({"course": result["course"], "samples": len(result["samples"]),
                      "first_signal_s_m": next(s["station_m"] for s in result["samples"] if s["requested_right_indicator"]),
                      "lateral_start_s_m": LATERAL_START_S_M,
                      "lead_m": LATERAL_START_S_M - SIGNAL_START_S_M,
                      "native_execution": "pending", "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    main()
