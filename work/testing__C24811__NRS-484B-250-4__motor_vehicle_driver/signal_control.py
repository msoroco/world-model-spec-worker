"""Reversible Native Off-state request for every inventoried entrance.

Off readback is an engineering setup check. Physical complete inoperability of
installed, uncovered vehicular heads still requires original source review.
"""

from contextlib import contextmanager


def find_entrance_lights(world, entrance_road_lanes):
    lights = list(world.get_actors().filter("traffic.traffic_light*"))
    selected = []
    for road_id, lane_id in entrance_road_lanes:
        matching = [light for light in lights if any(
            waypoint.road_id == road_id and waypoint.lane_id == lane_id
            for waypoint in light.get_affected_lane_waypoints())]
        if len(matching) != 1:
            raise ValueError("Expected one governing Native light per entrance")
        selected.append(matching[0])
    if len(selected) < 2 or len({light.id for light in selected}) != len(selected):
        raise ValueError("Distinct inventoried entrance heads required")
    return selected


@contextmanager
def request_all_off(world, lights, traffic_light_state):
    with request_all_state(world, lights, traffic_light_state.Off) as selected:
        yield selected


@contextmanager
def request_all_state(world, lights, desired_state):
    if len(lights) < 2:
        raise ValueError("All entrance lights required")
    if desired_state is None:
        raise ValueError("Explicit Native signal state required")
    original = []
    try:
        for light in lights:
            frozen = light.is_frozen() if callable(getattr(light, "is_frozen", None)) else False
            original.append((light, light.get_state(), frozen))
            light.freeze(True)
            light.set_state(desired_state)
        world.tick()
        if any(light.get_state() != desired_state for light in lights):
            raise ValueError("Native signal-state readback failed")
        yield lights
    finally:
        for light, state, frozen in reversed(original):
            light.set_state(state)
            light.freeze(frozen)
        if original:
            world.tick()
            if any(light.get_state() != state or
                   (callable(getattr(light, "is_frozen", None)) and light.is_frozen() != frozen)
                   for light, state, frozen in original):
                raise ValueError("Native signal restoration readback failed")
