"""Lazy CARLA construction for the exact crosswalk pass or hold requests."""
from contextlib import contextmanager
import xml.etree.ElementTree as ET

from crosswalk_pass_scene import CAMERAS, validate


def pose(carla, xyz, pitch=0, yaw=0):
    return carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                           carla.Rotation(pitch=pitch, yaw=yaw))


def checked_map(world, scene):
    source = world.get_map().to_opendrive()
    root = ET.fromstring(source)
    road = root.find("road")
    if road is None or road.get("id") != "146108":
        raise ValueError("Original one-way road readback differs")
    if len(road.findall("lanes/laneSection/right/lane")) != 2:
        raise ValueError("Original two same-direction lanes missing")
    kind = scene["crosswalk_kind_requested"]
    if kind == "marked":
        if road.find("objects/object") is None or road.find("objects/object").get("type") != "crosswalk":
            raise ValueError("Original marked crossing missing")
    elif kind == "unmarked_intersection":
        if (root.find("junction/connection/laneLink") is None or len(root.findall("road")) != 4 or
                road.find("objects/object").get("type") == "crosswalk"):
            raise ValueError("Original unmarked intersection geometry missing or painted")
    else:
        raise ValueError("Crossing kind differs")
    return source


@contextmanager
def constructed_scene(client, carla, scene):
    validate(scene)
    world = client.generate_opendrive_world(scene["road_opendrive"])
    source = checked_map(world, scene)
    settings = world.get_settings()
    prior_sync, prior_delta = settings.synchronous_mode, settings.fixed_delta_seconds
    owned = []
    try:
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        observed = world.get_settings()
        if not observed.synchronous_mode or abs(observed.fixed_delta_seconds - .05) > 1e-6:
            raise RuntimeError("Original 20 Hz readback differs")
        library = world.get_blueprint_library()
        def spawn(blueprint, xyz, yaw=0):
            actor = world.try_spawn_actor(library.find(blueprint), pose(carla, xyz, yaw=yaw))
            if actor is None:
                raise RuntimeError("Original actor spawn failed: " + blueprint)
            owned.append(actor)
            return actor
        ego = spawn(scene["ego"]["blueprint"], [*scene["ego"]["start_xy_m"], .5])
        lead = spawn(scene["lead"]["blueprint"], [*scene["lead"]["center_xy_m"], .5])
        walkers = library.filter("walker.pedestrian.*")
        if not walkers:
            raise RuntimeError("Original pedestrian blueprint unavailable")
        pedestrian = world.try_spawn_actor(walkers[0], pose(carla, [*scene["pedestrian"]["start_xy_m"], .5]))
        if pedestrian is None:
            raise RuntimeError("Original pedestrian spawn failed")
        owned.append(pedestrian)
        cameras = {}
        for spec in scene["cameras"]:
            bp = library.find("sensor.camera.rgb")
            bp.set_attribute("image_size_x", str(spec["size"][0]))
            bp.set_attribute("image_size_y", str(spec["size"][1]))
            bp.set_attribute("fov", "80")
            sensor = world.spawn_actor(bp, pose(carla, spec["xyz"], spec["pitch"]),
                                       attach_to=ego if spec.get("attach_to_ego") else None)
            if sensor is None:
                raise RuntimeError("Original camera spawn failed: " + spec["name"])
            owned.append(sensor)
            cameras[spec["name"]] = sensor
        if set(cameras) != CAMERAS:
            raise ValueError("Four original cameras missing")
        yield {"world": world, "ego": ego, "lead": lead, "pedestrian": pedestrian,
               "cameras": cameras, "map_opendrive": source,
               "crossing_authority_observed": False,
               "lead_stop_purpose_observed": False}
    finally:
        for actor in reversed(owned):
            actor.destroy()
        settings.synchronous_mode, settings.fixed_delta_seconds = prior_sync, prior_delta
        world.apply_settings(settings)
