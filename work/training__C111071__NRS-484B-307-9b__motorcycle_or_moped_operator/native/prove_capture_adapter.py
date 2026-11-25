"""Exercise raw Native actor and signal readback before a live CARLA integration."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace as Object

from runner import capture_row

HERE = Path(__file__).resolve().parent


def point(x, y, z):
    return Object(x=x, y=y, z=z)


class Box:
    def get_world_vertices(self, transform):
        location = transform.location
        return [point(location.x + dx, location.y + dy, location.z + dz)
                for dx in (-1.0, 1.0) for dy in (-0.4, 0.4)
                for dz in (-0.3, 0.3)]


class Actor:
    id = 101
    type_id = 'vehicle.harley-davidson.low_rider'
    bounding_box = Box()

    def get_transform(self):
        return Object(location=point(10.0, -5.0, 1.0))

    def get_velocity(self):
        return point(3.0, 4.0, 0.0)


def proof():
    signal = {'governing_signal_id': 17, 'cross_signal_id': 18,
              'governing_state': 'red', 'arrow_state': 'review_required',
              'cross_state': 'green'}
    waypoint = Object(road_id=1, lane_id=-1)
    observed = capture_row(0, 81, 0.05, Actor(), waypoint, signal)
    if (observed['source_kind'] != 'native_observation' or
            observed['blueprint_id'] != Actor.type_id or
            observed['native_frame'] != 81 or observed['time_s'] != 0.05 or
            observed['speed_mps'] != 5.0 or len(observed['body_vertices_m']) != 8 or
            observed['signal_readback'] != signal):
        raise AssertionError('Raw actor/signal adapter differs')
    negatives = []
    for label, args, expected in (
            ('missing_lane', (0, 81, 0.05, Actor(), None, signal), 'Original body, lane or signal'),
            ('missing_signal', (0, 81, 0.05, Actor(), waypoint, None), 'Original body, lane or signal'),
            ('invalid_frame_index', (600, 81, 0.05, Actor(), waypoint, signal), 'Original Native frame identity'),
            ('invalid_time', (0, 81, float('nan'), Actor(), waypoint, signal), 'Original Native time')):
        try:
            capture_row(*args)
        except ValueError as exc:
            if expected not in str(exc):
                raise AssertionError(label + ': wrong rejection') from exc
            negatives.append({'mutation': label, 'error': str(exc)})
        else:
            raise AssertionError(label + ': accepted')
    return {'format': 'c111071-native-adapter-cpu-proof-v1', 'passed': True,
            'source': 'fake CARLA-shaped actor readback; no live CARLA invoked',
            'actor_id': observed['actor_id'], 'blueprint_id': observed['blueprint_id'],
            'body_vertices': len(observed['body_vertices_m']),
            'speed_mps': observed['speed_mps'],
            'signal_readback': observed['signal_readback'],
            'negative_rejections': negatives,
            'runner_sha256': hashlib.sha256((HERE / 'runner.py').read_bytes()).hexdigest(),
            'original_native_observed': False, 'physical_acceptance_claimed': False}


if __name__ == '__main__':
    result = proof()
    (HERE / 'capture-adapter-proof.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'passed': True, 'negative_rejections': len(result['negative_rejections'])}))
