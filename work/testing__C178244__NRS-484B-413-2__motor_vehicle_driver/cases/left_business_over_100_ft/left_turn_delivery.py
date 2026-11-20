"""Measure continuous left-indicator path length before a course change.

The business/residential 100-foot and other-area 300-foot boundaries are exact.
The module reports a conservative sampled distance from the first observed On
frame to the authored onset; it never treats weather as an excuse.
"""

import hashlib
import json
import math
import argparse
import subprocess
import os
import shutil
from pathlib import Path
from contextlib import contextmanager, ExitStack
from queue import Empty, Queue
from xml.etree import ElementTree as ET


FEET_TO_M = 0.3048
REQUIRED = ("drive_history.jsonl", "video_frames.jsonl", "route_context.json")
CASE = "testing__C178244__NRS-484B-413-2__motor_vehicle_driver__left_business_over_100_ft"
CAMERAS = {"overview": (1920, 1080), "approach": (1280, 720),
           "reference_corner": (1280, 720), "driver_reference": (1280, 720)}
MAP_SHA256 = "133932810f75ac785039068a94ceab89e8d8aa2a1fa6adf83bdf200f2bd48ced"
LEFT_BLINKER_MASK = 32


def validate_capture_config(config):
    if (config.get("selected_case_id") != CASE or config.get("law_id") != "NRS-484B-413-2"
            or config.get("cell_id") != "C178244" or config.get("rate_hz") != 20
            or config.get("duration_s") != 40 or config.get("course") != "left_turn"):
        raise ValueError("Exact C178244 left-turn capture identity required")
    if config.get("map_sha256") != MAP_SHA256:
        raise ValueError("Returned left-turn map hash required")
    rows = config.get("cameras")
    if not isinstance(rows, list) or [r.get("name") for r in rows] != list(CAMERAS):
        raise ValueError("Four named source cameras required")
    if any((r.get("width"), r.get("height")) != CAMERAS[r["name"]]
           or type(r.get("fov_deg")) not in (int, float)
           or not 30 <= r["fov_deg"] <= 120 for r in rows):
        raise ValueError("Pinned source camera dimensions/FOV required")
    if config.get("required_atoms") != ["sig.turn_indicator"]:
        raise ValueError("Selected indicator observation required")
    if abs(_number(config.get("indicator_start_m")) - 32.0) > 1e-9:
        raise ValueError("One sampled frame of left-signal lead required")
    if config.get("physical_completion", {}).get("destination_road") != 178247:
        raise ValueError("Native northbound departure road required")
    return config


def capture_config():
    return validate_capture_config({"selected_case_id": CASE, "law_id": "NRS-484B-413-2",
        "cell_id": "C178244", "actor": "motor_vehicle_driver", "course": "left_turn",
        "rate_hz": 20, "duration_s": 40, "requested_speed_mps": 5.0,
        "indicator_start_m": 32.0, "map_sha256": MAP_SHA256,
        "physical_completion": {"criterion": "road_transition", "motion_source": "body_history.jsonl",
                                "body_key": "body_vertices_m", "road_key": "road_id",
                                "destination_road": 178247},
        "required_atoms": ["sig.turn_indicator"],
        "cameras": [{"name": name, "width": size[0], "height": size[1],
                     "fov_deg": 90} for name, size in CAMERAS.items()]})


def retain_district_source(packet_path, output, native_map_name):
    """Hash and retain an exact-map, source-reviewed site packet and document.

    The packet is an operator-supplied source assertion. Pixel and legal review
    remain separate; an absent packet leaves the recorded district unresolved.
    """
    if not packet_path:
        return {"district_type": None, "district_source": None,
                "district_review_verified": False}
    path = Path(packet_path).resolve()
    packet = json.loads(path.read_text())
    if (packet.get("authored_map_sha256") != MAP_SHA256
            or packet.get("native_map_name") != native_map_name
            or packet.get("district_type") not in ("business", "residential", "other")
            or packet.get("independent_review") is not True):
        raise ValueError("District source packet lacks exact-map independent review")
    document = Path(packet.get("source_document", "")).resolve()
    if not document.is_file() or not packet.get("source_document_sha256"):
        raise ValueError("District source document missing")
    document_hash = hashlib.sha256(document.read_bytes()).hexdigest()
    if document_hash != packet["source_document_sha256"]:
        raise ValueError("District source document hash differs")
    output = Path(output)
    retained_packet, retained_document = output/"district-site-packet.json", output/"district-site-source.txt"
    if retained_packet.exists() or retained_document.exists():
        raise ValueError("Fresh district source paths required")
    shutil.copyfile(path, retained_packet)
    shutil.copyfile(document, retained_document)
    if hashlib.sha256(retained_document.read_bytes()).hexdigest() != document_hash:
        raise ValueError("Retained district document differs")
    return {"district_type": packet["district_type"],
            "district_source": "district-site-packet.json",
            "district_source_document": "district-site-source.txt",
            "district_source_sha256": document_hash,
            "district_review_verified": True}


def _waypoint_xy(waypoint):
    location = waypoint.transform.location
    return (_number(location.x), _number(location.y))


def verify_native_left_turn(approach, departure, *, minimum_approach_m=300 * FEET_TO_M,
                             max_step_m=5.0):
    """Validate the Native lane chain before using it for any signaling case.

    District classification is deliberately outside geometry: it needs a
    separately reviewed source, recorded in route_context.json.
    """
    if len(approach) < 3 or len(departure) < 2:
        raise ValueError("Incomplete Native left-turn route")
    incoming_key = (approach[0].road_id, approach[0].lane_id)
    outgoing_key = (departure[0].road_id, departure[0].lane_id)
    if any((wp.road_id, wp.lane_id) != incoming_key for wp in approach):
        raise ValueError("Approach lane or road changes before turn")
    if any((wp.road_id, wp.lane_id) != outgoing_key for wp in departure):
        raise ValueError("Departure lane or road changes after turn")
    if incoming_key[0] == outgoing_key[0]:
        raise ValueError("Left turn needs a distinct outgoing road")
    incoming_xy = [_waypoint_xy(wp) for wp in approach]
    outgoing_xy = [_waypoint_xy(wp) for wp in departure]
    steps = [math.dist(a, b) for a, b in zip(incoming_xy, incoming_xy[1:])]
    if any(not 0 < step <= max_step_m for step in steps):
        raise ValueError("Discontinuous Native approach")
    length = sum(steps)
    if length < minimum_approach_m:
        raise ValueError("Native approach shorter than 300-foot observation span")
    if math.dist(incoming_xy[-1], outgoing_xy[0]) > max_step_m:
        raise ValueError("Native turn connection is discontinuous")
    if any(not 0 < math.dist(a, b) <= max_step_m
           for a, b in zip(outgoing_xy, outgoing_xy[1:])):
        raise ValueError("Discontinuous Native departure")
    first = (incoming_xy[-1][0] - incoming_xy[-2][0],
             incoming_xy[-1][1] - incoming_xy[-2][1])
    last = (outgoing_xy[-1][0] - outgoing_xy[0][0],
            outgoing_xy[-1][1] - outgoing_xy[0][1])
    denominator = math.hypot(*first) * math.hypot(*last)
    if denominator == 0:
        raise ValueError("Zero Native turn vector")
    angle = math.degrees(math.atan2(first[0] * last[1] - first[1] * last[0],
                                    first[0] * last[0] + first[1] * last[1]))
    if not 30 < angle < 150:
        raise ValueError("Native route is not a left turn")
    return {"approach_road_id": incoming_key[0], "approach_lane_id": incoming_key[1],
            "outgoing_road_id": outgoing_key[0], "outgoing_lane_id": outgoing_key[1],
            "direct_approach_m": length, "turn_angle_deg": angle,
            "waypoints": list(approach) + list(departure)}


@contextmanager
def spawn_native_left_turn(world, blueprint, approach, departure):
    route = verify_native_left_turn(approach, departure)
    vehicle = world.try_spawn_actor(blueprint, approach[0].transform)
    if vehicle is None:
        raise ValueError("Native left-turn vehicle spawn failed")
    try:
        observed = world.get_map().get_waypoint(vehicle.get_location(), project_to_road=False)
        if observed is None or (observed.road_id, observed.lane_id) != (
                route["approach_road_id"], route["approach_lane_id"]):
            raise ValueError("Spawned vehicle outside Native approach lane")
        yield {"vehicle": vehicle, "route": route}
    finally:
        vehicle.destroy()


def set_native_left_blinker(vehicle, light_state_type, enabled):
    flag = light_state_type.LeftBlinker
    prior = vehicle.get_light_state()
    requested = prior | flag if enabled else prior & ~flag
    vehicle.set_light_state(requested)
    readback = vehicle.get_light_state()
    if bool(readback & flag) != bool(enabled):
        raise ValueError("Native left-indicator readback disagrees with request")
    if (readback & ~flag) != (prior & ~flag):
        raise ValueError("Native light actuation changed unrelated lamps")
    return {"requested_left_indicator": bool(enabled),
            "readback_left_indicator": bool(readback & flag)}


def indicator_request_at_remaining_distance(remaining_m, *, start_m,
                                            interruption_m=None):
    """Return the authored request for an approach station, before actuation.

    `remaining_m` must come from the selected route's cumulative lane distance.
    An interruption interval is a closed pair of remaining distances; it is a
    deliberate case variable and never inferred from the desired legal label.
    """
    remaining = _number(remaining_m)
    start = _number(start_m)
    if remaining < 0 or start <= 0:
        raise ValueError("Invalid route-distance indicator schedule")
    if interruption_m is not None:
        if not isinstance(interruption_m, (list, tuple)) or len(interruption_m) != 2:
            raise ValueError("Invalid indicator interruption interval")
        low, high = map(_number, interruption_m)
        if not 0 <= low < high < start:
            raise ValueError("Indicator interruption must lie inside the active approach")
        if low <= remaining <= high:
            return False
    return remaining <= start


def select_native_route(native_map, *, step_m=2.0):
    """Read back the authored approach and connector as real Native waypoints.

    The connector is the distinct outgoing road. Legal district status is not
    inferred from the synthetic road name or from this route readback.
    """
    step = _number(step_m)
    if not 0 < step <= 5:
        raise ValueError("Native route sampling must be within five metres")
    def sample(road, length):
        stations = [min(length, i * step) for i in range(math.ceil(length / step) + 1)]
        if stations[-1] != length:
            stations.append(length)
        points = []
        for station in stations:
            point = native_map.get_waypoint_xodr(road, -1, station)
            if point is None:
                raise ValueError("Authored Native road/lane station missing")
            points.append(point)
        return points
    approach = sample(178244, 120.0)
    connector = sample(178246, 5 * math.pi)
    return verify_native_left_turn(approach, connector)


def native_route_control(vehicle, route, *, target_speed_mps=5.0,
                         lookahead_m=5.0):
    """Make one bounded control request from actual actor pose and route points.

    The caller applies this request before the next Native tick and separately
    records its actual post-tick pose, speed and light readback.
    """
    speed_target = _number(target_speed_mps)
    lookahead = _number(lookahead_m)
    if not 0 < speed_target <= 15 or not 1 <= lookahead <= 15:
        raise ValueError("Invalid left-turn controller tuning")
    transform = vehicle.get_transform()
    x, y = _number(transform.location.x), _number(transform.location.y)
    heading = _number(transform.rotation.yaw)
    points = route["waypoints"]
    if len(points) < 4:
        raise ValueError("Native controller has no sampled route")
    positions = [_waypoint_xy(point) for point in points]
    nearest = min(range(len(positions)), key=lambda i: math.dist((x, y), positions[i]))
    cumulative = 0.0
    target_index = nearest
    for i in range(nearest, len(positions) - 1):
        cumulative += math.dist(positions[i], positions[i + 1])
        target_index = i + 1
        if cumulative >= lookahead:
            break
    tx, ty = positions[target_index]
    bearing = math.degrees(math.atan2(ty - y, tx - x))
    yaw_error = _angle_delta(bearing, heading)
    steer = max(-0.75, min(0.75, yaw_error / 35.0))
    velocity = vehicle.get_velocity()
    speed = math.sqrt(sum(_number(getattr(velocity, axis)) ** 2 for axis in ("x", "y", "z")))
    throttle = max(0.0, min(0.45, 0.18 * (speed_target - speed)))
    brake = max(0.0, min(1.0, 0.35 * (speed - speed_target)))
    if nearest >= len(points) - 2:
        throttle, brake, steer = 0.0, 1.0, 0.0
    # Approach stations are sampled every two metres; this is a controller
    # request, while the saved distance proof uses original post-tick motion.
    remaining = max(0.0, 120.0 - _number(getattr(points[nearest], "s"))) if nearest < len(points) else 0.0
    return {"throttle": throttle, "brake": brake, "steer": steer,
            "nearest_route_index": nearest, "target_route_index": target_index,
            "remaining_approach_m": remaining, "speed_mps": speed,
            "heading_error_deg": yaw_error}


def build_left_turn_opendrive():
    """Author a small connected left-turn road with a 120 m direct approach.

    This is synthetic route geometry. It supplies no evidence that any parcel is
    legally a business or residential district, nor that CARLA realizes the
    intended lane links. Both require separate source/Native review.
    """
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4",
                  name="C178244 synthetic left-turn approach", version="1",
                  north="55", south="-10", east="20", west="-125",
                  vendor="scenario-worker-demo CPU construction")
    curve_length = 5 * math.pi
    specs = ((178244, "direct approach", 120, -120, 0, 0, -1,
              None, ("junction", 178245, None)),
             (178246, "left-turn connector", curve_length, 0, 0, 0, 178245,
              ("road", 178244, "end"), ("road", 178247, "start")),
             (178247, "northbound departure", 40, 10, 10, math.pi/2, -1,
              ("junction", 178245, None), None))
    for road_id, name, length, x, y, heading, junction, predecessor, successor in specs:
        road = ET.SubElement(root, "road", name=name, length=str(length),
                             id=str(road_id), junction=str(junction), rule="RHT")
        link = ET.SubElement(road, "link")
        for tag, target in (("predecessor", predecessor), ("successor", successor)):
            if target:
                attrs = {"elementType":target[0], "elementId":str(target[1])}
                if target[2]:
                    attrs["contactPoint"] = target[2]
                ET.SubElement(link, tag, attrs)
        plan = ET.SubElement(road, "planView")
        geometry = ET.SubElement(plan, "geometry", s="0", x=str(x), y=str(y),
                                 hdg=str(heading), length=str(length))
        if road_id == 178246:
            ET.SubElement(geometry, "arc", curvature="0.1")
        else:
            ET.SubElement(geometry, "line")
        elevation = ET.SubElement(road, "elevationProfile")
        ET.SubElement(elevation, "elevation", s="0", a="0", b="0", c="0", d="0")
        ET.SubElement(road, "lateralProfile")
        lanes = ET.SubElement(road, "lanes")
        ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
        section = ET.SubElement(lanes, "laneSection", s="0")
        ET.SubElement(section, "left")
        center = ET.SubElement(section, "center")
        ET.SubElement(center, "lane", id="0", type="none", level="false")
        right = ET.SubElement(section, "right")
        lane = ET.SubElement(right, "lane", id="-1", type="driving", level="false")
        lane_link = ET.SubElement(lane, "link")
        if predecessor:
            ET.SubElement(lane_link, "predecessor", id="-1")
        if successor:
            ET.SubElement(lane_link, "successor", id="-1")
        ET.SubElement(lane, "width", sOffset="0", a="3.6", b="0", c="0", d="0")
    junction = ET.SubElement(root, "junction", name="C178244 left turn", id="178245")
    connection = ET.SubElement(junction, "connection", id="0", incomingRoad="178244",
                                connectingRoad="178246", contactPoint="start")
    ET.SubElement(connection, "laneLink", {"from":"-1", "to":"-1"})
    return ET.tostring(root, encoding="unicode") + "\n"


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Missing finite source measurement")
    return float(value)


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _angle_delta(degrees, reference):
    return (degrees - reference + 180.0) % 360.0 - 180.0


def analyze(root: Path) -> dict:
    root = Path(root)
    hashes = {}
    for name in REQUIRED:
        path = root / name
        if not path.is_file():
            raise ValueError("Missing required source: " + name)
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    context = json.loads((root / "route_context.json").read_text())
    for key in ("native_map_id", "approach_road_id", "approach_lane_id",
                "outgoing_road_id", "outgoing_lane_id", "native_route_source",
                "district_source", "turn_onset_frame"):
        if context.get(key) is None:
            raise ValueError("Missing sourced route context: " + key)
    district = context.get("district_type")
    if district not in ("business", "residential", "other"):
        raise ValueError("District class not sourced")
    if (context.get("district_source") != "district-site-packet.json"
            or context.get("district_source_document") != "district-site-source.txt"
            or context.get("district_review_verified") is not True):
        raise ValueError("District source packet not retained and reviewed")
    packet_path, document_path = root/"district-site-packet.json", root/"district-site-source.txt"
    if not packet_path.is_file() or not document_path.is_file():
        raise ValueError("Missing required source: district site packet/document")
    packet = json.loads(packet_path.read_text())
    document_hash = hashlib.sha256(document_path.read_bytes()).hexdigest()
    if (packet.get("district_type") != district
            or packet.get("native_map_name") != context["native_map_id"]
            or packet.get("authored_map_sha256") != MAP_SHA256
            or packet.get("source_document_sha256") != document_hash
            or context.get("district_source_sha256") != document_hash
            or packet.get("independent_review") is not True):
        raise ValueError("Saved district source does not bind the Native route")
    hashes["district-site-packet.json"] = hashlib.sha256(packet_path.read_bytes()).hexdigest()
    hashes["district-site-source.txt"] = document_hash
    threshold = (100 if district in ("business", "residential") else 300) * FEET_TO_M
    rows, frames = _rows(root / "drive_history.jsonl"), _rows(root / "video_frames.jsonl")
    if len(rows) < 3 or len(rows) != len(frames):
        raise ValueError("Incomplete drive/frame history")
    prior = (-1, -math.inf)
    path = 0.0
    previous_xy = None
    signal_start_path = None
    onset = None
    speeds = []
    seen_off_before_on = False
    prior_indicator = None
    prior_speed = None
    initial_heading = None
    measured_onset_frame = None
    for i, (row, frame) in enumerate(zip(rows, frames)):
        fid, time = row.get("frame"), _number(row.get("time_s"))
        if type(fid) is not int or fid <= prior[0] or time <= prior[1]:
            raise ValueError("Nonmonotone original drive history")
        prior_time = prior[1]
        prior = (fid, time)
        if frame.get("video_frame") != i or frame.get("carla_frame") != fid or frame.get("time_s") != time:
            raise ValueError("Original video frame join failed")
        xy = row.get("ego_position_xy_m")
        if not isinstance(xy, list) or len(xy) != 2:
            raise ValueError("Missing ego path point")
        xy = (_number(xy[0]), _number(xy[1]))
        speed = _number(row.get("ego_speed_mps"))
        if speed < 0:
            raise ValueError("Negative measured speed")
        if previous_xy is not None:
            segment_m = math.dist(xy, previous_xy)
            elapsed_s = time - prior_time
            plausible_m = max(speed, prior_speed) * elapsed_s
            if segment_m > plausible_m + max(0.1, 0.1 * plausible_m):
                raise ValueError("Measured path jump exceeds source speed")
            path += segment_m
        heading = _number(row.get("ego_heading_deg"))
        if previous_xy is not None and math.dist(xy, previous_xy) > 0.01:
            measured_bearing = math.degrees(math.atan2(xy[1] - previous_xy[1],
                                                        xy[0] - previous_xy[0]))
            if abs(_angle_delta(heading, measured_bearing)) > 5.0:
                raise ValueError("Source heading disagrees with measured path bearing")
        previous_xy = xy
        prior_speed = speed
        if initial_heading is None:
            initial_heading = heading
        heading_delta = _angle_delta(heading, initial_heading)
        if measured_onset_frame is None and abs(heading_delta) >= 10.0:
            measured_onset_frame = fid
            if heading_delta <= 0:
                raise ValueError("Measured course change is not a left turn")
        elif measured_onset_frame is None and abs(heading_delta) > 3.0:
            raise ValueError("Unstable pre-turn course heading")
        indicator = row.get("left_indicator")
        if type(indicator) is not bool:
            raise ValueError("Missing measured left indicator")
        mask = row.get("ego_light_mask")
        if type(mask) is not int or mask < 0 or bool(mask & LEFT_BLINKER_MASK) != indicator:
            raise ValueError("Native left-indicator flag disagrees with original light mask")
        if indicator and prior_indicator is False:
            seen_off_before_on = True
            signal_start_path = path
        if not indicator:
            signal_start_path = None
        prior_indicator = indicator
        speeds.append(speed)
        if fid == context["turn_onset_frame"]:
            if measured_onset_frame != fid:
                raise ValueError("Authored turn onset disagrees with measured heading change")
            if not seen_off_before_on or signal_start_path is None or not indicator:
                raise ValueError("No fully observed continuous pre-turn left signal")
            onset = {"frame": fid, "time_s": time, "path_length_m": path,
                     "continuous_left_signal_distance_m": path - signal_start_path,
                     "ego_position_xy_m": list(xy), "heading_delta_deg": heading_delta,
                     "onset_method": "first_source_heading_change_at_least_10deg"}
            break
    if onset is None:
        raise ValueError("Turn onset absent from original trace")
    return {"format": "worker-continuous-left-turn-signal-distance", "sources": hashes,
            "district_type": district, "required_distance_m": threshold,
            "turn_onset": onset, "observed_continuous_distance_meets_boundary":
                onset["continuous_left_signal_distance_m"] >= threshold - 1e-9,
            "approach_speed_samples_mps": speeds,
            "route_turn_direction_judgment": "unresolved until Native route geometry is reviewed",
            "weather_exception": "none in NRS 484B.413(2)"}


def measure_continuous_left_signal_distance(report):
    """Measure the uninterrupted sampled path before the left-turn onset."""
    return report["turn_onset"]["continuous_left_signal_distance_m"]


def source_district_boundary(report):
    """Return the boundary selected by the retained district source."""
    return report["required_distance_m"]


def measure_left_turn_onset(report):
    """Return the original frame and heading change used for the course onset."""
    onset = report["turn_onset"]
    return {"original_frame": onset["frame"],
            "heading_delta_deg": onset["heading_delta_deg"],
            "method": onset["onset_method"]}


def _read_camera(queue, frame):
    for _ in range(8):
        try:
            image = queue.get(timeout=10)
        except Empty as error:
            raise ValueError("Source camera frame missing") from error
        if image.frame == frame:
            return bytes(image.raw_data)
        if image.frame > frame:
            raise ValueError("Source camera skipped Native frame")
    raise ValueError("Source camera frame join failed")


@contextmanager
def _source_cameras(world, ego, carla, plan):
    loc = ego.get_transform().location
    def at(x, y, z, yaw, pitch):
        return carla.Transform(carla.Location(x=x, y=y, z=z),
                               carla.Rotation(yaw=yaw, pitch=pitch))
    transforms = {"overview": at(-8, -10, loc.z+42, 0, -80),
                  "approach": at(-70, -15, loc.z+8, 0, -15),
                  "reference_corner": at(12, -8, loc.z+12, 150, -30),
                  "driver_reference": at(1.0, 0, 1.65, 0, -6)}
    sensors = {}
    try:
        for row in plan:
            name = row["name"]
            blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
            for key, value in (("image_size_x", row["width"]),
                               ("image_size_y", row["height"]),
                               ("fov", row["fov_deg"]), ("sensor_tick", 0.05)):
                blueprint.set_attribute(key, str(value))
            kwargs = {"attach_to": ego} if name == "driver_reference" else {}
            sensor = world.spawn_actor(blueprint, transforms[name], **kwargs)
            if sensor is None:
                raise ValueError("Native source camera spawn failed: " + name)
            sensors[name] = sensor
        yield sensors
    finally:
        for sensor in reversed(list(sensors.values())):
            sensor.stop()
            sensor.destroy()


@contextmanager
def _ffv1(path, size):
    width, height = size
    if Path(path).exists():
        raise ValueError("Fresh source-video path required")
    process = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-n",
        "-f", "rawvideo", "-pixel_format", "bgra", "-video_size", f"{width}x{height}",
        "-framerate", "20", "-i", "pipe:0", "-an", "-c:v", "ffv1", "-level", "3",
        "-pix_fmt", "bgr0", str(path)], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    count = 0
    class Writer:
        def write(self, data):
            nonlocal count
            if len(data) != width * height * 4 or process.poll() is not None:
                raise ValueError("Native source-camera BGRA size/encoder mismatch")
            process.stdin.write(data)
            count += 1
    try:
        yield Writer()
    finally:
        process.stdin.close()
        code = process.wait(timeout=60)
        stderr = process.stderr.read().decode(errors="replace")
        process.stderr.close()
        if code or not count:
            raise ValueError("Native FFV1 encoder failed: " + stderr[-500:])


def capture_native(args, config):
    """Capture original Native motion/pixels on the returned synthetic map.

    The resulting route context remains district-unverified unless an exact-map
    independent legal-site packet is supplied. No legal status is fabricated.
    """
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot as save_world, restore

    output = Path(args.output_dir).resolve()
    if not output.is_dir() or not (output / "construction.json").is_file():
        raise ValueError("Use runtime.py capture to materialize exact construction")
    map_text = build_left_turn_opendrive()
    if hashlib.sha256(map_text.encode()).hexdigest() != config["map_sha256"]:
        raise ValueError("Authored map differs from returned map")
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    saved = save_world(client)
    vehicle = None
    other_vehicle = None
    helper = None
    frames = 0
    original_error = None
    try:
        world = client.generate_opendrive_world(map_text)
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        route = select_native_route(world.get_map())
        blueprints = world.get_blueprint_library().filter("vehicle.*")
        if not blueprints:
            raise ValueError("No Native vehicle blueprint")
        other_waypoint = world.get_map().get_waypoint_xodr(178247, -1, 25.0)
        if other_waypoint is None:
            raise ValueError("Assigned other-vehicle departure lane missing")
        other_vehicle = world.try_spawn_actor(blueprints[0], other_waypoint.transform)
        if other_vehicle is None:
            raise ValueError("Assigned other-vehicle spawn failed")
        observed_other = world.get_map().get_waypoint(other_vehicle.get_location(), project_to_road=False)
        if observed_other is None or (observed_other.road_id, observed_other.lane_id) != (178247, -1):
            raise ValueError("Assigned other vehicle outside departure lane")
        with spawn_native_left_turn(world, blueprints[0], route["waypoints"][:61],
                                     route["waypoints"][61:]) as built:
            vehicle = built["vehicle"]
            with _source_cameras(world, vehicle, carla, config["cameras"]) as sensors:
                queues = {name: Queue() for name in CAMERAS}
                for name, sensor in sensors.items():
                    sensor.listen(lambda image, name=name: queues[name].put(image))
                with ExitStack() as stack:
                    writers = {name: stack.enter_context(_ffv1(output/(name+".mkv"), size))
                               for name, size in CAMERAS.items()}
                    frame_map = stack.enter_context(FrameMap(output/"video_frames.jsonl"))
                    history = stack.enter_context((output/"drive_history.jsonl").open("x", buffering=1))
                    body_history = stack.enter_context((output/"body_history.jsonl").open("x", buffering=1))
                    helper = PipelineCapture(client, vehicle, output, CASE,
                                             required_observations=config["required_atoms"])
                    first_heading = None
                    onset_frame = None
                    try:
                        for _ in range(config["duration_s"] * config["rate_hz"]):
                            command = native_route_control(vehicle, route,
                                target_speed_mps=config["requested_speed_mps"])
                            requested = indicator_request_at_remaining_distance(
                                command["remaining_approach_m"],
                                start_m=config["indicator_start_m"])
                            set_native_left_blinker(vehicle, carla.VehicleLightState, requested)
                            vehicle.apply_control(carla.VehicleControl(
                                throttle=command["throttle"], brake=command["brake"],
                                steer=command["steer"]))
                            world.tick()
                            snap = world.get_snapshot()
                            for name in CAMERAS:
                                writers[name].write(_read_camera(queues[name], snap.frame))
                            frame_map.append(snap.frame, snap.timestamp.elapsed_seconds)
                            helper.capture(snap.frame, snap.timestamp.elapsed_seconds)
                            pose = vehicle.get_transform()
                            velocity = vehicle.get_velocity()
                            yaw = float(pose.rotation.yaw)
                            if first_heading is None:
                                first_heading = yaw
                            if onset_frame is None and _angle_delta(yaw, first_heading) >= 10:
                                onset_frame = int(snap.frame)
                            location = pose.location
                            native_waypoint = world.get_map().get_waypoint(location, project_to_road=False)
                            if native_waypoint is None:
                                raise ValueError("Native ego left the authored roadway")
                            vertices = vehicle.bounding_box.get_world_vertices(pose)
                            body = [[float(v.x), float(v.y), float(v.z)] for v in vertices]
                            if len(body) < 4:
                                raise ValueError("Native ego body geometry incomplete")
                            row = {"frame": int(snap.frame),
                                   "time_s": float(snap.timestamp.elapsed_seconds),
                                   "ego_position_xy_m": [float(location.x), float(location.y)],
                                   "ego_speed_mps": math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2),
                                   "ego_heading_deg": yaw,
                                   "ego_light_mask": int(vehicle.get_light_state()),
                                   "left_indicator": bool(vehicle.get_light_state() & carla.VehicleLightState.LeftBlinker),
                                   "native_road_id": int(native_waypoint.road_id),
                                   "requested_indicator": requested}
                            history.write(json.dumps(row, allow_nan=False)+"\n")
                            body_history.write(json.dumps({"frame": row["frame"],
                                "time_s": row["time_s"], "road_id": row["native_road_id"],
                                "body_vertices_m": body}, allow_nan=False)+"\n")
                            frames += 1
                    finally:
                        helper.close()
                        helper = None
        district_packet = getattr(args, "district_packet", None) or os.environ.get("SCENARIO_DISTRICT_SITE_PACKET")
        district = retain_district_source(district_packet, output, world.get_map().name)
        district_verified = district["district_review_verified"] and district["district_type"] == "business"
        context = {"native_map_id": world.get_map().name,
                   "approach_road_id": route["approach_road_id"],
                   "approach_lane_id": route["approach_lane_id"],
                   "outgoing_road_id": route["outgoing_road_id"],
                   "outgoing_lane_id": route["outgoing_lane_id"],
                   "native_route_source": "Native get_waypoint_xodr readback",
                   "district_type": district["district_type"] if district_verified else None,
                   "district_source": district["district_source"] if district_verified else None,
                   "district_source_document": district.get("district_source_document"),
                   "district_source_sha256": district.get("district_source_sha256"),
                   "district_review_verified": bool(district_verified),
                   "turn_onset_frame": onset_frame}
        (output/"route_context.json").write_text(json.dumps(context, indent=2)+"\n")
    except BaseException as error:
        original_error = error
        raise
    finally:
        if helper is not None:
            helper.close(confirmed=False)
        if other_vehicle is not None and other_vehicle.is_alive:
            other_vehicle.destroy()
        restoration = restore(client, saved)
        if original_error is None:
            seal_capture(output, frames=frames, restoration=restoration, errors=[],
                encoder_exit_codes={name: 0 for name in CAMERAS},
                context={"district_review_verified": bool(district_verified),
                         "native_left_turn_candidate": True})


def finalize_saved(attempt, output):
    """Derive the left-turn measurements only from staged original sources."""
    from worker_exchange.native_output import write_result, physical_result
    attempt, output = Path(attempt), Path(output)
    if (output.exists() or (attempt/"result.json").exists() or
            (attempt/"channels").exists() or (attempt.parent/"evidence").exists() or
            (attempt.parent/"evidence-checksums.json").exists()):
        raise ValueError("Retain prior finalization; choose a fresh saved version")
    required = ("config.json", "drive_history.jsonl", "body_history.jsonl",
                "route_context.json", "video_frames.jsonl", "trace.jsonl",
                "capture/evidence.jsonl", *(name+".mkv" for name in CAMERAS))
    for name in required:
        if not (attempt/name).is_file():
            raise ValueError("Missing required source: " + name)
    config = validate_capture_config(json.loads((attempt/"config.json").read_text()))
    description = config.get("recording_description")
    if not isinstance(description, dict) or not description.get("channels"):
        raise ValueError("Selected recording description required")
    report = analyze(attempt)
    rows = _rows(attempt/"drive_history.jsonl")
    frame_rows = _rows(attempt/"video_frames.jsonl")
    if len(rows) != len(frame_rows):
        raise ValueError("Original indicator/frame coverage incomplete")
    channel_root = attempt/"channels"
    channel_root.mkdir()
    specs = {"ego_speed": ("m/s", lambda r: r["ego_speed_mps"]),
             "ego_heading": ("deg", lambda r: r["ego_heading_deg"]),
             "ego_road_id": ("id", lambda r: r["native_road_id"]),
             "ego_turn_indicator": ("device state", lambda r: {
                 "reported_mask": r["ego_light_mask"],
                 "reported_device_state": "left" if r["left_indicator"] else "off"})}
    evidence = []
    for name, (unit, extract) in specs.items():
        with (channel_root/(name+".jsonl")).open("x") as stream:
            for row in rows:
                stream.write(json.dumps({"time_s": row["time_s"],
                    "original_frame": row["frame"], "value": extract(row)},
                    allow_nan=False)+"\n")
        evidence.append({"name": name, "unit": unit,
                         "reference": "channels/"+name+".jsonl"})
    # The pinned adapter opens Evidence(original.parent): a hash-bound export
    # beside this staged attempt. Rebuild it from saved sources, never labels.
    evidence_root = attempt.parent/"evidence"
    evidence_root.mkdir()
    original_export = ("trace.jsonl", "road.xodr", "route_context.json",
                       "drive_history.jsonl", "body_history.jsonl",
                       "district-site-packet.json", "district-site-source.txt")
    for name in original_export:
        source = attempt/name
        if source.is_file():
            shutil.copyfile(source, evidence_root/name)
    shutil.copytree(attempt/"capture", evidence_root/"capture")
    shutil.copyfile(channel_root/"ego_turn_indicator.jsonl",
                    evidence_root/"ego_turn_indicator.jsonl")
    checksums = {"evidence/"+p.relative_to(evidence_root).as_posix():
                 hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in evidence_root.rglob("*") if p.is_file()}
    (attempt.parent/"evidence-checksums.json").write_text(
        json.dumps(checksums, sort_keys=True, allow_nan=False)+"\n")
    (attempt/"district-context.json").write_text(json.dumps({"district_packet": {
        "district_type": report["district_type"],
        "native_map_id": json.loads((attempt/"route_context.json").read_text())["native_map_id"],
        "packet_sha256": report["sources"]["district-site-packet.json"],
        "document_sha256": report["sources"]["district-site-source.txt"],
        "legal_classification_confirmed": False}}, allow_nan=False)+"\n")
    evidence.append({"name": "district_packet", "unit": "source document",
                     "reference": "district-context.json"})
    distance = measure_continuous_left_signal_distance(report)
    boundary = source_district_boundary(report)
    turn_onset = measure_left_turn_onset(report)
    observed = report["observed_continuous_distance_meets_boundary"]
    result = {"case_id": CASE,
        "measured_values": {"continuous_left_signal_distance_m": distance,
                            "statutory_boundary_m": boundary,
                            "turn_onset_frame": report["turn_onset"]["frame"]},
        "target_checks": [{"target": "continuous_left_signal_at_least_100ft",
            "requested": True, "measured": observed,
            "method": "original left-lamp readback and sampled ego path through measured left-turn onset",
            "tolerance": 0.0, "matched": observed,
            "physical_cause_confirmed": False,
            "cause_evidence": ["drive_history.jsonl", "route_context.json",
                               "video_frames.jsonl"]}],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False, "termination_reason": "saved source assessment pending",
        "physical_failure_flags": ["Native left-lamp pixels and legal district review require independent review"],
        "trace_reference": "trace.jsonl",
        "video_references": [name+".mkv" for name in CAMERAS],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": description, "recording_evidence": evidence,
        "source_evidence_hashes": report["sources"],
        "capture_evidence_sha256": hashlib.sha256((attempt/"capture/evidence.jsonl").read_bytes()).hexdigest(),
        "realized_observables": {}}
    result = physical_result(attempt, result)
    analysis = {"format": "worker-left-turn-signal-analysis", "case_id": CASE,
        "measurements": {"continuous_left_signal_distance_m": {
            "value": distance, "unit": "m", "method": "measure_continuous_left_signal_distance",
            "sources": {name: report["sources"][name] for name in
                        ("drive_history.jsonl", "video_frames.jsonl", "route_context.json")}},
            "district_boundary_m": {"value": boundary, "unit": "m",
                "method": "source_district_boundary",
                "sources": {name: report["sources"][name] for name in
                            ("route_context.json", "district-site-packet.json",
                             "district-site-source.txt")}},
            "left_turn_onset": {"value": turn_onset, "method": "measure_left_turn_onset",
                "sources": {name: report["sources"][name] for name in
                            ("drive_history.jsonl", "video_frames.jsonl",
                             "route_context.json")}}},
        "source_report": report, "source_hashes": report["sources"],
        "physical_checks": result["physical_checks"],
        "legal_verdict_asserted": False}
    write_result(attempt, result)
    output.write_text(json.dumps(analysis, indent=2, allow_nan=False)+"\n")
    return analysis


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--district-packet")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--attempt")
    parser.add_argument("--output")
    args = parser.parse_args()
    config_path = Path(__file__).parent / "config.json"
    config = validate_capture_config(json.loads(config_path.read_text())) if config_path.is_file() else capture_config()
    if args.attempt:
        if not args.output:
            raise ValueError("--output required for saved finalization")
        finalize_saved(args.attempt, args.output)
        return
    if args.check:
        print(json.dumps({"case_id": CASE, "cpu_check_passed": True,
                          "carla_started": False, "map_sha256": MAP_SHA256}))
        return
    if not args.output_dir:
        raise ValueError("--output-dir required for Native capture")
    capture_native(args, config)


if __name__ == "__main__":
    main()
