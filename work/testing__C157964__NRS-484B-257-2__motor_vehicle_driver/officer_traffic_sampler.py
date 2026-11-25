"""Native other-vehicle body sampling for the signed entrance comparison.

The sampled body can establish geometric occupancy. Whether an approaching
vehicle is an immediate hazard remains an explicit source-reviewed input.
"""

import math
from shapely.geometry import MultiPoint, Polygon


def native_sampler(other_actor, site_intake, hazard_source):
    if (not isinstance(site_intake, dict) or
            site_intake.get("format") != "worker-officer-subsection-2-source-intake" or
            not site_intake.get("site_id")):
        raise ValueError("Reviewed site intake required for body sampling")
    polygon = Polygon(site_intake.get("intersection_polygon_xy_m", []))
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("Reviewed intersection polygon required")
    if type(getattr(other_actor, "id", None)) is not int:
        raise ValueError("Native other vehicle identity required")
    if not callable(hazard_source):
        raise ValueError("Approaching-hazard source adapter required")

    def sample(frame_index):
        if type(frame_index) is not int or frame_index < 0:
            raise ValueError("Native sample frame index required")
        box = getattr(other_actor, "bounding_box", None)
        if box is None or not hasattr(box, "get_world_vertices"):
            raise ValueError("Native other vehicle bounding box required")
        vertices = box.get_world_vertices(other_actor.get_transform())
        if not isinstance(vertices, (list, tuple)) or len(vertices) < 4:
            raise ValueError("Complete Native other vehicle body required")
        points = []
        for vertex in vertices:
            x, y = getattr(vertex, "x", None), getattr(vertex, "y", None)
            if (type(x) not in (int, float) or type(y) not in (int, float) or
                    not math.isfinite(x) or not math.isfinite(y)):
                raise ValueError("Finite Native other vehicle body required")
            points.append((float(x), float(y)))
        body = MultiPoint(points).convex_hull
        if body.geom_type != "Polygon" or body.area <= 0:
            raise ValueError("Degenerate Native other vehicle body")
        hazard = hazard_source(frame_index)
        if (not isinstance(hazard, dict) or
                hazard.get("site_id") != site_intake["site_id"] or
                hazard.get("other_actor_id") != other_actor.id or
                type(hazard.get("approaching_hazard")) is not bool or
                not isinstance(hazard.get("source"), str) or not hazard["source"]):
            raise ValueError("Sourced approaching-hazard judgment required")
        return {"source": "Native other-actor bounding-box readback",
                "site_id": site_intake["site_id"], "frame_index": frame_index,
                "other_actor_id": other_actor.id,
                "other_body_vertices_xy_m": [list(point) for point in points],
                "other_inside": body.intersects(polygon),
                "approaching_hazard": hazard["approaching_hazard"],
                "hazard_source": hazard["source"],
                "legal_immediate_hazard_judgment": "unresolved"}

    return sample
