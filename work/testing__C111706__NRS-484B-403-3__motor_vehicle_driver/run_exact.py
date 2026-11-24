"""Owned CARLA lifecycle for one source-reviewed exact U-turn case.

The caller supplies original spawn/camera transforms and a sensor builder. No
map geometry, business-district classification, or physical success is inferred.
"""
from __future__ import annotations

from copy import copy
from pathlib import Path
import sys

from capture_cameras import OriginalCameraCollector, VIEWS
from capture_uturn import capture
from construct import construct, load_site
from control_uturn import RouteFollower, TimedOtherVehicle


def run_exact(world, *, site_path: Path, site_sha256: str, case_id: str,
              ego_spawn, other_spawn, camera_builder, output: Path,
              control_factory, capture_fn=capture) -> dict:
    """Run one exact case and restore world/owned actors even on readback failure.

    ``camera_builder(world, actors, site)`` must return four named CARLA sensor
    actors already configured to the declared dimensions. All source selection
    and physical review happen before this function is invoked.
    """
    site = load_site(site_path, site_sha256, expected_case=case_id)
    if not callable(camera_builder) or not callable(control_factory):
        raise ValueError("camera and control factories required")
    if not site.get("route_sha256") or not site.get("intersection_boundary", {}).get("source_sha256"):
        raise ValueError("original route and boundary sources required")
    if not isinstance(output, Path) or output.exists():
        raise ValueError("new exact Native output path required")
    original_settings = copy(world.get_settings())
    owned = None
    sensors = {}
    try:
        settings = copy(original_settings)
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        owned = construct(world, site, ego_spawn=ego_spawn, other_spawn=other_spawn)
        sensors = camera_builder(world, owned, site)
        if set(sensors) != set(VIEWS) or len({sensor.id for sensor in sensors.values()}) != 4:
            raise ValueError("four distinct original camera actors required")
        camera_root = output.parent / "camera-originals"
        if camera_root.exists():
            raise ValueError("new camera-originals directory required")
        collector = OriginalCameraCollector(camera_root, sensors)
        ego_control = RouteFollower(owned["ego_route"], control_factory)
        other_follow = RouteFollower(owned["other_route"], control_factory)
        other_control = TimedOtherVehicle(other_follow, site["other_start_tick"])
        def brake(actor):
            actor.apply_control(control_factory(throttle=0.0, steer=0.0, brake=1.0))
        receipt = capture_fn(world, owned["ego"], owned["other_vehicle"],
                             site_path, site_sha256, case_id, output,
                             ego_control, other_control, brake,
                             ticks=900, step_s=0.05, camera_collector=collector)
        return {**receipt, "camera_manifest": str(camera_root / "camera-manifest.json")}
    finally:
        cleanup_errors = []
        for sensor in sensors.values():
            for method in (sensor.stop, sensor.destroy):
                try:
                    method()
                except Exception as exc:
                    cleanup_errors.append(exc)
        if owned is not None:
            for actor in (owned["other_vehicle"], owned["ego"]):
                try:
                    actor.apply_control(control_factory(throttle=0.0, steer=0.0, brake=1.0))
                except Exception as exc:
                    cleanup_errors.append(exc)
                try:
                    actor.destroy()
                except Exception as exc:
                    cleanup_errors.append(exc)
        try:
            world.apply_settings(original_settings)
        except Exception as exc:
            cleanup_errors.append(exc)
        if cleanup_errors and sys.exc_info()[0] is None:
            raise RuntimeError("exact-case cleanup failed") from cleanup_errors[0]
