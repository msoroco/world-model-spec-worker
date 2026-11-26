"""Prospective CARLA driver hand-pose rig for a visible preparing indication.

The pose request is an engineering control, not proof that the driver is inside
the vehicle or that an approaching driver can see the signal. Both need original
four-view pixel review bound to actor IDs and frame times.
"""
import math


BONES = ("crl_arm__L", "crl_foreArm__L", "crl_hand__L")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def check_survey(survey):
    require(survey.get("source_kind") == "original_native_site_survey",
            "Original hand-signal site survey required")
    require(survey.get("driver_blueprint")
            and len(survey.get("driver_spawn_xyz_yaw_deg", ())) == 4
            and survey.get("driver_vehicle_identity_source_id")
            and survey.get("hand_signal_pose_source_id")
            and survey.get("driver_window_visibility_source_id"),
            "Original driver and hand-pose sources required")
    pose = survey["driver_spawn_xyz_yaw_deg"]
    require(all(type(v) in (int, float) and math.isfinite(v) for v in pose),
            "Finite surveyed driver pose required")
    return {"source_bound": True, "driver_pose": pose,
            "physical_visibility_claimed": False}


def spawn(world, carla, survey):
    check_survey(survey)
    blueprint = world.get_blueprint_library().find(survey["driver_blueprint"])
    require(blueprint is not None and survey["driver_blueprint"].startswith("walker.pedestrian."),
            "CARLA walker driver blueprint required")
    x, y, z, yaw = survey["driver_spawn_xyz_yaw_deg"]
    pose = carla.Transform(carla.Location(x=x, y=y, z=z), carla.Rotation(yaw=yaw))
    actor = world.try_spawn_actor(blueprint, pose)
    require(actor is not None and actor.id, "Surveyed driver spawn unavailable")
    require(callable(getattr(actor, "apply_control", None)),
            "Driver actor cannot receive a skeletal hand pose")
    return actor


def request_hand_signal(actor, carla, *, active):
    require(actor is not None and callable(getattr(actor, "apply_control", None)),
            "Missing driver actor for hand signal")
    if not active:
        if callable(getattr(actor, "hide_pose", None)):
            actor.hide_pose()
        return {"pose_requested": False, "visible_to_subject_confirmed": False}
    require(hasattr(carla, "WalkerBoneControl"),
            "CARLA walker bone control unavailable")
    control = carla.WalkerBoneControl()
    control.bone_transforms = [
        (BONES[0], carla.Transform(rotation=carla.Rotation(pitch=-25, roll=40))),
        (BONES[1], carla.Transform(rotation=carla.Rotation(pitch=-65, roll=10))),
        (BONES[2], carla.Transform(rotation=carla.Rotation(roll=90))),
    ]
    actor.apply_control(control)
    if callable(getattr(actor, "show_pose", None)):
        actor.show_pose()
    return {"pose_requested": True, "driver_actor_id": actor.id,
            "bone_names": list(BONES), "visible_to_subject_confirmed": False}
