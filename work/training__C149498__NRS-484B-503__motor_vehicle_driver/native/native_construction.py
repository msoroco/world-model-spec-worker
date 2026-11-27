"""Lazy CARLA construction with original curb/sign readback and actor ownership."""

from contextlib import contextmanager
import xml.etree.ElementTree as ET

from .loading_scene import CAMERAS, validate


def transform(carla, xyz, pitch=0, yaw=0):
    return carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                           carla.Rotation(pitch=pitch, yaw=yaw, roll=0))


def checked_map(world, scene):
    source = world.get_map().to_opendrive()
    roads = {road.get("id"): road for road in ET.fromstring(source).findall("road")}
    road = roads.get("149498")
    if road is None or len(roads) != 1:
        raise ValueError("original one-way loading road differs")
    curb = road.find("objects/object")
    sign = road.find("signals/signal")
    if curb is None or curb.get("id") != scene["zone"]["object_id"] or curb.get("type") != "curb":
        raise ValueError("original marked passenger curb differs")
    if sign is None or sign.get("id") != scene["zone"]["sign_id"]:
        raise ValueError("original loading-zone sign differs")
    if not all(value in sign.get("name", "") for value in
               (scene["zone"]["hours_start"], scene["zone"]["hours_end"],
                scene["zone"]["time_zone"])):
        raise ValueError("original sign schedule differs")
    return source


@contextmanager
def constructed_scene(client, carla, scene):
    """Create scene actors and cameras; restore timing and destroy owned actors."""
    validate(scene)
    world = client.generate_opendrive_world(scene["road_opendrive"])
    source = checked_map(world, scene)
    settings = world.get_settings()
    old_sync = settings.synchronous_mode
    old_delta = settings.fixed_delta_seconds
    owned = []
    try:
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / scene["rate_hz"]
        world.apply_settings(settings)
        readback = world.get_settings()
        if not readback.synchronous_mode or abs(readback.fixed_delta_seconds - .05) > 1e-6:
            raise ValueError("original 20 Hz timing readback differs")
        library = world.get_blueprint_library()
        ego = world.try_spawn_actor(library.find(scene["ego"]["blueprint"]),
                                    transform(carla, scene["ego"]["start_xyz"],
                                              yaw=scene["ego"]["heading_deg"]))
        if ego is None:
            raise RuntimeError("original loading vehicle spawn failed")
        owned.append(ego)
        walkers = library.filter(scene["passenger"]["blueprint_filter"])
        if not walkers:
            raise RuntimeError("original passenger blueprint unavailable")
        passenger = world.try_spawn_actor(walkers[0],
                                          transform(carla, scene["passenger"]["start_xyz"]))
        if passenger is None:
            raise RuntimeError("original passenger spawn failed")
        owned.append(passenger)
        cameras = {}
        for spec in scene["cameras"]:
            blueprint = library.find("sensor.camera.rgb")
            blueprint.set_attribute("image_size_x", str(spec["size"][0]))
            blueprint.set_attribute("image_size_y", str(spec["size"][1]))
            blueprint.set_attribute("fov", "80")
            sensor = world.spawn_actor(
                blueprint, transform(carla, spec["xyz"], pitch=spec["pitch"], yaw=spec["yaw"]),
                attach_to=ego if spec.get("attach_to_ego") else None)
            if sensor is None:
                raise RuntimeError("original loading camera spawn failed: " + spec["name"])
            owned.append(sensor)
            cameras[spec["name"]] = sensor
        if set(cameras) != set(CAMERAS):
            raise ValueError("four original camera actors missing")
        yield {"world": world, "ego": ego, "passenger": passenger, "cameras": cameras,
               "map_opendrive": checked_map(world, scene),
               "occupant_count_observed": False,
               "regulatory_authority_observed": False}
    finally:
        for actor in reversed(owned):
            actor.destroy()
        settings.synchronous_mode = old_sync
        settings.fixed_delta_seconds = old_delta
        world.apply_settings(settings)
