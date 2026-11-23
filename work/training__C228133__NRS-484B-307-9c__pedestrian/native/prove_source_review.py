"""CPU source-binding proof using stubs, without any Native observation claim."""

import copy
import hashlib
import json
from pathlib import Path
import tempfile

from source_capture import VIEWS
from source_review import bind, write_bound_rows


HERE = Path(__file__).resolve().parent
OUT = HERE.parent / 'source-review-proof.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rejected(fn, expected):
    try:
        fn()
    except ValueError as error:
        assert expected in str(error), str(error)
        return str(error)
    raise AssertionError('Unsafe source review passed')


def prove():
    root = HERE.parents[2] / '.runtime-work'
    root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root, prefix='c228133-source-review-') as temp:
        attempt = Path(temp)
        hashes = {view: hashlib.sha256(view.encode()).hexdigest() for view in VIEWS}
        signal = {'frame': 0, 'native_frame': 101, 'time_s': 1.0,
                  'red_actor_id': 31, 'arrow_actor_id': 32,
                  'observed_red_actor_state': 'Red',
                  'observed_arrow_actor_state': 'Green',
                  'source_kind': 'native_signal'}
        device = {'frame': 0, 'native_frame': 101, 'time_s': 1.0,
                  'device_actor_id': None, 'source_kind': 'native_pedestrian_device'}
        video = {'video_frame': 0, 'native_frame': 101, 'carla_frame': 101,
                 'time_s': 1.0, 'source_rgb_sha256': hashes}
        sources = {'native-signal-frames.jsonl': signal,
                   'native-pedestrian-device-frames.jsonl': device,
                   'video_frames.jsonl': video,
                   'road-boundary.json': {'source_kind': 'native_map_readback',
                                          'road_side': 'at_or_above_y',
                                          'boundary_y_m': 0}}
        for name, row in sources.items():
            (attempt / name).write_text(json.dumps(row) + '\n')
        decision = {'frame': 0, 'source_rgb_sha256': hashes,
                    'red_actor_id': 31, 'arrow_actor_id': 32,
                    'device_actor_id': None, 'red': 'steady',
                    'green_turn_arrow': True, 'governs_pedestrian': True,
                    'permits_proceed': False,
                    'directional_arrow_pixels_reviewed': True,
                    'facing_governance_reviewed': True,
                    'other_device_inventory_reviewed': True}
        review = {'format': 'c228133-native-source-review-v1',
                  'reviewer': 'synthetic-cpu-stub',
                  'source_sha256': {name: digest(attempt / name) for name in sources},
                  'highway_boundary_reviewed': True,
                  'highway_boundary_basis': 'official_road_inventory',
                  'frames': [decision]}
        path = attempt / 'review.json'

        def check(changed):
            path.write_text(json.dumps(changed) + '\n')
            return bind(attempt, path)

        signals, devices = check(review)
        assert signals[0]['green_turn_arrow'] and signals[0]['red'] == 'steady'
        assert not devices[0]['permits_proceed']
        output = attempt / 'reviewed'
        assert write_bound_rows(attempt, path, output) == 1
        assert (output / 'native-signal-frames.jsonl').is_file()
        errors = []
        for key, value, expected in (
                ('source_rgb_sha256', {**hashes, 'overview': '0' * 64},
                 'four original camera'),
                ('green_turn_arrow', 'yes', 'explicit signal'),
                ('directional_arrow_pixels_reviewed', False, 'explicit signal'),
                ('permits_proceed', True, 'identified other device')):
            bad = copy.deepcopy(review)
            bad['frames'][0][key] = value
            errors.append(rejected(lambda bad=bad: check(bad), expected))
        bad = copy.deepcopy(review)
        bad['highway_boundary_reviewed'] = False
        errors.append(rejected(lambda: check(bad), 'Highway boundary'))
        bad = copy.deepcopy(review)
        bad['frames'][0]['native_frame'] = 102
        (attempt / 'native-signal-frames.jsonl').write_text(json.dumps(
            {**signal, 'native_frame': 102}) + '\n')
        errors.append(rejected(lambda: check(bad), 'Reviewed Native source changed'))
    return {'format': 'c228133-source-review-cpu-proof-v1', 'passed': True,
            'review_module_sha256': digest(HERE / 'source_review.py'),
            'negative_checks_passed': len(errors), 'negative_errors': errors,
            'synthetic_cpu_stub': True, 'original_native_observed': False,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    result = prove()
    OUT.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
