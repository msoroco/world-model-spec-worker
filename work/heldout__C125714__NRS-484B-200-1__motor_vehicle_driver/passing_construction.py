"""Construct two directed Native vehicles for a proposed passing comparison."""

from math import hypot

from right_half_route import control_step


def spawn_lead(world, route, *, blueprint_id='vehicle.tesla.model3', lead_index=3):
    if len(route) < lead_index + 4 or lead_index < 2:
        raise ValueError('Passing route lacks lead and recovery distance')
    first, lead_point = route[0].transform.location, route[lead_index].transform.location
    forward = route[0].transform.get_forward_vector()
    delta_x, delta_y = lead_point.x-first.x, lead_point.y-first.y
    norm = hypot(forward.x, forward.y)
    if norm < .8 or (delta_x*forward.x + delta_y*forward.y)/norm < 5:
        raise ValueError('Lead spawn is not ahead of subject')
    blueprint = world.get_blueprint_library().find(blueprint_id)
    lead = world.try_spawn_actor(blueprint, route[lead_index].transform)
    if lead is None:
        raise ValueError('Native passing lead spawn failed')
    return lead


def lead_control(lead, route, index):
    transform = lead.get_transform()
    location = transform.location
    forward = transform.get_forward_vector()
    velocity = lead.get_velocity()
    target = route[min(5 + index//12, len(route)-1)].transform.location
    return control_step((location.x, location.y), (forward.x, forward.y),
                        (velocity.x, velocity.y), (target.x, target.y),
                        target_speed_mps=3.0)


def subject_passing_control(subject, target_xy):
    transform = subject.get_transform()
    location = transform.location
    forward = transform.get_forward_vector()
    velocity = subject.get_velocity()
    return control_step((location.x, location.y), (forward.x, forward.y),
                        (velocity.x, velocity.y), target_xy,
                        target_speed_mps=7.0)
