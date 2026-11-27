"""Source-bound Native closed-divider props for the C80909 opening branch."""
from __future__ import annotations

import math

from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from native_driver import body_polygon


def _rect(value):
    if (not isinstance(value,list) or len(value)!=4 or
            not all(type(x) in (int,float) and math.isfinite(x) for x in value) or
            value[0]>=value[2] or value[1]>=value[3]):
        raise ValueError("invalid reviewed divider rectangle")
    return box(*value)


def validate_divider(scene):
    context=scene["context"]
    opening=_rect(context["opening_bounds_xy_m"])
    barriers=[_rect(value) for value in context["closed_divider_bounds_xy_m"]]
    props=scene.get("divider_props")
    if not barriers or not isinstance(props,list) or not props:
        raise ValueError("reviewed physical divider props required")
    planned=[]
    for item in props:
        if not item.get("blueprint_id") or not type(item.get("z_m")) in (int,float):
            raise ValueError("reviewed divider blueprint and height required")
        if not math.isfinite(item["z_m"]):
            raise ValueError("non-finite divider placement")
        footprint=_rect(item["bounds_xy_m"])
        if footprint.intersects(opening) or not any(b.covers(footprint) for b in barriers):
            raise ValueError("divider prop extends into opening or roadway")
        planned.append(footprint)
    coverage=unary_union(planned)
    if any(barrier.difference(coverage).area>1e-4 for barrier in barriers):
        raise ValueError("reviewed closed divider has an unconstructed gap")
    return planned


def spawn_divider(world,scene,carla):
    """Spawn actual static props; reject asset footprints that differ from review."""
    planned=validate_divider(scene)
    opening=_rect(scene["context"]["opening_bounds_xy_m"])
    barriers=[_rect(value) for value in scene["context"]["closed_divider_bounds_xy_m"]]
    actors=[]
    try:
        for item,expected in zip(scene["divider_props"],planned):
            blueprint=world.get_blueprint_library().find(item["blueprint_id"])
            center=expected.centroid
            transform=carla.Transform(carla.Location(x=center.x,y=center.y,z=item["z_m"]),
                                      carla.Rotation(yaw=0))
            actor=world.spawn_actor(blueprint,transform)
            if actor is None:
                raise ValueError("Native closed-divider prop spawn failed")
            actors.append(actor)
            footprint=Polygon(body_polygon(actor))
            if (not footprint.is_valid or
                    expected.symmetric_difference(footprint).area>0.05 or
                    footprint.intersects(opening) or
                    not any(barrier.covers(footprint) for barrier in barriers)):
                raise ValueError("Native divider actor footprint differs from reviewed geometry")
        actual=unary_union([Polygon(body_polygon(actor)) for actor in actors])
        if any(barrier.difference(actual).area>0.05 for barrier in barriers):
            raise ValueError("Native closed divider has a physical gap")
        return actors
    except BaseException:
        for actor in reversed(actors):
            actor.destroy()
        raise


def verify_recorded_divider(context,reviewed_props,geometry):
    scene={"context":context,"divider_props":reviewed_props}
    planned=validate_divider(scene)
    actors=geometry.get("actors")
    if not isinstance(actors,list) or len(actors)!=len(planned):
        raise ValueError("original Native divider actor count differs from review")
    if [item.get("actor_id") for item in actors]!=context.get("divider_actor_ids"):
        raise ValueError("original Native divider actor identities differ")
    actual=[]
    for original,expected,item in zip(actors,planned,reviewed_props):
        if original.get("blueprint_id")!=item["blueprint_id"]:
            raise ValueError("original Native divider blueprint differs")
        footprint=Polygon(original["body_vertices_xy_m"])
        if (not footprint.is_valid or footprint.area<=0 or
                expected.symmetric_difference(footprint).area>0.05):
            raise ValueError("saved Native divider footprint differs from reviewed geometry")
        actual.append(footprint)
    coverage=unary_union(actual)
    barriers=[_rect(value) for value in context["closed_divider_bounds_xy_m"]]
    if any(barrier.difference(coverage).area>0.05 for barrier in barriers):
        raise ValueError("saved Native divider has a physical gap")
    return {"actor_count":len(actors),"closed_divider_coverage_verified":True}
