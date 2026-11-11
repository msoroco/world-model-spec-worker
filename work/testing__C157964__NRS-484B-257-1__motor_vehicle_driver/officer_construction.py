"""Spawn a source-reviewed officer performer at a surveyed junction position.

A pedestrian blueprint and costume are not proof of police authority or actual
traffic control. Those require original-camera and provenance review.
"""

from contextlib import contextmanager
import math


def _distance(a,b):
    return math.sqrt((a.x-b.x)**2+(a.y-b.y)**2+(a.z-b.z)**2)


@contextmanager
def spawn_officer_performer(world, blueprint, transform, junction_center,
                            *, min_clearance_m=2.0, max_distance_m=20.0):
    point=transform.location
    distance=_distance(point,junction_center)
    if not math.isfinite(distance) or distance<min_clearance_m or distance>max_distance_m:
        raise ValueError("Officer placement outside surveyed junction band")
    actor=world.try_spawn_actor(blueprint,transform)
    if actor is None:raise ValueError("Native officer performer spawn failed")
    try:
        realized=actor.get_location()
        if _distance(realized,point)>1.0:
            raise ValueError("Realized officer location differs from surveyed placement")
        yield {"actor":actor,"surveyed_distance_to_junction_m":distance,
               "realized_location":realized}
    finally:
        actor.destroy()
