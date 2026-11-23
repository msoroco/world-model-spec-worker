"""Finite reverse/yield controller with explicit CARLA control injection."""


class BackingController:
    def __init__(self, *, yield_for_pedestrian, control_factory=None):
        if not isinstance(yield_for_pedestrian, bool):
            raise ValueError("yield policy must be explicit")
        self.yield_for_pedestrian = yield_for_pedestrian
        self.control_factory = control_factory or (lambda **values: values)

    def step(self, vehicle, *, pedestrian_in_corridor, phase):
        if phase not in ("hold", "backing", "complete"):
            raise ValueError("unknown controller phase")
        if not isinstance(pedestrian_in_corridor, bool):
            raise ValueError("pedestrian corridor state missing")
        hold = phase in ("hold", "complete") or (self.yield_for_pedestrian and pedestrian_in_corridor)
        command = {"reverse": True, "throttle": 0.0 if hold else 0.18,
                   "brake": 1.0 if hold else 0.0, "hand_brake": False}
        vehicle.apply_control(self.control_factory(**command))
        return command
