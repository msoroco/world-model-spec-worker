"""Own a stationary third Native vehicle ahead of the following pair."""
from contextlib import contextmanager
import math

@contextmanager
def spawn_queued_vehicle(world,blueprint,transform,ego,lead,control_factory,*,minimum_lead_separation_m=6.0):
    queued=world.try_spawn_actor(blueprint,transform)
    if queued is None:raise ValueError('Native queued traffic spawn failed')
    try:
        q=queued.get_location();l=lead.get_location();e=ego.get_location()
        lead_distance=math.dist((q.x,q.y,q.z),(l.x,l.y,l.z))
        ego_distance=math.dist((q.x,q.y,q.z),(e.x,e.y,e.z))
        if not all(math.isfinite(v) for v in (lead_distance,ego_distance)) or lead_distance<minimum_lead_separation_m or ego_distance<=lead_distance:
            raise ValueError('Queued vehicle is not safely ahead of lead')
        queued.apply_control(control_factory(throttle=0.0,brake=1.0,steer=0.0))
        yield queued
    finally:
        queued.destroy()
