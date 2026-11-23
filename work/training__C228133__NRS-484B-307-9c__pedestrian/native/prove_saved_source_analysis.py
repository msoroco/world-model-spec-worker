"""Full-window synthetic CPU proof for the saved C228133 source path."""

import hashlib
import json
from pathlib import Path
import tempfile

from saved_source_analysis import analyze, digest
from source_capture import VIEWS


HERE = Path(__file__).resolve().parent
OUT = HERE.parent / 'saved-source-analysis-proof.json'
FRAMES = 600


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n'
                            for row in rows))


def sample(attempt, enters):
    attempt.mkdir()
    signal, device, pedestrian, video, decisions = [], [], [], [], []
    for i in range(FRAMES):
        time_s = i / 20
        frame = i + 100
        hashes = {view: hashlib.sha256(f'{view}:{i}'.encode()).hexdigest()
                  for view in VIEWS}
        signal.append({'frame': i, 'native_frame': frame, 'time_s': time_s,
                       'red_actor_id': 31, 'arrow_actor_id': 32,
                       'observed_red_actor_state': 'Red',
                       'observed_arrow_actor_state': 'Green',
                       'source_kind': 'native_signal'})
        device.append({'frame': i, 'native_frame': frame, 'time_s': time_s,
                       'device_actor_id': None,
                       'source_kind': 'native_pedestrian_device'})
        pedestrian.append({'frame': i, 'native_frame': frame, 'time_s': time_s,
                           'actor_id': 17, 'source_kind': 'native_actor',
                           'footprint_roadward_y_m': 0.2 if enters and i >= 80
                           else -0.2})
        video.append({'video_frame': i, 'native_frame': frame,
                      'carla_frame': frame, 'time_s': time_s,
                      'source_rgb_sha256': hashes})
        decisions.append({'frame': i, 'source_rgb_sha256': hashes,
                          'red_actor_id': 31, 'arrow_actor_id': 32,
                          'device_actor_id': None, 'red': 'steady',
                          'green_turn_arrow': True,
                          'governs_pedestrian': True,
                          'permits_proceed': False,
                          'directional_arrow_pixels_reviewed': True,
                          'facing_governance_reviewed': True,
                          'other_device_inventory_reviewed': True})
    for name, rows in (('native-signal-frames.jsonl', signal),
                       ('native-pedestrian-device-frames.jsonl', device),
                       ('native-pedestrian-frames.jsonl', pedestrian),
                       ('video_frames.jsonl', video)):
        write_rows(attempt / name, rows)
    (attempt / 'road-boundary.json').write_text(json.dumps({
        'format': 'pedestrian-road-boundary-v1',
        'source_kind': 'native_map_readback', 'native_road_id': 7,
        'road_side': 'at_or_above_y', 'boundary_y_m': 0}) + '\n')
    (attempt / 'governing-device-authority.json').write_text(json.dumps({
        'format': 'c228133-governing-device-authority-v1',
        'source_kind': 'official_traffic_control_inventory',
        'is_debug_geometry': False, 'red_actor_id': 31,
        'arrow_actor_id': 32,
        'authority_reference': 'synthetic-cpu-fixture'}) + '\n')
    (attempt / 'highway-authority.json').write_text(json.dumps({
        'format': 'c228133-highway-authority-v1',
        'basis': 'official_road_inventory', 'native_road_id': 7,
        'road_side': 'at_or_above_y', 'boundary_y_m': 0,
        'authority_reference': 'synthetic-cpu-fixture'}) + '\n')
    names = ('native-signal-frames.jsonl',
             'native-pedestrian-device-frames.jsonl', 'video_frames.jsonl',
             'road-boundary.json', 'governing-device-authority.json',
             'highway-authority.json')
    review = {'format': 'c228133-native-source-review-v1',
              'reviewer': 'synthetic-cpu-fixture',
              'source_sha256': {name: digest(attempt / name) for name in names},
              'highway_boundary_reviewed': True,
              'highway_boundary_basis': 'official_road_inventory',
              'frames': decisions}
    (attempt / 'independent-review.json').write_text(json.dumps(review) + '\n')


def prove():
    root = HERE.parents[2] / '.runtime-work'
    root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root, prefix='c228133-saved-600-') as temp:
        temp = Path(temp)
        observed = {}
        for suffix in ('reference', 'contrast'):
            attempt = temp / suffix
            sample(attempt, suffix == 'contrast')
            before = {p.name: digest(p) for p in attempt.iterdir() if p.is_file()}
            report = analyze(attempt)
            assert report['measurement']['frame_count'] == FRAMES
            expected = [80] if suffix == 'contrast' else []
            assert report['measurement']['potential_9c_entry_frames'] == expected
            assert before == {p.name: digest(p) for p in attempt.iterdir()
                              if p.is_file()}
            observed[suffix] = expected
        broken = temp / 'tampered'
        sample(broken, True)
        with (broken / 'native-signal-frames.jsonl').open('a') as out:
            out.write('{}\n')
        try:
            analyze(broken)
        except ValueError as error:
            assert 'Reviewed Native source changed' in str(error)
        else:
            raise AssertionError('Tampered original signal rows accepted')
    return {'format': 'c228133-saved-source-analysis-proof-v1',
            'passed': True, 'frames_per_case': FRAMES,
            'duration_s': FRAMES / 20, 'rate_hz': 20,
            'observed_potential_entry_frames': observed,
            'original_sources_preserved': True,
            'tampered_signal_source_rejected': True,
            'analyzer_sha256': digest(HERE / 'saved_source_analysis.py'),
            'synthetic_cpu_fixture': True,
            'original_native_observed': False,
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


if __name__ == '__main__':
    result = prove()
    OUT.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
