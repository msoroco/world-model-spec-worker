"""Native traffic-light selection and reversible state control for C158196.

This controls a real CARLA signal actor; callers must separately retain image
evidence that its vehicular heads are installed and uncovered. A frozen phase is
not, by itself, evidence of an inoperative signal.
"""


def find_governing_signal(world, road_id, lane_id):
    """Choose only a signal whose affected Native waypoint matches the approach."""
    matches = []
    for light in world.get_actors().filter("traffic.traffic_light*"):
        affected = light.get_affected_lane_waypoints()
        if any(wp.road_id == road_id and wp.lane_id == lane_id for wp in affected):
            matches.append(light)
    if len(matches) != 1:
        raise ValueError(f"Expected one governing traffic light, found {len(matches)}")
    return matches[0]


class SignalControl:
    """Apply a requested Native signal state and restore the actor afterward."""

    def __init__(self, world, light, states, target):
        if target not in ("Red", "Green", "Off"):
            raise ValueError("Unsupported target state")
        self.world, self.light, self.states, self.target = world, light, states, target
        self.original = None

    def __enter__(self):
        self.original = self.light.get_state()
        self.light.freeze(True)
        try:
            self.light.set_state(getattr(self.states, self.target))
            self.world.tick()
            if self.light.get_state() != getattr(self.states, self.target):
                raise ValueError("Traffic light state readback failed")
        except Exception:
            self.light.set_state(self.original)
            self.light.freeze(False)
            raise
        return self.light

    def __exit__(self, *_):
        self.light.set_state(self.original)
        self.light.freeze(False)
        self.world.tick()
        if self.light.get_state() != self.original:
            raise ValueError("Traffic light restoration readback failed")
