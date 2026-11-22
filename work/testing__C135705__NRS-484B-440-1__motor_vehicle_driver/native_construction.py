"""Source-bound CARLA construction for the 200-foot standing-vehicle candidates.

All CARLA imports and world changes occur in run_native. This module can be
checked with small fake actors on a CPU without making a physical claim.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from standing_geometry import rectangle, segment_crosses_rect

ASSIGNMENT = "testing__C135705__NRS-484B-440-1__motor_vehicle_driver"
SUFFIXES = ("passage_clear_view", "passage_blocked", "view_occluded_both")
RATE_HZ = 20


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def candidate_opendrive():
    """Straight two-way paved road plus explicit 2.5 m shoulders, metres."""
    return '''<?xml version="1.0" encoding="UTF-8"?>
<OpenDRIVE>
  <header revMajor="1" revMinor="4" name="C135705 standing geometry candidate" version="1" north="6" south="-6" east="80" west="-80" vendor="worker-candidate"/>
  <road name="candidate two-way road with shoulders" length="160" id="440" junction="-1">
    <link/>
    <planView><geometry s="0" x="-80" y="0" hdg="0" length="160"><line/></geometry></planView>
    <elevationProfile><elevation s="0" a="0" b="0" c="0" d="0"/></elevationProfile>
    <lateralProfile/>
    <lanes><laneOffset s="0" a="0" b="0" c="0" d="0"/>
      <laneSection s="0"><center><lane id="0" type="none" level="false"/></center>
        <left>
          <lane id="1" type="driving" level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" weight="standard" color="yellow" width="0.12" laneChange="none"/></lane>
          <lane id="2" type="shoulder" level="false"><width sOffset="0" a="2.5" b="0" c="0" d="0"/></lane>
        </left>
        <right>
          <lane id="-1" type="driving" level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" weight="standard" color="yellow" width="0.12" laneChange="none"/></lane>
          <lane id="-2" type="shoulder" level="false"><width sOffset="0" a="2.5" b="0" c="0" d="0"/></lane>
        </right>
      </laneSection>
    </lanes>
  </road>
</OpenDRIVE>
'''


def validate_scene(scene, source_path=None):
    suffix = scene.get("case_id", "").removeprefix(ASSIGNMENT + "__")
    if suffix not in SUFFIXES or scene["case_id"] != ASSIGNMENT + "__" + suffix:
        raise ValueError("case differs from exact C135705 assignment")
    if scene.get("capture_rate_hz") != RATE_HZ or scene.get("duration_s", 0) < 8:
        raise ValueError("20 Hz and at least eight seconds required for passage")
    if scene.get("map_source_sha256") is None or not scene.get("map_source"):
        raise ValueError("source-bound OpenDRIVE required")
    if source_path is not None and sha(source_path) != scene["map_source_sha256"]:
        raise ValueError("OpenDRIVE source hash differs")
    road = rectangle(scene["paved_road_xy_m"], "paved road")
    shoulders = [rectangle(scene[k], k) for k in
                 ("shoulder_negative_y_xy_m", "shoulder_positive_y_xy_m")]
    if road != (-80., -3.5, 80., 3.5) or shoulders != [(-80., -6., 80., -3.5), (-80., 3.5, 80., 6.)]:
        raise ValueError("authored road/shoulders differ from candidate OpenDRIVE")
    if len(scene["sight_occluders_xy_m"]) != (2 if suffix == "view_occluded_both" else 0):
        raise ValueError("occluder count differs from exact comparison")
    for rect in scene["sight_occluders_xy_m"]:
        rectangle(rect, "occluder")
    if scene.get("standing_blueprint_id") is None or scene.get("passing_blueprint_id") is None:
        raise ValueError("fixed Native actor blueprint IDs required")
    if suffix == "view_occluded_both" and not scene.get("occluder_blueprint_id"):
        raise ValueError("actual occluder blueprint required")
    if scene.get("disabled_physical_mechanism") != "engine_off_brake_locked":
        raise ValueError("standing actor disability mechanism not constructed")
    return suffix


def _center(rect):
    x0, y0, x1, y1 = rectangle(rect, "actor target")
    return (x0+x1)/2, (y0+y1)/2


def _blueprint(world, name, role):
    bp = world.get_blueprint_library().find(name)
    if bp is None:
        raise ValueError("Native blueprint missing: " + name)
    if bp.has_attribute("role_name"):
        bp.set_attribute("role_name", role)
    return bp


def _spawn(world, carla, blueprint, x, y, yaw=0., z=.25):
    actor = world.spawn_actor(blueprint, carla.Transform(
        carla.Location(x=x, y=y, z=z), carla.Rotation(yaw=yaw)))
    if actor is None:
        raise RuntimeError("Native actor spawn failed: " + str(blueprint.id))
    return actor


def polygon(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    if len(vertices) != 8:
        raise ValueError("Native actor lacks eight 3D body vertices")
    points = sorted({(float(p.x), float(p.y)) for p in vertices})
    if len(points) != 4 or not all(math.isfinite(v) for p in points for v in p):
        raise ValueError("Native actor lacks four finite footprint corners")
    cx = sum(p[0] for p in points)/4
    cy = sum(p[1] for p in points)/4
    return [list(p) for p in sorted(points, key=lambda p: math.atan2(p[1]-cy,p[0]-cx))]


def bounds(points):
    return [min(p[0] for p in points), min(p[1] for p in points),
            max(p[0] for p in points), max(p[1] for p in points)]


def spawn_scene(world, scene, carla):
    """Create both real vehicles and both requested physical occluders."""
    actors = []
    try:
        x, y = _center(scene["standing_body_xy_m"])
        standing = _spawn(world, carla,
                          _blueprint(world,scene["standing_blueprint_id"],"c135705_standing"),x,y)
        actors.append(standing)
        # Persist an attempted mechanical failure, with brake engaged. The
        # statutory unavoidable-stop and temporary-duration findings still
        # require independent review and are never inferred from this command.
        standing.set_simulate_physics(False)
        standing.apply_control(carla.VehicleControl(throttle=0., brake=1., hand_brake=True))
        x, y = scene["other_vehicle_centers_xy_m"][0]
        passing = _spawn(world, carla,
                         _blueprint(world,scene["passing_blueprint_id"],"c135705_passing"),x,y,yaw=180.)
        actors.append(passing)
        props=[]
        for index,rect in enumerate(scene["sight_occluders_xy_m"]):
            x,y=_center(rect)
            prop=_spawn(world,carla,
                        _blueprint(world,scene["occluder_blueprint_id"],f"c135705_occluder_{index}"),x,y,z=0.)
            actors.append(prop);props.append(prop)
        return standing,passing,props,actors
    except BaseException:
        for actor in reversed(actors):
            actor.destroy()
        raise


def sample(actor, snapshot):
    transform=actor.get_transform();v=actor.get_velocity();body=polygon(actor)
    return {"frame":int(snapshot.frame),"time_s":float(snapshot.timestamp.elapsed_seconds),
            "actor_id":int(actor.id),"position_xy_m":[float(transform.location.x),float(transform.location.y)],
            "heading_deg":float(transform.rotation.yaw),"velocity_xy_mps":[float(v.x),float(v.y)],
            "speed_mps":math.hypot(v.x,v.y),"body_vertices_xy_m":body}


def occluder_probes(scene, props):
    """Measure actual prop bodies against both authored 200-foot sight rays."""
    target=_center(scene["standing_body_xy_m"])
    bodies=[bounds(polygon(prop)) for prop in props]
    probes={}
    for side in (-1,1):
        for distance in scene["sight_probe_distances_m"]:
            eye=(side*distance,scene["sight_eye_y_m"])
            hits=[i for i,body in enumerate(bodies) if segment_crosses_rect(eye,target,body)]
            probes[f"{'negative_x' if side<0 else 'positive_x'}:{distance:.3f}m"]={
                "eye_xy_m":eye,"target_xy_m":target,"actual_prop_hits":hits,"clear_geometry":not hits}
    return {"actual_prop_bodies_xy_m":bodies,"probes":probes}
