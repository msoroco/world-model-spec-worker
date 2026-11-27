"""Lazy CARLA construction for controlled driver and bicycle proximity trials.

The requested bicycle blueprint and movements are engineering inputs. Recorded
Native actor IDs, classifications, bodies and responses are separate evidence.
"""
from __future__ import annotations

import hashlib
import json
import math

from controller import EngineeringKnobs, PathController
from geometry import (EGO_BLUEPRINT, RIDER_BLUEPRINT, EGO_START_X_M,
                      EGO_LANE_Y_M, RIDER_START_X_M, RIDER_Y_M,
                      open_drive, plan, route)


CAMERAS = (
    ("overview", 1920, 1080, (88.0, -10.0, 38.0), "world", 85),
    ("approach", 1280, 720, (64.0, -10.0, 12.0), "world", 80),
    ("reference_corner", 1280, 720, (96.0, -6.0, 9.0), "world", 75),
    ("driver_reference", 1280, 720, (0.0, 0.0, 2.0), "ego", 90),
)


def camera_plan() -> list[dict]:
    return [{"name": name, "width": width, "height": height,
             "xyz_m": list(xyz), "attachment": attachment, "fps": 20,
             "fov_deg": fov}
            for name, width, height, xyz, attachment, fov in CAMERAS]


def validate_camera_plan(specs: list[dict]) -> None:
    expected = camera_plan()
    if specs != expected:
        raise ValueError("Four-view camera plan differs")


def fixed_context() -> dict:
    rider_route = json.dumps(route("rider", "clear"), separators=(",", ":"))
    return {"cell_id": "C136495", "law_id": "NRS-484B-270-1",
            "actor": "motor_vehicle_driver", "duration_s": 30, "rate_hz": 20,
            "authored_road_sha256": hashlib.sha256(open_drive().encode()).hexdigest(),
            "ego_blueprint": EGO_BLUEPRINT, "rider_blueprint": RIDER_BLUEPRINT,
            "rider_route_sha256": hashlib.sha256(rider_route.encode()).hexdigest(),
            "camera_plan": camera_plan()}


def _wheel_geometry(actor) -> tuple[float, float]:
    wheels = actor.get_physics_control().wheels
    if len(wheels) < 2:
        raise RuntimeError("Native actor has no verified steering axle")
    wheelbase = (max(w.position.x for w in wheels) - min(w.position.x for w in wheels)) / 100
    steering = max(w.max_steer_angle for w in wheels)
    if not (wheelbase > 0 and steering > 0 and math.isfinite(wheelbase)):
        raise RuntimeError("Native actor steering geometry unverified")
    return wheelbase, steering


def build(client, carla, condition: str, candidate: str = "primary") -> dict:
    """Create the exact road, two actors, and measured-pose controllers.

    The caller must own an idle CARLA endpoint, save/restore world state, destroy
    returned actors, and record the original measurements. This function makes
    no claim of successful capture or rider behavior.
    """
    if candidate not in ("primary", "fallback1"):
        raise ValueError("Unknown rider candidate construction")
    source_plan = plan(condition)
    world = client.generate_opendrive_world(open_drive(), carla.OpendriveGenerationParameters(
        vertex_distance=.25, max_road_length=50, wall_height=0,
        additional_width=0, smooth_junctions=False,
        enable_mesh_visibility=True, enable_pedestrian_navigation=False))
    mapping = world.get_map()
    for role, xy in (("ego", (EGO_START_X_M, EGO_LANE_Y_M)),
                     ("rider", (RIDER_START_X_M, RIDER_Y_M))):
        waypoint = mapping.get_waypoint(carla.Location(x=xy[0], y=xy[1], z=.2),
                                        project_to_road=False,
                                        lane_type=carla.LaneType.Driving)
        if waypoint is None or waypoint.road_id != 136495 or waypoint.lane_id != -1:
            raise RuntimeError("Native narrow-road lane survey failed: " + role)
    library = world.get_blueprint_library()
    actors = {}
    try:
        for role, blueprint_id, x, y in (
            ("ego", EGO_BLUEPRINT, EGO_START_X_M, EGO_LANE_Y_M),
            ("rider", RIDER_BLUEPRINT, RIDER_START_X_M, RIDER_Y_M),
        ):
            blueprint = library.find(blueprint_id)
            blueprint.set_attribute("role_name", "c136495_" + role)
            actor = world.spawn_actor(blueprint, carla.Transform(
                carla.Location(x=x, y=y, z=.5), carla.Rotation(yaw=0)))
            if actor is None:
                raise RuntimeError("Native actor spawn failed: " + role)
            actors[role] = actor
        controllers = {}
        for role, actor in actors.items():
            wheelbase, steering = _wheel_geometry(actor)
            target = 7.0 if role == "ego" else 4.0
            lookahead = 2.5 if candidate == "fallback1" else 4.0
            controllers[role] = PathController(route(role, condition), wheelbase,
                                               steering,
                                               EngineeringKnobs(target_speed_mps=target,
                                                                lookahead_base_m=lookahead,
                                                                final_margin_m=0.0))
        return {"world": world, "actors": actors, "controllers": controllers,
                "source_plan": source_plan, "camera_plan": camera_plan(),
                "candidate_id": candidate,
                "physical_native_verified": False}
    except Exception:
        for actor in reversed(list(actors.values())):
            actor.destroy()
        raise


def command_from_native(controller: PathController, actor, dt_s: float) -> dict:
    pose = actor.get_transform()
    velocity = actor.get_velocity()
    speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
    return controller.step(position_xy_m=(pose.location.x, pose.location.y),
                           yaw_rad=math.radians(pose.rotation.yaw),
                           speed_mps=speed, dt_s=dt_s)
