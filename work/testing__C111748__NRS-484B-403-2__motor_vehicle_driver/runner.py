"""Local CARLA adapter boundary for one exact device-duty case.

The caller supplies transforms, synchronized camera readbacks and a CARLA
VehicleControl factory. Importing this module never imports CARLA or ticks a world.
"""
from __future__ import annotations
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def module(name):
    spec = importlib.util.spec_from_file_location("device_runner_" + name, ROOT / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

construction = module("construct")
map_guard = module("native_map")
policy = module("control_policy")
capture = module("native_capture")


class RunnerError(ValueError):
    pass


def run(world, site_path: Path, site_sha256: str, case_id: str, output: Path,
        *, ego_transform, device_transform, camera_sample, control_factory,
        snapshot_world, restore_world, frames: int = capture.DELIVERY_FRAMES,
        diagnostic: bool = False) -> dict:
    """Run with resource ownership, brake and world restore on every exit."""
    if not all(callable(x) for x in (camera_sample, control_factory, snapshot_world, restore_world)):
        raise RunnerError("local adapter callbacks missing")
    binding = map_guard.verify(world, site_path, site_sha256, case_id)
    site = construction.load_site(site_path, site_sha256, case_id)
    state = snapshot_world(world)
    actors = None
    last = None
    first_visible = None
    try:
        actors = construction.construct(world, site, ego_transform=ego_transform,
                                        device_transform=device_transform)
        ego_actor = actors["ego"]

        def brake():
            ego_actor.apply_control(control_factory({"throttle": 0.0, "brake": 1.0,
                                                     "steer": 0.0}))

        def apply_control(i, source_site):
            if last is None:
                brake()
                return
            command = policy.command(case_id, source_site, last["ego"],
                                     last["device_readback"],
                                     first_visible_frame=first_visible,
                                     original_frame=last["frame"] + 1)
            ego_actor.apply_control(control_factory(command))

        def tick():
            frame = world.tick()
            snap = world.get_snapshot()
            if snap.frame != frame:
                raise RunnerError("world snapshot frame mismatch")
            return frame, snap.timestamp.elapsed_seconds

        def sample(frame):
            nonlocal last, first_visible
            row = camera_sample(world, actors, frame, site)
            if not isinstance(row, dict):
                raise RunnerError("camera and actor sample missing")
            last = dict(row)
            last["frame"] = frame
            observed = row.get("device_readback", {})
            ego = row.get("ego", {})
            if (observed.get("visible_to_ego") is True and
                    ego.get("approach_id") == site["device"]["governed_approach"] and
                    first_visible is None):
                first_visible = frame
            return row

        result = capture.capture(site_path, site_sha256, case_id, output,
                                 tick=tick, apply_control=apply_control,
                                 sample=sample, brake=brake, frames=frames,
                                 diagnostic=diagnostic)
        result["map_binding"] = binding
        return result
    finally:
        try:
            if actors is not None:
                try:
                    actors["ego"].apply_control(control_factory({"throttle": 0.0,
                                                                "brake": 1.0, "steer": 0.0}))
                finally:
                    try:
                        actors["device"].destroy()
                    finally:
                        actors["ego"].destroy()
        finally:
            restore_world(world, state)
