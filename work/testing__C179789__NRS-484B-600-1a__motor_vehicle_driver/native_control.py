"""Sustained, common Native speed control for the exact condition comparisons.

The controller acts on current measured speed and clearance every 20 Hz frame.
Its gains and safety envelope are engineering controls, never legal thresholds.
"""

from __future__ import annotations

import math


def _speed(actor):
    velocity = actor.get_velocity()
    values = (velocity.x, velocity.y, velocity.z)
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or
           not math.isfinite(value) for value in values):
        raise ValueError("Native actor velocity is invalid")
    return math.sqrt(sum(value * value for value in values))


def _control(error, control_factory):
    # One shared policy; request values alone differ among the seven cases.
    if error >= 0:
        return control_factory(throttle=min(.65, .12 + .18 * error), brake=0.0, steer=0.0)
    return control_factory(throttle=0.0, brake=min(.75, -.22 * error), steer=0.0)


def _values(control):
    return {name: float(control[name] if isinstance(control, dict) else getattr(control, name))
            for name in ("throttle", "brake", "steer")}


def step(scene, condition_sample: dict, control_factory) -> dict:
    """Apply one control to each actor after a source-joined Native sample."""
    if condition_sample.get("source_ids", {}).get("ego_actor_id") != scene.ego.id or \
            condition_sample.get("source_ids", {}).get("leader_actor_id") != scene.leader.id:
        raise ValueError("controller observation actor IDs differ")
    measured_ego = condition_sample.get("ego_speed_mps")
    gap = condition_sample.get("leader_gap_m")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or
           not math.isfinite(value) or value < 0 for value in (measured_ego, gap)):
        raise ValueError("controller speed or clearance observation invalid")
    leader_speed = _speed(scene.leader)
    ego_target = scene.targets["ego_speed_mps"]
    leader_target = scene.targets["leader_speed_mps"]
    for value in (ego_target, leader_target):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError("controller target speed invalid")
    ego_control = _control(ego_target - measured_ego, control_factory)
    if gap < max(4.0, measured_ego * 1.2):
        ego_control = control_factory(throttle=0.0, brake=1.0, steer=0.0)
    leader_control = _control(leader_target - leader_speed, control_factory)
    scene.ego.apply_control(ego_control)
    scene.leader.apply_control(leader_control)
    return {"frame": condition_sample["frame"],
            "source_frame": condition_sample["source_frame"],
            "ego_target_speed_mps": ego_target,
            "leader_target_speed_mps": leader_target,
            "ego_measured_speed_mps": measured_ego,
            "leader_measured_speed_mps": leader_speed,
            "leader_gap_m": gap,
            "ego_control": _values(ego_control),
            "leader_control": _values(leader_control),
            "legal_judgment": "unresolved", "physical_acceptance_claimed": False}
