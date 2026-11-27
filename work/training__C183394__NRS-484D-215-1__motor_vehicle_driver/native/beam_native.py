"""Lazy CARLA setup and per-tick command for the authored beam comparison.

The caller owns world restoration and original capture. These functions fail on
missing map/actor/lamp readback instead of reporting a successful physical run.
"""
from __future__ import annotations

from math import hypot

from beam_scene import beam_request, request


def install(client, carla, case, acceleration_gain=.20):
    if not 0 < acceleration_gain <= .5:
        raise ValueError("invalid vehicle acceleration gain")
    plan = request(case)
    world = client.generate_opendrive_world(plan["road_opendrive"],
        carla.OpendriveGenerationParameters(vertex_distance=.25, max_road_length=50,
            wall_height=0, additional_width=0, smooth_junctions=False,
            enable_mesh_visibility=True, enable_pedestrian_navigation=False))
    settings = world.get_settings()
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = .05
    world.apply_settings(settings)
    world.set_weather(carla.WeatherParameters(sun_altitude_angle=-30,
                                             precipitation=0, fog_density=0))
    mapping = world.get_map()
    for role, lane_type in (("ego", carla.LaneType.Shoulder),
                            ("oncoming", carla.LaneType.Driving)):
        item = plan[role]
        point = carla.Location(*item["start_xyz_m"])
        waypoint = mapping.get_waypoint(point, project_to_road=False, lane_type=lane_type)
        if waypoint is None or waypoint.road_id != plan["road_id"] \
                or waypoint.lane_id != item["target_lane_id"]:
            raise RuntimeError("original shoulder/oncoming map readback differs: " + role)
    library = world.get_blueprint_library()
    owned = []
    for role in ("ego", "oncoming"):
        item = plan[role]
        blueprint = library.find(item["blueprint"])
        blueprint.set_attribute("role_name", "c183394_" + role)
        transform = carla.Transform(carla.Location(*item["start_xyz_m"]),
                                    carla.Rotation(yaw=item["heading_deg"]))
        actor = world.try_spawn_actor(blueprint, transform)
        if actor is None:
            for prior in reversed(owned):
                prior.destroy()
            raise RuntimeError("original vehicle spawn failed: " + role)
        owned.append(actor)
    return {"world": world, "map": mapping, "ego": owned[0],
            "oncoming": owned[1], "owned": owned, "plan": plan,
            "acceleration_gain": acceleration_gain,
            "physical_verified": False}


def command_tick(scene, carla):
    ego, other = scene["ego"], scene["oncoming"]
    ep, op = ego.get_transform().location, other.get_transform().location
    separation = hypot(ep.x - op.x, ep.y - op.y)
    state = beam_request(scene["plan"]["beam_mode"], separation)
    light = carla.VehicleLightState
    requested_bits = light.Position | (light.LowBeam if state == "low_beam" else light.HighBeam)
    ego.set_light_state(light(requested_bits))
    for actor in (ego, other):
        velocity = actor.get_velocity()
        speed = hypot(velocity.x, velocity.y)
        actor.apply_control(carla.VehicleControl(
            throttle=scene["acceleration_gain"] if speed < 2.5 else 0,
                                                 brake=.18 if speed > 3 else 0,
                                                 steer=0))
    observed_bits = int(ego.get_light_state())
    if observed_bits & int(light.LowBeam if state == "low_beam" else light.HighBeam) == 0:
        raise RuntimeError("original headlamp state readback differs")
    return {"separation_m": separation, "requested_beam_state": state,
            "observed_light_state_bits": observed_bits,
            "glare_or_lowermost_proven": False}
