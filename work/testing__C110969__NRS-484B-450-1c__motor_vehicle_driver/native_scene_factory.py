"""Run a reviewed intersection route with four original Native cameras.

The route and camera placement packets are independently reviewed inputs. This
module creates actors and records original samples; it makes no legal finding.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from intersection_observables import _require
from native_acquisition import acquire
from native_camera_adapter import NativeCameraAdapter
from native_media import CAMERAS, NativeMediaWriter
from native_scene import DestinationController, validate_route


def _pose(carla, values):
    _require(all(key in values for key in ("x", "y", "z", "yaw_deg")),
             "reviewed Native pose incomplete")
    return carla.Transform(
        carla.Location(x=float(values["x"]), y=float(values["y"]), z=float(values["z"])),
        carla.Rotation(yaw=float(values["yaw_deg"]),
                       pitch=float(values.get("pitch_deg", 0)),
                       roll=float(values.get("roll_deg", 0))))


def validate_camera_packet(packet, route, boundary):
    _require(packet.get("map_id") == boundary.get("map_id") == route.get("map_id"),
             "camera packet map identity differs")
    _require(packet.get("case_id") == route.get("case_id") and packet.get("source_refs") and
             packet.get("placement_reviewed") is True,
             "reviewed exact camera placement packet missing")
    cameras = packet.get("cameras")
    _require(isinstance(cameras, dict) and set(cameras) == set(CAMERAS),
             "four reviewed camera poses required")
    for name, spec in cameras.items():
        _require(spec.get("pose") and spec.get("attach_to") in ("ego", "world") and
                 isinstance(spec.get("fov_deg"), (int, float)) and 1 <= spec["fov_deg"] < 180 and
                 spec.get("source_refs"), "reviewed camera placement incomplete: " + name)
    return cameras


def run_native(world, carla, route, boundary, camera_packet, observer, case_id,
               run_id, output, sample_count=900):
    """Create the exact scene and retain original camera/trace source packets."""
    _require(route.get("case_id") == case_id, "route case identity differs")
    validate_route(route, boundary, case_id)
    cameras = validate_camera_packet(camera_packet, route, boundary)
    _require(world.get_map().name == boundary["map_id"], "live Native map differs")
    _require(observer is not None and callable(getattr(observer, "observe", None)),
             "independent original activity observer required")
    original_settings = world.get_settings()
    actors = []
    adapter = None
    writer = None
    try:
        settings = copy.copy(original_settings)
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        library = world.get_blueprint_library()
        vehicle_blueprint = library.find(route["vehicle_blueprint"])
        _require(vehicle_blueprint is not None, "reviewed vehicle blueprint missing")
        ego = world.spawn_actor(vehicle_blueprint, _pose(carla, route["spawn"]))
        _require(ego is not None, "Native vehicle spawn failed")
        actors.append(ego)
        sensors = {}
        for name, (width, height) in CAMERAS.items():
            spec = cameras[name]
            blueprint = library.find("sensor.camera.rgb")
            _require(blueprint is not None, "Native RGB blueprint missing")
            blueprint.set_attribute("image_size_x", str(width))
            blueprint.set_attribute("image_size_y", str(height))
            blueprint.set_attribute("fov", str(spec["fov_deg"]))
            sensor = world.spawn_actor(blueprint, _pose(carla, spec["pose"]),
                                       attach_to=ego if spec["attach_to"] == "ego" else None)
            _require(sensor is not None, "Native camera spawn failed: " + name)
            actors.append(sensor)
            sensors[name] = sensor
        adapter = NativeCameraAdapter(sensors)
        writer = NativeMediaWriter(Path(output), adapter)
        controller = DestinationController(
            route, boundary, case_id, carla.VehicleControl)
        return acquire(world, ego, boundary, controller, observer, case_id, run_id,
                       Path(output), sample_count=sample_count, media_writer=writer)
    except BaseException:
        if writer is not None:
            writer.abort()
        raise
    finally:
        if adapter is not None:
            adapter.close()
        for actor in reversed(actors):
            actor.destroy()
        world.apply_settings(original_settings)


def run_from_packets(world, carla, route_path, boundary_path, camera_path,
                     observer, case_id, run_id, output, sample_count=900):
    """Load only explicit reviewed source packets; never derive them from case names."""
    paths = [Path(route_path), Path(boundary_path), Path(camera_path)]
    packets = [json.loads(path.read_text()) for path in paths]
    return run_native(world, carla, *packets, observer, case_id, run_id,
                      output, sample_count=sample_count)
