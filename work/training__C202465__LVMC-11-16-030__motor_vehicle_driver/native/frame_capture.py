"""One original Native tick: body, dynamic rays, and exception-source join.

The caller owns world ticks, camera frame joins and independently reviewed
per-frame flagman/signal readbacks. This module cannot make those facts true.
"""

from __future__ import annotations

from rail_join import joined_row
from rail_native_rays import observe


def capture_frame(world, ego, rail_vehicles, reviews, location_factory,
                  frame, flagman_state, signal_state):
    pose = ego.get_transform()
    vertices = ego.bounding_box.get_world_vertices(pose)
    velocity = ego.get_velocity()
    body = {
        "frame": frame, "actor_id": ego.id, "actor_type_id": ego.type_id,
        "body_vertices_m": [[float(v.x), float(v.y), float(v.z)] for v in vertices],
        "velocity_mps": [float(velocity.x), float(velocity.y), float(velocity.z)],
        "position_m": [float(pose.location.x), float(pose.location.y),
                       float(pose.location.z)],
    }
    rays = observe(world, ego, rail_vehicles, reviews["railway"], location_factory, frame)
    joined = joined_row(frame, body, rays, reviews, flagman_state, signal_state)
    return {"frame": frame, "body": body, "rays": rays,
            "flagman": dict(flagman_state), "signal": dict(signal_state),
            "joined": joined, "physical_acceptance_claimed": False}
