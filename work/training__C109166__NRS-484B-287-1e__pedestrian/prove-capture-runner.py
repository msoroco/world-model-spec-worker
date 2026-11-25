"""CPU proof of Native runner's identity, device state and source gate."""
import copy
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
import capture_runner
import native_request


class Light:
    id = 42

    def __init__(self):
        self.state = 'Off'

    def set_state(self, state):
        self.state = state

    def get_state(self):
        return self.state

    def get_opendrive_id(self):
        return 'surveyed-203'

    def freeze(self, enabled):
        self.frozen = enabled


class Carla:
    class TrafficLightState:
        Green = 'Green'
        Red = 'Red'


def rejects(fn, expected):
    try:
        fn()
    except ValueError as exc:
        if expected not in str(exc):
            raise AssertionError(str(exc)) from exc
        return str(exc)
    raise AssertionError('invalid Native request accepted')


def main():
    config = {'cell_id': 'C109166', 'law_id': 'NRS-484B-287-1e',
              'actor': 'pedestrian', 'case_suffix': 'controlled_2',
              'case_id': 'training__C109166__NRS-484B-287-1e__pedestrian__controlled_2',
              'rate_hz': 20, 'duration_s': 30,
              'cameras': native_request.camera_plan(),
              'opendrive_signal_id': 'surveyed-203', 'entry_proxy_x_m': -5.5,
              'driver_reference_height_m': 3.0}
    valid = capture_runner.check(config)
    light = Light()
    head = capture_runner.NativeHead(light, Carla, 'surveyed-203')
    head.frame = 1100
    observed = native_request.apply_device_and_readback(head, 'controlled_2', 100, native_frame=1100)
    if observed['displayed_instruction'] != 'diagonal_dont_walk' or light.state != 'Red' or not light.frozen:
        raise AssertionError('Native red head actuation/readback differs')
    head.frame = 1160
    observed = native_request.apply_device_and_readback(head, 'controlled_2', 160, native_frame=1160)
    if observed['displayed_instruction'] != 'diagonal_walk' or light.state != 'Green':
        raise AssertionError('Native green head actuation/readback differs')
    failures = {}
    for name, key, value, expected in (
        ('wrong_case', 'case_id', 'other', 'identity differs'),
        ('wrong_duration', 'duration_s', 10, '30-second'),
        ('missing_head', 'opendrive_signal_id', '', 'head identity'),
        ('wrong_camera', 'cameras', [], 'source-camera'),
        ('wrong_proxy', 'entry_proxy_x_m', -6.0, 'entry proxy')):
        trial = copy.deepcopy(config)
        trial[key] = value
        failures[name] = rejects(lambda: capture_runner.check(trial), expected)
    light.get_opendrive_id = lambda: 'other'
    failures['head_identity_changed'] = rejects(lambda: head.observe(native_request.request('controlled_1', 100)['device_id']),
                                                'surveyed head changed')
    proof = {'format': 'c109166-native-capture-runner-cpu-proof-v1',
             'runner_sha256': hashlib.sha256((HERE / 'native/capture_runner.py').read_bytes()).hexdigest(),
             'valid': valid, 'stubbed_head_actuation_readback': True, 'rejections': failures,
             'native_executed': False, 'official_status_verified': False,
             'actual_display_pixels_reviewed': False}
    (HERE / 'capture-runner-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'runner_sha256': proof['runner_sha256'],
                      'negative_count': len(failures), 'native_executed': False}))


if __name__ == '__main__':
    main()
