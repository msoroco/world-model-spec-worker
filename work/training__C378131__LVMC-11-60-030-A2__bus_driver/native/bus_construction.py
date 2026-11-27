"""Lazy CARLA scene ownership and original map readback."""

from contextlib import contextmanager
import xml.etree.ElementTree as ET

from .bus_scene import CAMERAS, validate


def transform(carla, xyz, pitch=0, yaw=0):
    return carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                           carla.Rotation(pitch=pitch, yaw=yaw, roll=0))


def checked_map(world, scene):
    source = world.get_map().to_opendrive()
    roads = ET.fromstring(source).findall("road")
    if len(roads) != 1 or roads[0].get("id") != "378131":
        raise ValueError("original bus street differs")
    marker = roads[0].find("objects/object")
    if marker is None or marker.get("id") != scene["zone_id"]:
        raise ValueError("original loading marker differs")
    return source


@contextmanager
def constructed_scene(client, carla, scene):
    validate(scene)
    world = client.generate_opendrive_world(scene["road_opendrive"])
    source = checked_map(world, scene)
    settings = world.get_settings()
    old_sync, old_delta = settings.synchronous_mode, settings.fixed_delta_seconds
    owned = []
    try:
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        readback = world.get_settings()
        if not readback.synchronous_mode or abs(readback.fixed_delta_seconds - .05) > 1e-6:
            raise ValueError("20 Hz Native timing readback differs")
        library = world.get_blueprint_library()
        blueprint = library.find(scene["ego"]["blueprint"])
        if blueprint is None:
            raise RuntimeError("bus blueprint unavailable")
        if blueprint.has_attribute("role_name"):
            blueprint.set_attribute("role_name", "tour_bus_requested" if
                                    scene["vehicle_class_requested"] == "tour_bus" else
                                    "route_bus_requested")
        ego = world.try_spawn_actor(blueprint, transform(carla, scene["ego"]["start_xyz"],
                                                       yaw=scene["ego"]["heading_deg"]))
        if ego is None:
            raise RuntimeError("bus spawn failed")
        owned.append(ego)
        pedestrians = library.filter(scene["passenger"]["blueprint_filter"])
        if not pedestrians:
            raise RuntimeError("passenger blueprint unavailable")
        passenger = world.try_spawn_actor(pedestrians[0],
                                          transform(carla, scene["passenger"]["start_xyz"]))
        if passenger is None:
            raise RuntimeError("passenger spawn failed")
        owned.append(passenger)
        cameras = {}
        for spec in scene["cameras"]:
            camera_blueprint = library.find("sensor.camera.rgb")
            camera_blueprint.set_attribute("image_size_x", str(spec["size"][0]))
            camera_blueprint.set_attribute("image_size_y", str(spec["size"][1]))
            sensor = world.spawn_actor(
                camera_blueprint,
                transform(carla, spec["xyz"], pitch=spec["pitch"], yaw=spec["yaw"]),
                attach_to=ego if spec.get("attach_to_ego") else None)
            if sensor is None:
                raise RuntimeError("camera spawn failed: " + spec["name"])
            owned.append(sensor)
            cameras[spec["name"]] = sensor
        if set(cameras) != set(CAMERAS):
            raise ValueError("four camera actors missing")
        yield {"world": world, "ego": ego, "passenger": passenger,
               "cameras": cameras, "map_opendrive": checked_map(world, scene),
               "designation_authority_confirmed": False,
               "physical_loading_confirmed": False}
    finally:
        for actor in reversed(owned):
            actor.destroy()
        settings.synchronous_mode = old_sync
        settings.fixed_delta_seconds = old_delta
        world.apply_settings(settings)
