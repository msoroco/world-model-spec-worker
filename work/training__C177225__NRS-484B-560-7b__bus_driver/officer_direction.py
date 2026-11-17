"""Deterministic CPU construction for the C177225 directed-stop comparison.

Coordinates are one-dimensional station coordinates along an authored crossing
approach. A CARLA runner must map them to checked road waypoints and save its
native map readback; these targets are not observations of a driven bus.
"""
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class Crossing:
    track_center_m: float = 0.0
    track_half_width_m: float = 2.5
    stop_setback_m: float = 7.0
    bus_length_m: float = 12.0
    exit_clearance_m: float = 18.0

    def validate(self):
        values = vars(self).values()
        if not all(isinstance(v, (int, float)) and isfinite(v) for v in values):
            raise ValueError('Crossing geometry must be finite')
        if self.track_half_width_m <= 0 or self.stop_setback_m <= self.track_half_width_m:
            raise ValueError('Stop line must precede the near rail')
        if self.bus_length_m <= 0 or self.exit_clearance_m < self.bus_length_m:
            raise ValueError('Bus exit space does not clear the far rail')

    def stop_station(self, direction):
        self.validate()
        if direction not in (-1, 1):
            raise ValueError('Approach direction must be -1 or 1')
        return self.track_center_m - direction * self.stop_setback_m

    def approach_station(self, direction, distance_m=70.0):
        if not isfinite(distance_m) or distance_m <= self.stop_setback_m + self.bus_length_m:
            raise ValueError('Insufficient approach distance for bus')
        return self.track_center_m - direction * distance_m

    def exit_station(self, direction):
        self.validate()
        if direction not in (-1, 1):
            raise ValueError('Approach direction must be -1 or 1')
        return self.track_center_m + direction * (
            self.track_half_width_m + self.exit_clearance_m)


@dataclass(frozen=True)
class OfficerStop:
    officer_id: str
    bus_id: str
    direction: int
    issued_frame: int
    first_governing_frame: int
    last_governing_frame: int
    crossing_id: str
    authorized: bool
    hand_signal: str = 'STOP'

    def validate(self):
        if not self.officer_id or not self.bus_id or not self.crossing_id:
            raise ValueError('Officer, recipient and crossing bindings are required')
        if self.direction not in (-1, 1) or self.hand_signal != 'STOP':
            raise ValueError('This construction requires an explicit directed stop')
        if not self.authorized:
            raise ValueError('Officer authorization is not established')
        frames = (self.issued_frame, self.first_governing_frame,
                  self.last_governing_frame)
        if any(type(frame) is not int or frame < 0 for frame in frames):
            raise ValueError('Direction frames must be nonnegative integers')
        if not frames[0] <= frames[1] < frames[2]:
            raise ValueError('Direction must be issued before it governs')


def target_control(layout, signal, *, bus_id, crossing_id, direction,
                   station_m, speed_mps, frame, obey, stop_margin_m=0.75):
    """Return a requested control target, never an observed or legal verdict.

    `obey=False` is the controlled contrast: it keeps the same signal and
    geometry but requests motion through the line. The runner must retain the
    actual velocity and signal history for independent later review.
    """
    layout.validate()
    signal.validate()
    if (bus_id, crossing_id, direction) != (
            signal.bus_id, signal.crossing_id, signal.direction):
        raise ValueError('Directed stop does not govern this bus approach')
    if not isfinite(station_m) or not isfinite(speed_mps) or speed_mps < 0:
        raise ValueError('Missing measured bus station or speed')
    if type(frame) is not int or frame < 0:
        raise ValueError('Missing synchronized frame')
    if type(obey) is not bool:
        raise ValueError('Requested behavior must be explicit')
    if not isfinite(stop_margin_m) or stop_margin_m <= 0:
        raise ValueError('Stop margin must be positive')
    line = layout.stop_station(direction)
    remaining_m = direction * (line - station_m) - stop_margin_m
    governing = signal.first_governing_frame <= frame <= signal.last_governing_frame
    if frame < signal.issued_frame or not governing:
        return {'throttle': 0.25, 'brake': 0.0, 'requested': 'approach',
                'signal_governing': False, 'distance_to_stop_m': remaining_m}
    if obey:
        if remaining_m <= 0.5 and speed_mps <= 0.05:
            return {'throttle': 0.0, 'brake': 1.0, 'requested': 'hold_stop',
                    'signal_governing': True, 'distance_to_stop_m': remaining_m}
        braking_distance = speed_mps * speed_mps / 5.0 + 1.0
        brake = 1.0 if remaining_m <= braking_distance else 0.0
        return {'throttle': 0.0 if brake else 0.18, 'brake': brake,
                'requested': 'stop_before_rail', 'signal_governing': True,
                'distance_to_stop_m': remaining_m}
    return {'throttle': 0.25, 'brake': 0.0, 'requested': 'continue_through_line',
            'signal_governing': True, 'distance_to_stop_m': remaining_m}
