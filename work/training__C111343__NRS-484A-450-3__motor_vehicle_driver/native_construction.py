"""Lazy, source-checked CARLA construction for the exact yield-crosswalk pair.

Requests are engineering targets. Map readback and actor creation are required
before capture; neither establishes that stopping is required for safety.
"""

from contextlib import contextmanager
import xml.etree.ElementTree as ET

from yield_crosswalk_scene import CAMERAS, validate


def transform(carla, xyz, pitch=0, yaw=0):
    return carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                           carla.Rotation(pitch=pitch, yaw=yaw, roll=0))


def checked_map(world, scene):
    source = world.get_map().to_opendrive()
    roads = {road.get("id"): road for road in ET.fromstring(source).findall("road")}
    if not {"111343", "111344"} <= set(roads):
        raise ValueError("Original map lacks the two crossing roads")
    approach = roads["111343"]
    signs = approach.findall("signals/signal")
    sign = next((item for item in signs if item.get("id") == "yield-111343"), None)
    if (sign is None or sign.get("name") != "YIELD" or sign.get("orientation") != "+"
            or abs(float(sign.get("s", -1)) - 70) > .01):
        raise ValueError("Original governing YIELD sign differs")
    markings = approach.findall("objects/object")
    kind = scene["reference_kind"]
    expected = {"crosswalk": ("near-crosswalk-111343", "crosswalk"),
                "stop_line": ("marked-stop-line-111343", "stopLine"),
                "viewpoint": ("sight-obstruction-111343", "building")}[kind]
    if (len(markings) != 1 or markings[0].get("id") != expected[0] or
            markings[0].get("type") != expected[1] or
            abs(float(markings[0].get("s", -1)) - (72 if kind == "viewpoint" else 74)) > .01):
        raise ValueError("Original stopping-reference map hierarchy differs")
    return source


@contextmanager
def constructed_scene(client, carla, scene):
    """Own all created actors and restore world timing on exit."""
    validate(scene)
    world = client.generate_opendrive_world(scene["road_opendrive"])
    checked_map(world, scene)
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
            raise ValueError("Original 20 Hz timing readback differs")
        library = world.get_blueprint_library()
        vehicles = {}
        for key, spec in (("ego", scene["ego"]),
                          ("intersecting", scene["intersecting_vehicle"])):
            actor = world.try_spawn_actor(library.find(spec["blueprint"]),
                                          transform(carla, spec["start_xyz"], yaw=spec["heading_deg"]))
            if actor is None:
                raise RuntimeError("Original vehicle spawn failed: " + key)
            owned.append(actor)
            vehicles[key] = actor
        cameras = {}
        for spec in scene["cameras"]:
            blueprint = library.find("sensor.camera.rgb")
            blueprint.set_attribute("image_size_x", str(spec["size"][0]))
            blueprint.set_attribute("image_size_y", str(spec["size"][1]))
            blueprint.set_attribute("fov", "80")
            sensor = world.spawn_actor(
                blueprint, transform(carla, spec["xyz"], pitch=spec["pitch"], yaw=spec["yaw"]),
                attach_to=vehicles["ego"] if spec.get("attach_to_ego") else None)
            if sensor is None:
                raise RuntimeError("Original camera spawn failed: " + spec["name"])
            owned.append(sensor)
            cameras[spec["name"]] = sensor
        if set(cameras) != CAMERAS:
            raise ValueError("Four source camera actors missing")
        yield {"world": world, "ego": vehicles["ego"],
               "intersecting": vehicles["intersecting"], "cameras": cameras,
               "map_opendrive": checked_map(world, scene)}
    finally:
        for actor in reversed(owned):
            actor.destroy()
        settings.synchronous_mode = old_sync
        settings.fixed_delta_seconds = old_delta
        world.apply_settings(settings)
