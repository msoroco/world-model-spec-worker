"""Owner-controlled Native tick loop for the exact straight-bicycle cases.

The caller supplies a CARLA world and adapters for the reviewed site, device,
motion, original readback and camera bytes. The loop records observed state;
no requested policy is promoted to a physical or legal finding.
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path


BASE = Path(__file__).resolve().parent


def _module(name):
    spec = importlib.util.spec_from_file_location("c111125_8d_" + name, BASE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def execute_case(*, world, authority_root, site, case_suffix, transform,
                 apply_device_policy, apply_motion, read_original, camera_pngs,
                 attempt_root, frame_count=900, diagnostic_fixture=False):
    """Run one owned actor and seal only a complete original attempt.

    ``read_original`` must return the post-tick actor, device, detector and
    participant readbacks. ``camera_pngs`` must return the four original camera
    frames for that same world frame. The owner retains world ownership.
    """
    trial = _module("signal_trial")
    capture = _module("native_capture")
    if not diagnostic_fixture and frame_count != 900:
        raise ValueError("original delivery requires exactly 900 observed frames")
    settings = world.get_settings()
    if settings.synchronous_mode is not True or not math.isclose(
            settings.fixed_delta_seconds, 0.05, abs_tol=1e-9):
        raise ValueError("Native world must use synchronized 20 Hz ticks")
    actor, binding = trial.spawn_case(world, site, Path(authority_root),
                                      case_suffix, transform, apply_device_policy)
    plan = binding["plan"]
    history = []

    def sample_tick(index):
        if history:
            last = history[-1]
            request = trial.control_step(plan, {
                **last,
                "complete_device_cycles": trial._complete_cycles(
                    [row["cross_signal"] for row in history]),
            })
        else:
            request = {"target": "hold_before_boundary", "requested_motion": False,
                       "requested_detector_suppression": plan["requested_detector_suppression"]}
        apply_motion(actor, request)
        world_frame = world.tick()
        snapshot = world.get_snapshot()
        row = read_original(index, actor, world_frame)
        if not isinstance(row, dict) or row.get("frame") != world_frame or snapshot.frame != world_frame:
            raise ValueError("original readback differs from Native world frame")
        stamp = row.get("timestamp_s")
        if not isinstance(stamp, (int, float)) or not math.isfinite(stamp) or abs(
                stamp - snapshot.timestamp.elapsed_seconds) > 1e-6:
            raise ValueError("original readback differs from Native world time")
        images = camera_pngs(index, world_frame)
        history.append(row)
        return row, images

    try:
        return capture.capture_saved(
            attempt_root=Path(attempt_root), authority_root=Path(authority_root),
            site=site, case_suffix=case_suffix, actor_id=actor.id,
            observed_blueprint_id=actor.type_id,
            policy_receipt=binding["policy_receipt"], sample_tick=sample_tick,
            native_exit_code=0, frame_count=frame_count,
            diagnostic_fixture=diagnostic_fixture)
    finally:
        actor.destroy()
