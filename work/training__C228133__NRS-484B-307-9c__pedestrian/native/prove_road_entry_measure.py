"""Exercise saved-source road-entry measurement with synthetic CPU fixtures."""

import hashlib
import json
from pathlib import Path
import shutil

from road_entry_measure import VIEWS, measure


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / '.runtime-work/c228133-road-entry-measurement-fixture-v1'
OUTPUT = Path(__file__).resolve().parents[1] / 'road-entry-measurement-proof.json'


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))


def fixture(path, *, enter=True, permit=False, governs=True):
    path.mkdir(parents=True)
    kind = 'synthetic_native_sample'
    (path / 'road-boundary.json').write_text(json.dumps({
        'format': 'pedestrian-road-boundary-v1', 'road_side': 'at_or_above_y',
        'boundary_y_m': 0.0, 'source_kind': kind}) + '\n')
    positions = [-1.0, -0.5, 0.25 if enter else -0.25, 0.5 if enter else -0.2]
    write_rows(path / 'native-pedestrian-frames.jsonl', [
        {'frame': frame, 'native_frame': 100 + frame, 'time_s': 1 + frame / 20, 'actor_id': 7,
         'footprint_roadward_y_m': y, 'source_kind': kind}
        for frame, y in enumerate(positions)])
    write_rows(path / 'native-signal-frames.jsonl', [
        {'frame': frame, 'native_frame': 100 + frame, 'time_s': 1 + frame / 20, 'red': 'steady',
         'green_turn_arrow': True, 'governs_pedestrian': governs,
         'source_kind': kind} for frame in range(4)])
    write_rows(path / 'native-pedestrian-device-frames.jsonl', [
        {'frame': frame, 'native_frame': 100 + frame, 'time_s': 1 + frame / 20, 'permits_proceed': permit,
         'source_kind': kind} for frame in range(4)])
    write_rows(path / 'video_frames.jsonl', [
        {'video_frame': frame, 'native_frame': 100 + frame,
         'carla_frame': 100 + frame, 'time_s': 1 + frame / 20,
         'source_rgb_sha256': {view: '%064x' % (frame + index + 1)
                               for index, view in enumerate(VIEWS)}}
        for frame in range(4)])


def reject(path, expected):
    try:
        measure(path, diagnostic_fixture=True)
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError('Unexpected rejection: ' + str(error)) from error
        return str(error)
    raise AssertionError('Corrupt source was accepted')


def prove():
    if ROOT / '.runtime-work' not in FIXTURE.parents:
        raise ValueError('Fixture must stay ignored')
    if FIXTURE.exists():
        shutil.rmtree(FIXTURE)
    rows = []
    for name, options, expected in (
            ('red_entry', {'enter': True}, [2]),
            ('no_entry', {'enter': False}, []),
            ('other_device_permits', {'enter': True, 'permit': True}, []),
            ('non_governing_signal', {'enter': True, 'governs': False}, [])):
        path = FIXTURE / name
        fixture(path, **options)
        result = measure(path, diagnostic_fixture=True)
        assert result['potential_9c_entry_frames'] == expected
        assert result['diagnostic_fixture'] and not result['original_native_observed']
        rows.append({'scenario': name, 'potential_9c_entry_frames': expected,
                     'entry_events': result['entry_events']})
    negative = FIXTURE / 'red_entry'
    missing = negative / 'native-pedestrian-device-frames.jsonl'
    held = negative / 'native-pedestrian-device-frames.hold'
    missing.rename(held)
    missing_error = reject(negative, 'Missing required source')
    held.rename(missing)
    frame_map = negative / 'video_frames.jsonl'
    original = frame_map.read_text()
    altered = [json.loads(line) for line in original.splitlines()]
    del altered[2]['source_rgb_sha256'][VIEWS[-1]]
    write_rows(frame_map, altered)
    camera_error = reject(negative, 'four-camera frame join')
    frame_map.write_text(original)
    signal = negative / 'native-signal-frames.jsonl'
    original = signal.read_text()
    altered = [json.loads(line) for line in original.splitlines()]
    altered[2]['time_s'] = 0.5
    write_rows(signal, altered)
    time_error = reject(negative, 'timestamps do not join')
    signal.write_text(original)
    native_frame_original = signal.read_text()
    altered = [json.loads(line) for line in native_frame_original.splitlines()]
    altered[2]['native_frame'] = 999
    write_rows(signal, altered)
    native_frame_error = reject(negative, 'Native frame identities do not join')
    signal.write_text(native_frame_original)
    source = Path(__file__).with_name('road_entry_measure.py')
    return {'format': 'c228133-road-entry-measurement-proof-v1', 'passed': True,
            'measurement_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'source_kind': 'synthetic_native_sample', 'rows': rows,
            'negative_errors': [missing_error, camera_error, time_error,
                                native_frame_error],
            'original_native_observed': False, 'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


if __name__ == '__main__':
    result = prove()
    OUTPUT.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
