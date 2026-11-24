"""Per-frame officer direction program for the exact exception comparisons.

The caller supplies a Native bone-pose adapter reviewed for the selected walker.
The adapter must move the visible arm bones and report the realized pose. A
programmed direction is never substituted for an original-camera observation.
"""

from dataclasses import dataclass
import math


SUFFIXES = (
    "officer_active_stop_then_go",
    "officer_active_hold",
    "officer_present_inactive",
    "no_officer_yield_nearest_view",
)
PREFIX = "testing__C157964__NRS-484B-257-1__motor_vehicle_driver__"


@dataclass(frozen=True)
class DirectionPhase:
    start_frame: int
    end_frame: int
    direction: str


def phases(case_id: str, frames: int = 600) -> tuple[DirectionPhase, ...]:
    if type(frames) is not int or frames < 3:
        raise ValueError("Officer program needs a complete 20 Hz capture")
    suffix = case_id[len(PREFIX):] if isinstance(case_id, str) and case_id.startswith(PREFIX) else None
    if suffix not in SUFFIXES:
        raise ValueError("Unknown exact officer case")
    if suffix == "officer_active_stop_then_go":
        switch = frames // 2
        return (DirectionPhase(0, switch, "stop"),
                DirectionPhase(switch, frames, "go"))
    if suffix == "officer_active_hold":
        return (DirectionPhase(0, frames, "stop"),)
    return (DirectionPhase(0, frames, "none"),)


def apply_direction(actor, adapter, case_id: str, frame_index: int,
                    frames: int = 600) -> dict:
    """Apply an explicit visible-bone pose and retain its Native readback.

    ``adapter`` takes (actor, direction) and returns a source-shaped readback
    with the same actor ID, pose name and at least one realized bone transform.
    It must raise when the selected walker lacks the necessary Native API.
    """
    if type(frame_index) is not int or not 0 <= frame_index < frames:
        raise ValueError("Officer direction frame outside capture")
    direction = next(p.direction for p in phases(case_id, frames)
                     if p.start_frame <= frame_index < p.end_frame)
    if direction == "none":
        if actor is not None and type(getattr(actor, "id", None)) is not int:
            raise ValueError("Native officer identity missing")
        if case_id.endswith("__no_officer_yield_nearest_view") and actor is not None:
            raise ValueError("No-officer baseline contains an officer actor")
        if case_id.endswith("__officer_present_inactive") and actor is None:
            raise ValueError("Inactive-officer comparison lacks the officer actor")
        return {"frame_index": frame_index, "officer_actor_id": getattr(actor, "id", None),
                "programmed_direction": "none", "pose_applied": False}
    if actor is None or type(getattr(actor, "id", None)) is not int:
        raise ValueError("Native officer identity missing")
    if adapter is None:
        raise ValueError("Native visible-bone direction adapter missing")
    readback = adapter(actor, direction)
    if (not isinstance(readback, dict) or
            readback.get("officer_actor_id") != actor.id or
            readback.get("direction") != direction or
            not isinstance(readback.get("realized_bones"), dict) or
            not readback["realized_bones"]):
        raise ValueError("Native officer direction pose readback missing")
    return {"frame_index": frame_index, "officer_actor_id": actor.id,
            "programmed_direction": direction, "pose_applied": True,
            "realized_bones": readback["realized_bones"]}


def native_bone_adapter(carla, stop_pose: dict, go_pose: dict):
    """Create the Native walker adapter from reviewed, named arm rotations.

    Pose maps use walker bone names as keys and pitch/yaw/roll degrees as values.
    The selected walker must expose those bones; unsupported walkers fail before
    capture is sealed. Bone readback proves API application, not visible pixels.
    """
    poses = {"stop": stop_pose, "go": go_pose}
    if not all(isinstance(p, dict) and p for p in poses.values()):
        raise ValueError("Both visible-direction bone poses are required")
    for pose in poses.values():
        for name, angles in pose.items():
            if (not isinstance(name, str) or not name or not isinstance(angles, dict) or
                    set(angles) != {"pitch", "yaw", "roll"}):
                raise ValueError("Named officer arm bone rotation required")
            if any(type(value) not in (int, float) or not math.isfinite(value)
                   for value in angles.values()):
                raise ValueError("Officer bone rotation must be finite")

    def bone_parts(entry):
        if hasattr(entry, "name") and hasattr(entry, "relative"):
            return entry.name, entry.relative
        if isinstance(entry, (tuple, list)) and len(entry) >= 3:
            return entry[0], entry[2]
        raise ValueError("Unsupported Native walker bone readback shape")

    def apply(actor, direction):
        if direction not in poses:
            raise ValueError("Unsupported officer direction")
        original = actor.get_bones()
        available = {bone_parts(entry)[0] for entry in original.bone_transforms}
        missing = set(poses[direction]) - available
        if missing:
            raise ValueError("Selected walker lacks officer arm bones: " + ", ".join(sorted(missing)))
        updates = [(name, carla.Transform(rotation=carla.Rotation(**angles)))
                   for name, angles in poses[direction].items()]
        actor.set_bones(carla.WalkerBoneControl(updates))
        actor.blend_pose(1.0)
        readback = {name: relative.rotation
                    for entry in actor.get_bones().bone_transforms
                    for name, relative in [bone_parts(entry)]
                    if name in poses[direction]}
        if set(readback) != set(poses[direction]):
            raise ValueError("Native officer arm-bone readback incomplete")
        realized = {name: {axis: float(getattr(rotation, axis))
                           for axis in ("pitch", "yaw", "roll")}
                    for name, rotation in readback.items()}
        for name, target in poses[direction].items():
            if any(not math.isfinite(realized[name][axis]) or
                   abs(realized[name][axis] - target[axis]) > 2.0
                   for axis in ("pitch", "yaw", "roll")):
                raise ValueError("Native officer arm-bone pose differs from command")
        return {"officer_actor_id": actor.id, "direction": direction,
                "realized_bones": realized}

    return apply
