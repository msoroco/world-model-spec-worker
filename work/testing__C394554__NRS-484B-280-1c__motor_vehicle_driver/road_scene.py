"""Source-gated transit-stop encounter measurements.

Coordinates and engineering distances do not define statutory "near" or
"proper caution". The stop, bus and pedestrian must be read back from Native.
"""
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def point(value):
    if not isinstance(value, list) or len(value) != 3 or any(
            type(x) not in (int, float) or not math.isfinite(x) for x in value):
        raise ValueError("invalid original world point")
    return value


def footprint(vertices):
    if not isinstance(vertices, list) or len(vertices) < 4:
        raise ValueError("missing original actor body")
    for vertex in vertices:
        point(vertex)
    return (min(v[0] for v in vertices), min(v[1] for v in vertices),
            max(v[0] for v in vertices), max(v[1] for v in vertices))


def gap(a, b):
    ax0, ay0, ax1, ay1 = footprint(a)
    bx0, by0, bx1, by1 = footprint(b)
    return math.hypot(max(bx0 - ax1, ax0 - bx1, 0),
                      max(by0 - ay1, ay0 - by1, 0))


def load_site(path):
    path = Path(path)
    site = json.loads(path.read_text())
    if (site.get("format"), site.get("cell_id"), site.get("layout"),
            site.get("control")) != ("worker-transit-stop-site", "C394554", "road", "bus_stop"):
        raise ValueError("wrong transit-stop cell identity")
    source = site.get("map_source", {})
    map_path = path.parent / source.get("path", "")
    if not map_path.is_file() or sha(map_path) != source.get("sha256"):
        raise ValueError("missing or stale original road map source")
    if not site.get("road", {}).get("lane_source") or site["road"].get("road_id") is None:
        raise ValueError("original driving lane not read back")
    stop = site.get("stop", {})
    if not stop.get("actor_id") or not stop.get("blueprint_id", "").startswith("static.prop."):
        raise ValueError("physical bus stop actor not read back")
    if "busstop" not in stop["blueprint_id"].lower() and "bus_stop" not in stop["blueprint_id"].lower():
        raise ValueError("physical bus stop blueprint not identified")
    if not stop.get("position_source"):
        raise ValueError("bus stop placement source absent")
    point(stop.get("position_m"))
    bus = site.get("bus", {})
    model = bus.get("blueprint_id", "").lower()
    if not bus.get("actor_id") or not model.startswith("vehicle.") or not (
            "bus" in model or model == "vehicle.mitsubishi.fusorosa"):
        raise ValueError("original public bus actor not read back")
    point(bus.get("position_m"))
    footprint(bus.get("body_vertices_m"))
    if not bus.get("door_side_source") or not bus.get("door_region_source"):
        raise ValueError("bus boarding-side geometry not sourced")
    door = bus.get("door_region_m", {})
    if not all(type(door.get(k)) in (int, float) and math.isfinite(door[k]) for k in
               ("x_min", "x_max", "y_min", "y_max")):
        raise ValueError("bus door region absent")
    if not door["x_min"] < door["x_max"] or not door["y_min"] < door["y_max"]:
        raise ValueError("bus door region invalid")
    if math.dist(stop["position_m"], bus["position_m"]) > 20:
        raise ValueError("bus not at physical stop")
    return site


def measure(site, sample):
    if sample.get("ego_class") != "motor_vehicle" or sample.get("pedestrian_class") != "pedestrian":
        raise ValueError("wrong original participant classes")
    if not sample.get("ego_class_source") or not sample.get("pedestrian_class_source"):
        raise ValueError("original participant class source absent")
    if sample.get("bus_actor_id") != site["bus"]["actor_id"] or sample.get("stop_actor_id") != site["stop"]["actor_id"]:
        raise ValueError("transit actors differ from original site")
    if not sample.get("driver_control_source"):
        raise ValueError("original driver control source absent")
    event = sample.get("driver_observation_event")
    if event is not None and (event.get("source") != "original_driver_input" or event.get("observed") is not True):
        raise ValueError("driver observation is not an original input")
    ego, ped, bus = (sample.get(key) for key in
                     ("ego_body_vertices_m", "pedestrian_body_vertices_m", "bus_body_vertices_m"))
    for body in (ego, ped, bus):
        footprint(body)
    if any(math.dist(now, prior) > 0.1 for now, prior in
           zip(bus, site["bus"]["body_vertices_m"])):
        raise ValueError("bus body changed from stop-site readback")
    speed, brake = sample.get("ego_speed_mps"), sample.get("ego_brake")
    if type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0:
        raise ValueError("original ego speed absent")
    if type(brake) not in (int, float) or not 0 <= brake <= 1:
        raise ValueError("original brake input absent")
    x0, y0, x1, y1 = footprint(ped)
    door = site["bus"]["door_region_m"]
    door_gap = math.hypot(max(door["x_min"] - x1, x0 - door["x_max"], 0),
                          max(door["y_min"] - y1, y0 - door["y_max"], 0))
    phase = sample.get("passenger_phase")
    if phase not in ("waiting_at_stop", "boarding_bus"):
        raise ValueError("original passenger phase absent")
    return {"pedestrian_stop_distance_m": math.dist(
                [(x0+x1)/2, (y0+y1)/2], site["stop"]["position_m"][:2]),
            "pedestrian_bus_body_gap_m": gap(ped, bus),
            "pedestrian_bus_door_region_gap_m": door_gap,
            "passenger_phase": phase, "driver_observation_event": event,
            "ego_speed_mps": speed, "ego_brake": brake,
            "legal_near_stop_verdict": None, "legal_boarding_verdict": None,
            "legal_proper_caution_verdict": None}


def controller(measurement):
    """A fixed engineering brake response to the scripted driver input."""
    brake = 1.0 if measurement.get("driver_observation_event") else 0.0
    return {"throttle": 0.0 if brake else 0.25, "brake": brake, "steer": 0.0}
