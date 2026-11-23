"""Validate three-vehicle route candidates and measured release permissions.

Permissions are engineering controller inputs. Original Native motion and
source-camera frames decide whether the selected branch was actually realized.
"""

import hashlib
import json
import math
from pathlib import Path
from xml.etree import ElementTree as ET


ROLES = ("ego", "earlier", "occupant")
CASES = ("off_stop_earlier_and_occupied", "off_stop_earlier_only",
         "off_stop_occupant_only", "off_no_full_halt", "operative_signal")
CONDITIONS = {"observed_ego_halt", "observed_occupant_entry",
              "minimum_body_separation", "observed_earlier_halt",
              "scheduled_frame", "observed_earlier_clearance",
              "observed_occupant_halt"}


def _point(value):
    if (not isinstance(value, list) or len(value) != 2 or
            any(type(v) not in (int, float) or not math.isfinite(v) for v in value)):
        raise ValueError("Finite route XY point required")
    return value


def validate(path):
    path = Path(path)
    plan = json.loads(path.read_text())
    if plan.get("format") != "c24811-three-vehicle-route-candidate-v1":
        raise ValueError("Three-vehicle C24811 candidate required")
    site = json.loads(path.with_name("blind-site-candidate.json").read_text())
    map_path = path.with_name(site["map"]["path"])
    digest = hashlib.sha256(map_path.read_bytes()).hexdigest()
    if digest != plan.get("map_sha256") or digest != site["map"]["sha256"]:
        raise ValueError("Route map differs from site candidate")
    roads = {int(road.get("id")): road for road in ET.parse(map_path).getroot().findall("road")}
    vehicles = plan.get("vehicles")
    if not isinstance(vehicles, dict) or set(vehicles) != set(ROLES):
        raise ValueError("Three distinct vehicle routes required")
    spawns = {}
    for role in ROLES:
        row = vehicles[role]
        spawn = row.get("spawn_road_lane_s")
        if (not isinstance(spawn, list) or len(spawn) != 3 or
                any(type(x) is not int for x in spawn[:2]) or
                type(spawn[2]) not in (int, float)):
            raise ValueError("Sourced Native spawn required: " + role)
        road = roads.get(spawn[0])
        if road is None or spawn[1] != -1 or not 0 <= spawn[2] < float(road.get("length")):
            raise ValueError("Spawn outside authored approach: " + role)
        expected = site["entrances"]["ego" if role == "ego" else "other"]
        if spawn[:2] != [expected["road_id"], expected["lane_id"]]:
            raise ValueError("Spawn differs from governed approach: " + role)
        marks = [obj for obj in road.findall("objects/object")
                 if obj.get("id") == str(expected["stop_line_object_id"]) and
                 obj.get("name") == "StopLine"]
        if (len(marks) != 1 or float(marks[0].get("s")) != row.get("stop_line_s_m") or
                row.get("stop_line_point_xy_m") != expected["stop_boundary_point_xy_m"] or
                row.get("upstream_normal_xy") != ([-1, 0] if role == "ego" else [0, -1])):
            raise ValueError("Route stop reference differs from authored map: " + role)
        targets = row.get("target_xy_m")
        if not isinstance(targets, list) or len(targets) < 2:
            raise ValueError("Complete route targets required: " + role)
        for target in targets:
            _point(target)
        speed = row.get("target_speed_mps")
        if type(speed) not in (int, float) or not math.isfinite(speed) or not 0 < speed <= 10:
            raise ValueError("Bounded route speed required: " + role)
        required = row.get("release_after")
        if not isinstance(required, list) or not required or not set(required) <= CONDITIONS:
            raise ValueError("Measured release conditions required: " + role)
        spawns[role] = (spawn[2], expected["road_id"])
    spacing = plan.get("minimum_spawn_spacing_m")
    if type(spacing) not in (int, float) or spacing < 10:
        raise ValueError("Positive spawn-spacing engineering threshold required")
    if (spawns["earlier"][0] <= spawns["occupant"][0] or
            spawns["earlier"][0] - spawns["occupant"][0] < spacing):
        raise ValueError("Earlier and occupant vehicles overlap or reverse on shared lane")
    separation = plan.get("minimum_ego_occupant_body_separation_m")
    if type(separation) not in (int, float) or not math.isfinite(separation) or separation < 2:
        raise ValueError("Positive body-separation threshold required")
    controls = plan.get("case_controls")
    if not isinstance(controls, dict) or set(controls) != set(CASES):
        raise ValueError("All five exact case controls required")
    for name, control in controls.items():
        if (control.get("signal") not in ("Off", "explicit_operative_indication") or
                control.get("ego_stop") not in ("full_halt", "rolling") or
                control.get("earlier_stop") not in ("full_halt", "no_prior_halt") or
                control.get("occupant_entry") not in ("required", "hold_before_entry")):
            raise ValueError("Invalid case control: " + name)
        override = control.get("ego_target_speed_override_mps")
        if override is not None and (name != "off_no_full_halt" or
                type(override) not in (int, float) or not math.isfinite(override) or
                not 1 <= override <= vehicles["ego"]["target_speed_mps"]):
            raise ValueError("Rolling comparison speed override invalid")
    return {"map_sha256": digest, "route_roles": list(ROLES),
            "shared_lane_spawn_spacing_m": spawns["earlier"][0]-spawns["occupant"][0],
            "case_count": len(controls), "native_motion_verified": False}


def release_permission(plan, case_name, role, observed):
    """Gate control on measured histories, never on a planned timestamp alone."""
    if case_name not in CASES or role not in ROLES:
        raise ValueError("Exact case and vehicle role required")
    if not isinstance(observed, dict):
        raise ValueError("Measured controller feedback required")
    control = plan["case_controls"][case_name]
    if role == "ego":
        needed = ["minimum_body_separation"]
        if control["ego_stop"] == "full_halt":
            needed.append("observed_ego_halt")
        needed.append("observed_earlier_clearance" if control["occupant_entry"] == "hold_before_entry"
                      else "observed_occupant_entry")
    elif role == "earlier":
        needed = ["scheduled_frame"]
        if control["earlier_stop"] == "full_halt":
            needed.append("observed_earlier_halt")
    else:
        if control["occupant_entry"] == "hold_before_entry":
            return False
        needed = ["observed_earlier_clearance", "observed_occupant_halt"]
    for key in needed:
        if key == "minimum_body_separation":
            distance = observed.get("ego_occupant_body_separation_m")
            if type(distance) not in (int, float) or not math.isfinite(distance):
                raise ValueError("Measured body separation required")
            if distance < plan["minimum_ego_occupant_body_separation_m"]:
                return False
        elif observed.get(key) is not True:
            return False
    return True


if __name__ == "__main__":
    print(json.dumps(validate(Path(__file__).with_name("interaction-routes.json")), indent=2))
