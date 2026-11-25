"""Local CARLA adapter boundary for one exact device-duty case.

The caller supplies transforms, synchronized camera readbacks and a CARLA
VehicleControl factory. Importing this module never imports CARLA or ticks a world.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
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
site_review = module("site_review")


class RunnerError(ValueError):
    pass


def check_bundle() -> str:
    """Validate exact selected-case files without importing or contacting CARLA."""
    config = json.loads((ROOT / "config.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    case_id = config.get("selected_case_id")
    if (config.get("assignment_id") != plan.get("assignment_id") or
            config.get("law_id") != plan.get("law_id") or
            config.get("cell_id") != plan.get("cell_id") or
            config.get("actor") != plan.get("actor") or
            case_id not in {case["case_id"] for case in plan["cases"]} or
            config.get("supported_case_ids") != [case["case_id"] for case in plan["cases"]]):
        raise RunnerError("exact selected case identity changed")
    if config.get("rate_hz") != 20 or config.get("duration_s") != 45 or config.get("frame_count") != 900:
        raise RunnerError("900-frame capture contract changed")
    cameras = config.get("cameras", [])
    expected = (("overview", 1920, 1080), ("approach", 1280, 720),
                ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))
    if [(camera.get("name"), camera.get("width"), camera.get("height"))
            for camera in cameras] != list(expected):
        raise RunnerError("four-camera capture profile changed")
    selected = next(case for case in plan["cases"] if case["case_id"] == case_id)
    expected_prohibition = selected["scenario_parameters"]["device_prohibits_u_turn"]
    expected_turn = selected["scenario_parameters"]["driver_turn_target"]
    if config.get("case") != {"case_id": case_id,
                              "device_prohibits_u_turn": expected_prohibition,
                              "driver_turn_target": expected_turn}:
        raise RunnerError("selected device/action construction changed")
    return case_id


def run(world, site_path: Path, site_sha256: str, case_id: str, output: Path,
        *, ego_transform, device_transform, camera_sample, control_factory,
        snapshot_world, restore_world, frames: int = capture.DELIVERY_FRAMES,
        diagnostic: bool = False, review_path: Path | None = None,
        review_source_root: Path | None = None) -> dict:
    """Run with resource ownership, brake and world restore on every exit."""
    if not all(callable(x) for x in (camera_sample, control_factory, snapshot_world, restore_world)):
        raise RunnerError("local adapter callbacks missing")
    if not diagnostic:
        if review_path is None or review_source_root is None:
            raise RunnerError("original reviewed site packet required")
        reviewed = site_review.verify(site_path, site_sha256, case_id,
                                      review_path, review_source_root)
    else:
        reviewed = None
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
                                 diagnostic=diagnostic, review_binding=reviewed)
        result["map_binding"] = binding
        result["site_review_binding"] = reviewed
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    selected = check_bundle()
    if args.check:
        print("exact device-duty bundle passed: " + selected)
        return
    raise RunnerError("local CARLA adapter and original reviewed source packet required")


if __name__ == "__main__":
    main()
