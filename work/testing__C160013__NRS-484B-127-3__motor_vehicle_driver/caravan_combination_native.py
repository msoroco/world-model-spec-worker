"""CARLA-lazy spawn of a reviewed powerless drawn unit behind a caravan car.

The final Native capture must review the actual mesh and attachment behavior.
"""
import math
from contextlib import contextmanager


def _relative_transform(carla, row):
    if not isinstance(row, dict):
        raise ValueError("Reviewed drawn-unit relative transform required")
    values = {}
    for key in ("x", "y", "z", "yaw_deg"):
        value = row.get(key)
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("Finite drawn-unit relative transform required")
        values[key] = float(value)
    if values["x"] >= 0 or abs(values["y"]) > 1 or abs(values["yaw_deg"]) > 10:
        raise ValueError("Drawn unit must start behind aligned drawing vehicle")
    return carla.Transform(carla.Location(x=values["x"], y=values["y"], z=values["z"]),
                           carla.Rotation(yaw=values["yaw_deg"]))


@contextmanager
def spawn_drawn_unit(world, carla, drawing_actor, packet):
    """Spawn one reviewed unpowered prop as a rigid child of the drawing car."""
    if packet.get("drawn_unit_review_status") != "reviewed_native_drawn_unit":
        raise ValueError("Reviewed Native drawn unit required")
    blueprint_id = packet.get("blueprint_id")
    if not isinstance(blueprint_id, str) or not blueprint_id.startswith("static.prop."):
        raise ValueError("Powerless Native prop blueprint required")
    if packet.get("drawn_unit_has_motive_power") is not False:
        raise ValueError("Drawn unit must lack motive power")
    if not isinstance(packet.get("mesh_review_basis"), str) or not packet["mesh_review_basis"].strip():
        raise ValueError("Native drawn-unit mesh review required")
    relative = _relative_transform(carla, packet.get("relative_transform"))
    blueprint = world.get_blueprint_library().find(blueprint_id)
    unit = world.try_spawn_actor(blueprint, relative, attach_to=drawing_actor,
                                 attachment_type=carla.AttachmentType.Rigid)
    if unit is None:
        raise ValueError("Native drawn-unit spawn failed")
    try:
        if unit.id == drawing_actor.id or unit.type_id != blueprint_id:
            raise ValueError("Native drawn-unit identity mismatch")
        yield unit
    finally:
        unit.destroy()
