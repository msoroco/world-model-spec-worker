"""Candidate opposite-turn capture loop for CPU and future Native site binding.

The caller supplies a frame-aligned camera collector and source writer. This
module does not mark a candidate site reviewed or create accepted media.
"""

import math

from camera_setup import SIZES
from opposite_turn_construction import (construct_opposite_turn_pair,
                                        command_opposite_turn_pair)


def run_candidate_opposite_turn(world, carla, site, turning_role, blueprints,
                                transforms, release_frames, target_speeds_mps,
                                frames, collect_camera_frames, write_source):
    """Apply paired controls and retain one original source record per tick."""
    if type(frames) is not int or not 1 <= frames <= 1100:
        raise ValueError("Bounded positive capture frame count required")
    if not callable(collect_camera_frames) or not callable(write_source):
        raise ValueError("Four-camera collector and source writer required")
    progress = {"ego": 1, "other": 1}
    frame_ids = []
    with construct_opposite_turn_pair(world, blueprints, transforms,
                                      site, turning_role) as built:
        actors = built["actors"]
        for index in range(frames):
            command = command_opposite_turn_pair(
                carla, actors, site, progress, index, release_frames,
                target_speeds_mps, turning_role)
            native_frame = world.tick()
            if type(native_frame) is not int or (frame_ids and native_frame <= frame_ids[-1]):
                raise ValueError("Increasing original Native frame IDs required")
            cameras = collect_camera_frames(native_frame)
            if not isinstance(cameras, dict) or set(cameras) != set(SIZES) or any(
                    type(frame) is not int or frame != native_frame
                    for frame in cameras.values()):
                raise ValueError("All four camera sources must join original Native frame")
            bodies = {}
            for role, actor in actors.items():
                pose = actor.get_transform()
                velocity = actor.get_velocity()
                values = [float(pose.location.x), float(pose.location.y),
                          float(pose.rotation.yaw), float(velocity.x),
                          float(velocity.y), float(velocity.z)]
                if not all(math.isfinite(value) for value in values):
                    raise ValueError("Finite original actor pose and velocity required")
                bodies[role] = {"xy_yaw": values[:3], "velocity_xyz": values[3:]}
            write_source({"native_frame": native_frame,
                          "frame_index": index,
                          "turning_role": turning_role,
                          "camera_source_frames": cameras,
                          "actor_sources": bodies,
                          "applied_decisions": command["decisions"],
                          "physical_or_legal_acceptance_claimed": False})
            frame_ids.append(native_frame)
    return {"frames_recorded": len(frame_ids),
            "first_native_frame": frame_ids[0],
            "last_native_frame": frame_ids[-1],
            "physical_or_legal_acceptance_claimed": False}
