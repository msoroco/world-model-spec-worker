"""Spawn and verify the Native walker used for officer-control comparisons."""

from contextlib import contextmanager
import math


def _distance(a, b):
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 +
                     (a.z - b.z) ** 2)


@contextmanager
def spawn(world, blueprint, transform, junction_center):
    intended = transform.location
    distance = _distance(intended, junction_center)
    if not math.isfinite(distance) or not 2.0 <= distance <= 20.0:
        raise ValueError('Officer performer outside authored junction band')
    actor = world.try_spawn_actor(blueprint, transform)
    if actor is None:
        raise ValueError('Native officer performer spawn failed')
    try:
        realized = actor.get_location()
        if _distance(realized, intended) > 1.0:
            raise ValueError('Native officer location differs from construction')
        yield actor
    finally:
        actor.destroy()
