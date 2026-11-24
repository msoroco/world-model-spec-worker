"""Pure CPU geometry/controller checks for proposed Native sweep controls."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from sweep_native import (ACCEL_TARGETS_MPS2, ROUTE_OFFSETS_M,
                          longitudinal_acceleration, route_waypoint,
                          throttle_for_acceleration)

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rejects(label, action):
    try:
        action()
    except ValueError as error:
        return {'name': label, 'rejected': True, 'error': str(error)}
    raise AssertionError(label + ' accepted')


class Waypoint:
    road_id = 1
    lane_id = -1

    def __init__(self, options=None):
        self.options = options

    def next(self, offset):
        return self.options if self.options is not None else [Waypoint()]


class Map:
    def __init__(self, origin):
        self.origin = origin

    def get_waypoint(self, location, project_to_road):
        if location != 'spawn' or not project_to_road:
            raise AssertionError('Source spawn mapping differs')
        return self.origin


def main():
    ranges = json.loads((HERE / 'sweep-physical/planned-ranges.json').read_text())
    if tuple(ranges['positive']['acceleration_plan']['setpoints_mps2']) != ACCEL_TARGETS_MPS2:
        raise ValueError('Acceleration grid differs from source plan')
    if tuple(ranges['positive']['route_plan']['coordinates_m']) != ROUTE_OFFSETS_M:
        raise ValueError('Route grid differs from source plan')
    spawn = SimpleNamespace(location='spawn')
    geometry = []
    for offset in ROUTE_OFFSETS_M:
        result = route_waypoint(Map(Waypoint()), spawn, offset)
        geometry.append({'offset_m': offset, 'road_id': result.road_id,
                         'lane_id': result.lane_id, 'selected': True})
    controller = []
    for target in ACCEL_TARGETS_MPS2:
        acceleration = longitudinal_acceleration(SimpleNamespace(x=0.0, y=0.1), 90)
        throttle = throttle_for_acceleration(target, acceleration, 0.25)
        if not 0 <= throttle <= 1:
            raise AssertionError('Controller left normalized range')
        controller.append({'target_mps2': target, 'measured_mps2': acceleration,
                           'next_throttle': throttle})
    negatives = [
        rejects('off_grid_acceleration', lambda: throttle_for_acceleration(0.4, 0.1, 0.25)),
        rejects('nonfinite_feedback', lambda: throttle_for_acceleration(0.1, float('nan'), 0.25)),
        rejects('off_grid_route', lambda: route_waypoint(Map(Waypoint()), spawn, 200)),
        rejects('missing_route', lambda: route_waypoint(Map(Waypoint([])), spawn, 25)),
        rejects('ambiguous_route', lambda: route_waypoint(Map(Waypoint([Waypoint(), Waypoint()])), spawn, 25)),
        rejects('different_road', lambda: route_waypoint(Map(Waypoint([SimpleNamespace(road_id=2, lane_id=-1)])), spawn, 25)),
    ]
    proof = {'format': 'c229597-native-sweep-helper-proof-v1',
             'source_range_sha256': sha(HERE / 'sweep-physical/planned-ranges.json'),
             'helper_sha256': sha(HERE / 'sweep_native.py'),
             'route_selections': geometry, 'controller_steps': controller,
             'negative_cases': negatives, 'native_executed': False,
             'physical_response_verified': False,
             'highway_status_verified': False, 'legal_verdict_claimed': False}
    path = HERE / 'sweep-physical/native-helper-proof.json'
    path.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'route_selections': len(geometry),
                      'controller_steps': len(controller),
                      'negative_rejections': len(negatives), 'proof_sha256': sha(path)}))


if __name__ == '__main__':
    main()
