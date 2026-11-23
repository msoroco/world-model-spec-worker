"""Prove original/review joins and rejection with synthetic Native-shaped rows."""
import copy
import hashlib
import json
from pathlib import Path

from join_lighting_review import join
from measure_lighting import measure


HERE = Path(__file__).resolve().parent
SCRATCH = HERE.parents[2] / '.runtime-work' / 'c230241-join-proof'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n'
                            for row in rows))


def scenario(name, native, review, mapping, expected=None):
    directory = SCRATCH / name
    directory.mkdir(parents=True, exist_ok=True)
    paths = [directory / key for key in
             ('native.jsonl', 'review.jsonl', 'map.jsonl')]
    for path, rows in zip(paths, (native, review, mapping)):
        write_rows(path, rows)
    joined = directory / 'joined.jsonl'
    if joined.exists():
        joined.unlink()
    try:
        receipt = join(*paths, joined)
        assert expected is None, name + ' unexpectedly passed'
        assert receipt['frames'] == 600
        assert receipt['native_source_sha256'] == sha(paths[0])
        assert receipt['review_source_sha256'] == sha(paths[1])
        assert receipt['frame_map_sha256'] == sha(paths[2])
        return {'case': name, 'passed': True, 'joined_sha256': sha(joined),
                'native_sha256': sha(paths[0]),
                'review_sha256': sha(paths[1]),
                'frame_map_sha256': sha(paths[2])}
    except ValueError as exc:
        assert expected is not None and expected in str(exc), (name, str(exc))
        assert not joined.exists()
        return {'case': name, 'passed': True, 'expected_rejection': str(exc)}


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    native = [{'source_kind': 'synthetic_native_sample',
               'video_frame': index, 'native_frame': 2000 + index,
               'time_s': index / 20, 'velocity_mps': [3.0, 0.0, 0.0],
               'light_state_observed': 3,
               'light_state_requested': 'LowBeam|Position'}
              for index in range(600)]
    review = [{'source_kind': 'synthetic_native_sample',
               'video_frame': index, 'native_frame': 2000 + index,
               'time_s': index / 20, 'utc_s': 11801 + index / 20,
               'headlamp_lit': True, 'tail_lamp_lit': True,
               'headlamp_white': True, 'tail_lamp_red': True,
               'front_visible_ft': 300, 'rear_visible_ft': 500,
               'discernible_500ft': True}
              for index in range(600)]
    mapping = [{'video_frame': index, 'native_frame': 2000 + index,
                'carla_frame': 2000 + index, 'time_s': index / 20}
               for index in range(600)]
    checks = [scenario('joined-positive', native, review, mapping)]
    context = SCRATCH / 'context.json'
    context.write_text(json.dumps({
        'source_kind': 'synthetic_native_sample',
        'vehicle_class_source': 'synthetic fixture',
        'clock_source': 'synthetic fixture',
        'range_calibration_source': 'synthetic fixture',
        'visibility_review_source': 'synthetic fixture',
        'vehicle_covered': True, 'headlamp_count': 1,
        'tail_lamp_rear_mounted': True, 'sunset_utc_s': 10000,
        'next_sunrise_utc_s': 50000}, indent=2) + '\n')
    measurement = measure(SCRATCH / 'joined-positive' / 'joined.jsonl',
                          context, SCRATCH / 'joined-positive' / 'map.jsonl')
    assert measurement['measurements']['required_burning_frames'] == 600
    assert measurement['measurements']['headlamp_dark_frames'] == 0
    checks[0]['measurement_source_sha256'] = measurement['source_sha256']
    for name, field, target, expected in (
            ('review-identity', 'review', 'native_frame',
             'Original Native/review frame join differs'),
            ('native-velocity', 'native', 'velocity_mps',
             'Original Native velocity missing'),
            ('injected-derived', 'native', 'front_visible_ft',
             'Native motion file has injected derived lighting review'),
            ('review-field', 'review', 'discernible_500ft',
             'Independent lighting review incomplete'),
            ('map-identity', 'mapping', 'native_frame',
             'Original Native/review frame join differs')):
        originals = {'native': native, 'review': review, 'mapping': mapping}
        altered = copy.deepcopy(originals)
        if name == 'review-identity':
            altered[field][-1][target] = 9999
        elif name == 'native-velocity':
            altered[field][-1][target] = [3.0, None, 0.0]
        elif name == 'injected-derived':
            altered[field][-1][target] = 999
        elif name == 'review-field':
            altered[field][-1].pop(target)
        else:
            altered[field][-1][target] = 9999
        checks.append(scenario(name, altered['native'], altered['review'],
                               altered['mapping'], expected))
    receipt = {'format': 'c230241-native-review-join-proof-v1',
               'diagnostic_only': True, 'checks': checks,
               'join_script_sha256': sha(HERE / 'join_lighting_review.py'),
               'measurement_script_sha256': sha(HERE / 'measure_lighting.py'),
               'prover_sha256': sha(Path(__file__))}
    output = HERE / 'lighting-review-join-proof.json'
    output.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'checks_passed': len(checks),
                      'receipt_sha256': sha(output)}))


if __name__ == '__main__':
    main()
