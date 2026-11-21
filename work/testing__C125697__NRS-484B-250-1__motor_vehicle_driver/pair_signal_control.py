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
    if len(lights) < 2:
        raise ValueError("All entrance lights required")
    original = []
    try:
        for light in lights:
            original.append((light, light.get_state()))
            light.freeze(True)
            light.set_state(traffic_light_state.Off)
        world.tick()
        if any(light.get_state() != traffic_light_state.Off for light in lights):
            raise ValueError("Native Off readback failed")
        yield lights
    finally:
        for light, state in reversed(original):
            light.set_state(state)
            light.freeze(False)
        if original:
            world.tick()
            if any(light.get_state() != state for light, state in original):
                raise ValueError("Native signal restoration readback failed")
