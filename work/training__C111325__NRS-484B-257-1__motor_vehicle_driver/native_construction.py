"""Lazy CARLA construction for a dedicated local server; no capture verdict."""

from contextlib import contextmanager
import xml.etree.ElementTree as ET

from stop_yield_scene import validate


def transform(carla, xyz, pitch=0, yaw=0):
    return carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                           carla.Rotation(pitch=pitch, yaw=yaw, roll=0))


def original_map_check(world, scene):
    xodr = world.get_map().to_opendrive()
    root = ET.fromstring(xodr)
    roads = {road.attrib.get("id"): road for road in root.findall("road")}
    if not {"111325", "111326"} <= set(roads):
        raise ValueError("CARLA map omitted authored crossing roads")
    signs = roads["111325"].findall("signals/signal")
    governing = next((s for s in signs if s.attrib.get("id") == scene["governing_sign"]), None)
    if governing is None:
        raise ValueError("CARLA map omitted governing sign")
    if (abs(float(governing.attrib.get("s", -100)) - 74) > .01 or
            abs(float(governing.attrib.get("t", -100)) + 3.7) > .01 or
            governing.attrib.get("orientation") != "+"):
        raise ValueError("CARLA map changed governing sign station or approach orientation")
    reference = scene["stopping_reference"]
    objects = roads["111325"].findall("objects/object")
    expected = "marked-stop-line" if reference == "stop_line" else "near-side-crosswalk" if reference == "crosswalk" else None
    marked = next((obj for obj in objects if obj.attrib.get("name") == expected), None)
    if expected and marked is None:
        raise ValueError("CARLA map omitted required stopping reference")
    if marked is not None:
        station = 74 if reference == "stop_line" else 75
        if (abs(float(marked.attrib.get("s", -100)) - station) > .01 or
                abs(float(marked.attrib.get("width", -1)) - 7) > .01):
            raise ValueError("CARLA map changed stopping-reference geometry")
    if reference == "nearest_viewpoint" and any(obj.attrib.get("name") in {"marked-stop-line", "near-side-crosswalk"} for obj in objects):
        raise ValueError("CARLA map retained an excluded stopping reference")
    if scene["signal_controlling"]:
        signal = next((s for s in signs if s.attrib.get("id") == "traffic-signal-111325"), None)
        if signal is None:
            raise ValueError("CARLA map omitted controlling traffic signal")
        if signal.attrib.get("dynamic") != "yes" or abs(float(signal.attrib.get("s", -100)) - 75) > .01:
            raise ValueError("CARLA map changed controlling signal geometry")
    return xodr


@contextmanager
def constructed_scene(client, carla, scene):
    """Build and clean owned actors/settings; caller owns the dedicated server."""
    validate(scene)
    world = client.generate_opendrive_world(scene["road_opendrive"])
    original_map_check(world, scene)
    settings = world.get_settings()
    old_sync = settings.synchronous_mode
    old_delta = settings.fixed_delta_seconds
    owned = []
    try:
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / scene["rate_hz"]
        world.apply_settings(settings)
        if not world.get_settings().synchronous_mode or abs(world.get_settings().fixed_delta_seconds - .05) > 1e-6:
            raise ValueError("CARLA synchronous 20 Hz settings readback differs")
        library = world.get_blueprint_library()
        ego_spec = scene["ego"]
        ego = world.try_spawn_actor(library.find(ego_spec["blueprint"]),
                                    transform(carla, ego_spec["start_xyz"], yaw=ego_spec["heading_deg"]))
        if ego is None:
            raise RuntimeError("CARLA subject spawn failed")
        owned.append(ego)
        through_spec = scene["through_vehicle"]
        through = world.try_spawn_actor(library.find(through_spec["blueprint"]),
                                        transform(carla, through_spec["start_xyz"], yaw=through_spec["heading_deg"]))
        if through is None:
            raise RuntimeError("CARLA through-highway vehicle spawn failed")
        owned.append(through)
        officer = None
        if scene["police_controlling"]:
            spec = scene["police_actor_request"]
            matches = library.filter(spec["blueprint_filter"])
            if not matches:
                raise ValueError("No reviewed officer actor blueprint available")
            officer = world.try_spawn_actor(matches[0], transform(carla, spec["xyz"]))
            if officer is None:
                raise RuntimeError("CARLA officer actor spawn failed")
            owned.append(officer)
        cameras = {}
        for spec in scene["cameras"]:
            camera = library.find("sensor.camera.rgb")
            camera.set_attribute("image_size_x", str(spec["width"]))
            camera.set_attribute("image_size_y", str(spec["height"]))
            camera.set_attribute("fov", str(spec["fov_deg"]))
            pose = transform(carla, spec["xyz"], pitch=spec["pitch"], yaw=spec["yaw"])
            sensor = world.spawn_actor(camera, pose, attach_to=ego) if spec.get("attach_to_ego") else world.spawn_actor(camera, pose)
            if sensor is None:
                raise RuntimeError("CARLA source camera spawn failed: " + spec["name"])
            owned.append(sensor)
            cameras[spec["name"]] = sensor
        if set(cameras) != {"overview", "approach", "reference_corner", "driver_reference"}:
            raise ValueError("Four source cameras not constructed")
        yield {"world": world, "ego": ego, "through": through, "officer": officer,
               "cameras": cameras, "map_opendrive": original_map_check(world, scene),
               "prior_synchronous_mode": old_sync, "prior_fixed_delta_seconds": old_delta}
    finally:
        for actor in reversed(owned):
            actor.destroy()
        settings.synchronous_mode = old_sync
        settings.fixed_delta_seconds = old_delta
        world.apply_settings(settings)
