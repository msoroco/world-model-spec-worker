"""Lazy Native actor construction for hand indication and officer direction."""


def _arm_pose(carla, side):
    if side not in ("L", "R"):
        raise ValueError("Only modeled left or right hand may be requested")
    sign = 1 if side == "R" else -1
    rotations = (("shoulder", -45 * sign), ("arm", -55 * sign),
                 ("foreArm", -35 * sign), ("hand", 0))
    return [(f"crl_{name}__{side}", carla.Transform(rotation=carla.Rotation(
             pitch=0, yaw=90 if name == "hand" else 0, roll=roll)))
            for name, roll in rotations]


def apply_indication(carla, walker, side):
    """Request an arm signal and require original Native bone readback."""
    poses = _arm_pose(carla, side)
    if not all(hasattr(walker, name) for name in ("set_bones", "show_pose", "get_bones")):
        raise ValueError("Native walker bone pose/readback API unavailable")
    if not hasattr(carla, "WalkerBoneControlIn"):
        raise ValueError("Native WalkerBoneControlIn API unavailable")
    walker.set_bones(carla.WalkerBoneControlIn(poses))
    walker.show_pose()
    rows = walker.get_bones().bone_transforms
    observed = {row.name if hasattr(row, "name") else row[0] for row in rows}
    required = {name for name, _ in poses}
    if not required <= observed:
        raise ValueError("Requested indication bones absent in Native readback")
    return {"requested_bones": sorted(required), "native_bones_read_back": True,
            "original_pixel_visibility_verified": False,
            "source_identity_verified": False}


def spawn_indication_actor(carla, world, blueprint, xyz_m, source_vehicle=None):
    """Spawn a reviewable walker beside the source vehicle or at the officer post."""
    if not blueprint.startswith("walker.pedestrian."):
        raise ValueError("Indication actor requires walker skeleton")
    if len(xyz_m) != 3 or not all(isinstance(value, (int, float)) for value in xyz_m):
        raise ValueError("Indication actor needs exact three-dimensional spawn")
    if source_vehicle is not None:
        origin = source_vehicle.get_location()
        if abs(xyz_m[0] - origin.x) > 3 or abs(-xyz_m[1] - origin.y) > 5:
            raise ValueError("Source-driver proxy is not beside source vehicle")
    actor = world.try_spawn_actor(world.get_blueprint_library().find(blueprint),
                                  carla.Transform(carla.Location(x=xyz_m[0], y=-xyz_m[1],
                                                                 z=xyz_m[2])))
    if actor is None:
        raise RuntimeError("Indication actor Native spawn failed")
    return actor
