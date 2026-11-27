"""Install and read back a requested elevated structure in original Native.

This helper never identifies a legal bridge or viaduct from an authored label.
It fails closed when the installed asset or the Native drivable deck differs.
"""

import math

from structure_variant import KINDS, validate


def install(world, mapping, carla, request, support_blueprint):
    validate(request)
    if not isinstance(support_blueprint, str) or not support_blueprint.startswith("static.prop."):
        raise ValueError("Installed structural support blueprint required")
    kind = request["structure_kind_requested"]
    library = world.get_blueprint_library()
    blueprint = library.find(support_blueprint)
    if blueprint is None:
        raise ValueError("Structural support asset unavailable")
    deck_start = request["deck_start_x_m"]
    deck_end = request["deck_end_x_m"]
    samples = []
    for x, expected_z in ((-60.0, 0.0), (deck_start, 4.0),
                          ((deck_start + deck_end) / 2, 4.0),
                          (deck_end, 4.0), (deck_end + 30, 0.0)):
        waypoint = mapping.get_waypoint(carla.Location(x=x, y=-1.75, z=expected_z),
                                        project_to_road=False,
                                        lane_type=carla.LaneType.Driving)
        if waypoint is None or waypoint.road_id != 313130 or waypoint.lane_id != -1:
            raise RuntimeError("Original raised-road lane readback unavailable")
        actual_z = waypoint.transform.location.z
        if not math.isfinite(actual_z) or abs(actual_z - expected_z) > 0.5:
            raise RuntimeError("Original drivable deck elevation differs")
        samples.append({"x_m": x, "expected_z_m": expected_z,
                        "native_z_m": actual_z, "road_id": waypoint.road_id,
                        "lane_id": waypoint.lane_id})
    owned = []
    support_rows = []
    try:
        for x in KINDS[kind]["support_x_m"]:
            for y in (-4.5, 4.5):
                actor = world.try_spawn_actor(blueprint, carla.Transform(
                    carla.Location(x=x, y=y, z=0)))
                if actor is None:
                    raise RuntimeError("Original structural support could not spawn")
                owned.append(actor)
                bounds = actor.bounding_box.get_world_vertices(actor.get_transform())
                z_values = [vertex.z for vertex in bounds]
                if len(bounds) != 8 or not all(math.isfinite(z) for z in z_values) or \
                        max(z_values) - min(z_values) < 3:
                    raise RuntimeError("Original structural support lacks deck-height geometry")
                support_rows.append({"actor_id": actor.id,
                                     "type_id": actor.type_id,
                                     "requested_x_m": x, "requested_y_m": y,
                                     "native_z_range_m": [min(z_values), max(z_values)]})
    except BaseException:
        for actor in reversed(owned):
            actor.destroy()
        raise
    return {"format": "worker-original-structure-setup",
            "structure_kind_requested": kind,
            "native_deck_samples": samples,
            "native_supports": support_rows,
            "span_count_requested": request["span_count"],
            "source_kind": "original_native_geometry_readback",
            "physical_structure_verified": False,
            "legal_view_obstructed": "independent_judgment_required"}, owned
