"""Spawn two real barrier sections with a traversable median opening between.

The supplied blueprints/transforms are source-reviewed. The CPU geometry check
does not prove public-authority establishment or physical drivability.
"""

from contextlib import contextmanager
import math

from shapely.geometry import MultiPoint, Polygon


def _xy(value):
    x,y=float(value.x),float(value.y)
    if not math.isfinite(x) or not math.isfinite(y):raise ValueError("Nonfinite barrier geometry")
    return x,y


@contextmanager
def spawn_barrier_opening(world,sections,opening_xy_m,barrier_axis_xy):
    if len(sections)!=2:raise ValueError("Exactly two physical barrier sections required")
    opening=Polygon(opening_xy_m)
    if not opening.is_valid or opening.area<=0:raise ValueError("Invalid opening footprint")
    ax,ay=map(float,barrier_axis_xy)
    norm=math.hypot(ax,ay)
    if not math.isfinite(norm) or norm<=0:raise ValueError("Invalid divider axis")
    ax,ay=ax/norm,ay/norm
    owned=[]
    try:
        footprints=[];sides=[]
        for blueprint,transform in sections:
            actor=world.try_spawn_actor(blueprint,transform)
            if actor is None:raise ValueError("Native barrier section spawn failed")
            owned.append(actor)
            vertices=actor.bounding_box.get_world_vertices(actor.get_transform())
            if len(vertices)<4:raise ValueError("Missing realized barrier vertices")
            footprint=MultiPoint([_xy(v) for v in vertices]).convex_hull
            if footprint.area<=0 or footprint.intersects(opening):
                raise ValueError("Barrier section overlaps or closes opening")
            footprints.append(footprint)
            relative=footprint.centroid
            sides.append((relative.x-opening.centroid.x)*ax+(relative.y-opening.centroid.y)*ay)
        if sides[0]*sides[1]>=0:raise ValueError("Barrier sections do not straddle opening")
        yield {"actors":owned,"opening_xy_m":list(opening.exterior.coords),
               "barrier_footprints_xy_m":[list(p.exterior.coords) for p in footprints],
               "section_axis_offsets_m":sides}
    finally:
        for actor in reversed(owned):actor.destroy()
