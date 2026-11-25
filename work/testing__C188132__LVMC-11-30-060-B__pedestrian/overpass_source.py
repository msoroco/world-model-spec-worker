"""Source-bound engineering candidate for the C188132 overpass crossing.

The elevated deck is an OpenDRIVE feature. Native readback and pixels must still
confirm that CARLA actually renders it; this module makes no legal decision.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from xml.etree import ElementTree as ET
from site_review import inspect as inspect_site


ASSIGNMENT = "testing__C188132__LVMC-11-30-060-B__pedestrian"
CASES = ("yield_before_vehicle", "enter_ahead_of_vehicle", "designated_prohibition")
FPS = 20
FRAMES = 900


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_map(path):
    root = ET.parse(path).getroot()
    if root.tag != "OpenDRIVE":
        raise ValueError("OpenDRIVE source required")
    roads = {road.attrib.get("id"): road for road in root.findall("road")}
    if set(roads) != {"1", "2"}:
        raise ValueError("surface roadway and elevated overpass required")
    surface, deck = roads["1"], roads["2"]
    for road in (surface, deck):
        if float(road.attrib["length"]) < 20:
            raise ValueError("road segment is too short")
        if road.find("./planView/geometry/line") is None:
            raise ValueError("straight road geometry required")
    z0 = float(surface.find("./elevationProfile/elevation").attrib["a"])
    z1 = float(deck.find("./elevationProfile/elevation").attrib["a"])
    if abs(z0) > 0.01 or z1 - z0 < 4.0:
        raise ValueError("source has no elevated pedestrian deck")
    types = [lane.attrib.get("type") for lane in deck.findall("./lanes/laneSection/*/lane")]
    if "sidewalk" not in types:
        raise ValueError("overpass pedestrian deck absent")
    surface_types = [lane.attrib.get("type") for lane in surface.findall("./lanes/laneSection/*/lane")]
    if "driving" not in surface_types:
        raise ValueError("surface vehicle roadway absent")
    return {"surface_z_m": z0, "deck_z_m": z1, "source_sha256": sha(path)}


def validate_case(scene, map_path):
    if scene.get("assignment_id") != ASSIGNMENT:
        raise ValueError("wrong assignment")
    if scene.get("case_id") != ASSIGNMENT + "__" + scene.get("variant", ""):
        raise ValueError("wrong exact case")
    if scene["variant"] not in CASES:
        raise ValueError("unknown variant")
    source = validate_map(map_path)
    if scene.get("map_sha256") != source["source_sha256"]:
        raise ValueError("candidate map changed")
    if scene.get("fps") != FPS or scene.get("frames") != FRAMES:
        raise ValueError("full 20 Hz acquisition required")
    if scene.get("pedestrian_start_xyz") != [0.0, -8.0, 0.2]:
        raise ValueError("pedestrian must start south of roadway")
    if scene.get("pedestrian_goal_xyz") != [0.0, 8.0, 0.2]:
        raise ValueError("pedestrian must reach opposite side")
    if scene.get("vehicle_start_xyz") != [-30.0, -1.75, 0.3]:
        raise ValueError("roadway vehicle must approach from west")
    if scene.get("crossing_point_xy_m") != [0.0, 0.0]:
        raise ValueError("crossing must pass under provided deck")
    if scene.get("designated_prohibition") != (scene["variant"] == "designated_prohibition"):
        raise ValueError("exception context differs from case")
    if scene.get("requested_hold_until_vehicle_passes") != (scene["variant"] == "yield_before_vehicle"):
        raise ValueError("controller request differs from case")
    if scene.get("pedestrian_speed_mps") != 1.4 or scene.get("vehicle_speed_mps") != 5.0:
        raise ValueError("comparison motion policy changed")
    return source


def _point(actor):
    p = actor.get_transform().location
    out = [float(p.x), float(p.y), float(p.z)]
    if not all(math.isfinite(v) for v in out):
        raise ValueError("nonfinite Native location")
    return out


def spawn_pair(world, carla, scene):
    """Spawn both requested participants; caller owns cleanup and world restoration."""
    walkers = world.get_blueprint_library().filter("walker.pedestrian.*")
    vehicles = world.get_blueprint_library().filter("vehicle.*")
    if not walkers or not vehicles:
        raise ValueError("pedestrian and vehicle blueprints required")
    def transform(xyz, yaw):
        return carla.Transform(carla.Location(*xyz), carla.Rotation(yaw=yaw))
    walker = world.try_spawn_actor(walkers[0], transform(scene["pedestrian_start_xyz"], 90))
    if walker is None:
        raise RuntimeError("Native pedestrian spawn failed")
    vehicle = world.try_spawn_actor(vehicles[0], transform(scene["vehicle_start_xyz"], 0))
    if vehicle is None:
        walker.destroy()
        raise RuntimeError("Native roadway vehicle spawn failed")
    return walker, vehicle


def request_controls(carla, scene, walker, vehicle):
    """Apply one requested control step from current Native positions."""
    wp = _point(walker)
    vp = _point(vehicle)
    hold = scene["requested_hold_until_vehicle_passes"] and vp[0] < 6.0
    walker_speed = 0.0 if hold else scene["pedestrian_speed_mps"]
    walker.apply_control(carla.WalkerControl(carla.Vector3D(0, 1, 0), walker_speed, False))
    vehicle.set_target_velocity(carla.Vector3D(scene["vehicle_speed_mps"], 0, 0))
    return {"walker_requested_mps": walker_speed,
            "vehicle_requested_mps": scene["vehicle_speed_mps"],
            "vehicle_position_before_step_m": vp, "walker_position_before_step_m": wp}


def native_sample(scene, snapshot, walker, vehicle, world=None):
    """Read original actor states after world.tick, never the requested targets."""
    frame = int(snapshot.frame)
    time_s = float(snapshot.timestamp.elapsed_seconds)
    if not math.isfinite(time_s):
        raise ValueError("nonfinite Native time")
    if world is None:
        actors = [vehicle]
    else:
        actors = list(world.get_actors().filter("vehicle.*"))
    inventory = []
    for actor in actors:
        velocity = actor.get_velocity()
        xyz = _point(actor)
        values = [float(velocity.x), float(velocity.y), float(velocity.z)]
        if not all(math.isfinite(value) for value in values):
            raise ValueError("nonfinite Native vehicle velocity")
        inventory.append({"actor_id": int(actor.id), "xyz_m": xyz,
                          "velocity_xyz_mps": values})
    inventory.sort(key=lambda item: item["actor_id"])
    if len({item["actor_id"] for item in inventory}) != len(inventory) or not any(
            item["actor_id"] == int(vehicle.id) for item in inventory):
        raise ValueError("original vehicle inventory omits selected vehicle or duplicates identity")
    return {"case_id": scene["case_id"], "frame": frame, "time_s": time_s,
            "pedestrian_actor_id": int(walker.id), "vehicle_actor_id": int(vehicle.id),
            "pedestrian_xyz_m": _point(walker), "vehicle_xyz_m": _point(vehicle),
            "vehicle_velocity_xyz_mps": [float(v) for v in
                (vehicle.get_velocity().x, vehicle.get_velocity().y, vehicle.get_velocity().z)],
            "all_native_vehicles": inventory}


def measure_original(scene, rows):
    """Measure route order and conflict from source-bound original frames.

    The 0.5 m crossing band is an engineering observation bin, not a legal
    definition of yielding or right-of-way.
    """
    if len(rows) != FRAMES:
        raise ValueError("full original 900-frame history required")
    expected = scene["case_id"]
    ids = {(r.get("pedestrian_actor_id"), r.get("vehicle_actor_id")) for r in rows}
    if len(ids) != 1 or any(not isinstance(i, int) or i <= 0 for i in next(iter(ids))):
        raise ValueError("participant identity changed or missing")
    if any(r.get("case_id") != expected for r in rows):
        raise ValueError("original case identity changed")
    frames = [r["frame"] for r in rows]
    times = [r["time_s"] for r in rows]
    if any(b != a+1 for a, b in zip(frames, frames[1:])):
        raise ValueError("original frame gap")
    if any(abs((b-a)-.05) > .001 for a, b in zip(times, times[1:])):
        raise ValueError("original 20 Hz time gap")
    for row in rows:
        for key in ("pedestrian_xyz_m", "vehicle_xyz_m", "vehicle_velocity_xyz_mps"):
            values = row.get(key)
            if not isinstance(values, list) or len(values) != 3 or not all(
                isinstance(v, (float, int)) and math.isfinite(v) for v in values):
                raise ValueError("missing original participant source: "+key)
        inventory = row.get("all_native_vehicles")
        if not isinstance(inventory, list) or not inventory:
            raise ValueError("missing original all-vehicle inventory")
        inventory_ids = set()
        for item in inventory:
            ident = item.get("actor_id") if isinstance(item, dict) else None
            if not isinstance(ident, int) or ident <= 0 or ident in inventory_ids:
                raise ValueError("invalid original vehicle inventory identity")
            inventory_ids.add(ident)
            for key in ("xyz_m", "velocity_xyz_mps"):
                values = item.get(key)
                if not isinstance(values, list) or len(values) != 3 or not all(
                    isinstance(v, (int, float)) and math.isfinite(v) for v in values):
                    raise ValueError("missing original vehicle inventory source: "+key)
        target = next((item for item in inventory if item["actor_id"] == row["vehicle_actor_id"]), None)
        if target is None or target["xyz_m"] != row["vehicle_xyz_m"] or target[
                "velocity_xyz_mps"] != row["vehicle_velocity_xyz_mps"]:
            raise ValueError("selected vehicle differs from original all-vehicle inventory")
    pedestrian_entry = next((r for r in rows if r["pedestrian_xyz_m"][1] >= -3.5), None)
    pedestrian_exit = next((r for r in rows if r["pedestrian_xyz_m"][1] >= 3.5), None)
    vehicle_pass = next((r for r in rows if r["vehicle_xyz_m"][0] >= 0.5), None)
    if pedestrian_entry is None or pedestrian_exit is None or vehicle_pass is None:
        raise ValueError("physical crossing or vehicle passage incomplete")
    if pedestrian_entry["frame"] >= pedestrian_exit["frame"]:
        raise ValueError("pedestrian crossing order invalid")
    overlap = [r["frame"] for r in rows if abs(r["pedestrian_xyz_m"][1]+1.75) <= .5
               and abs(r["vehicle_xyz_m"][0]) <= 2.5]
    return {"case_id": expected, "frames": len(rows),
            "pedestrian_road_entry_frame": pedestrian_entry["frame"],
            "pedestrian_road_exit_frame": pedestrian_exit["frame"],
            "vehicle_crossing_pass_frame": vehicle_pass["frame"],
            "pedestrian_entered_after_vehicle_passed": pedestrian_entry["frame"] > vehicle_pass["frame"],
            "simultaneous_engineering_conflict_frames": overlap,
            "designated_prohibition_source_context": scene["designated_prohibition"],
            "observed_native_vehicle_actor_ids": sorted({item["actor_id"] for row in rows
                                                           for item in row["all_native_vehicles"]}),
            "roadway_classification": "requires_source_map_review",
            "legal_right_of_way": "unresolved"}


def audit_saved(attempt, *, diagnostic=False):
    """Independent hash and frame audit; no synthetic physical acceptance."""
    attempt = Path(attempt).resolve()
    manifest = json.loads((attempt/"original-sources.json").read_text())
    if manifest.get("format") != "c188132-original-sources-v1":
        raise ValueError("original source manifest absent")
    def source(key):
        entry = manifest[key]
        path = (attempt/entry["path"]).resolve()
        if not path.is_relative_to(attempt) or sha(path) != entry["sha256"]:
            raise ValueError("missing or stale original source: "+key)
        return path
    scene = json.loads(source("scene").read_text())
    validate_case(scene, source("map"))
    site = inspect_site(source("site_review"), source("map"), scene,
                        diagnostic=diagnostic)
    for key, expected in (("site_review_source", site["site_source_sha256"]),
                          ("municipal_source", site["municipal_source_sha256"])):
        if sha(source(key)) != expected:
            raise ValueError("reviewed source differs from original source manifest: "+key)
    rows = [json.loads(line) for line in source("body_history").read_text().splitlines() if line]
    measured = measure_original(scene, rows)
    joins = [json.loads(line) for line in source("frame_map").read_text().splitlines() if line]
    if [(r["frame"], r["time_s"]) for r in rows] != [
        (r.get("carla_frame", r.get("frame")), r["time_s"]) for r in joins]:
        raise ValueError("original video frame map differs")
    measured["roadway_classification"] = "reviewed_surface_bounds_and_native_inventory"
    measured["reviewed_roadway_y_bounds_m"] = site["roadway_y_bounds_m"]
    measured["reviewed_municipal_designation"] = site["designation_prohibited"]
    return {"format": "c188132-saved-source-audit-v1", "measurement": measured,
            "source_hashes": {k: manifest[k]["sha256"] for k in
                              ("scene", "map", "body_history", "frame_map",
                               "site_review", "site_review_source", "municipal_source")},
            "physical_acceptance_claimed": False}


def audit_pair(first, second, comparison, *, diagnostic=False,
               first_processing=None, second_processing=None):
    """Compare original histories with only declared source changes."""
    roots = [Path(first).resolve(), Path(second).resolve()]
    if diagnostic:
        saved = [audit_saved(root, diagnostic=True) for root in roots]
    else:
        from delivery_audit import audit as audit_delivery
        if first_processing is None or second_processing is None:
            raise ValueError('both saved processing receipts required for original comparison')
        saved = [audit_delivery(root, pixel_review=root/'original-pixel-review.json',
                                processing_receipt=receipt)
                 for root, receipt in zip(roots, (first_processing, second_processing))]
    scenes = [json.loads((root/"scene.json").read_text()) for root in roots]
    if diagnostic:
        first_map = saved[0]['source_hashes']['map']
        second_map = saved[1]['source_hashes']['map']
    else:
        first_map = sha(roots[0]/'candidate-overpass.xodr')
        second_map = sha(roots[1]/'candidate-overpass.xodr')
    if first_map != second_map:
        raise ValueError("comparison physical map differs")
    baseline = {k:v for k,v in scenes[0].items() if k not in
                ("case_id", "variant", "requested_hold_until_vehicle_passes",
                 "designated_prohibition", "prohibition_context")}
    other = {k:v for k,v in scenes[1].items() if k not in
             ("case_id", "variant", "requested_hold_until_vehicle_passes",
              "designated_prohibition", "prohibition_context")}
    if baseline != other:
        raise ValueError("comparison fixed construction changed")
    if comparison == "entry_timing":
        if [s["variant"] for s in scenes] != list(CASES[:2]):
            raise ValueError("wrong entry-timing pair")
        if scenes[0]["designated_prohibition"] or scenes[1]["designated_prohibition"]:
            raise ValueError("prohibition must be absent in entry comparison")
        if not scenes[0]["requested_hold_until_vehicle_passes"] or scenes[1]["requested_hold_until_vehicle_passes"]:
            raise ValueError("entry controller difference missing")
    elif comparison == "designated_exception":
        if [s["variant"] for s in scenes] != list(CASES[1:]):
            raise ValueError("wrong exception pair")
        if scenes[0]["designated_prohibition"] or not scenes[1]["designated_prohibition"]:
            raise ValueError("declared prohibition difference missing")
        if any(s["requested_hold_until_vehicle_passes"] for s in scenes):
            raise ValueError("exception controller changed")
    else:
        raise ValueError("unknown comparison")
    rows = []
    for root in roots:
        manifest = json.loads((root/"original-sources.json").read_text())
        entry = manifest["body_history"]
        rows.append([json.loads(line) for line in (root/entry["path"]).read_text().splitlines() if line])
    if [(r["frame"],r["time_s"]) for r in rows[0]] != [
        (r["frame"],r["time_s"]) for r in rows[1]]:
        raise ValueError("comparison original frame/time join differs")
    if any(a["vehicle_xyz_m"] != b["vehicle_xyz_m"] or
           a["vehicle_velocity_xyz_mps"] != b["vehicle_velocity_xyz_mps"]
           for a,b in zip(*rows)):
        raise ValueError("comparison roadway vehicle trajectory changed")
    if any(a["all_native_vehicles"] != b["all_native_vehicles"]
           for a,b in zip(*rows)):
        raise ValueError("comparison original all-vehicle inventory changed")
    if comparison == "entry_timing":
        a,b = [s["measurement"] for s in saved]
        if not a["pedestrian_entered_after_vehicle_passed"] or b["pedestrian_entered_after_vehicle_passed"]:
            raise ValueError("original entry-timing contrast absent")
    elif any(a["pedestrian_xyz_m"] != b["pedestrian_xyz_m"] for a,b in zip(*rows)):
        raise ValueError("exception comparison pedestrian motion changed")
    return {"format":"c188132-original-comparison-v1", "comparison_id":comparison,
            "case_ids":[s["case_id"] for s in scenes],
            "original_sources_verified":True, "physical_acceptance_claimed":False,
            "legal_right_of_way":"unresolved"}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--first', required=True)
    parser.add_argument('--second', required=True)
    parser.add_argument('--comparison', required=True, choices=('entry_timing', 'designated_exception'))
    parser.add_argument('--first-processing', required=True)
    parser.add_argument('--second-processing', required=True)
    args = parser.parse_args()
    print(json.dumps(audit_pair(args.first, args.second, args.comparison,
                                first_processing=args.first_processing,
                                second_processing=args.second_processing), indent=2))


if __name__ == '__main__':
    main()
