"""Audit the fixed right-side geometry against an earlier other-body entry."""

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = REPO / '.runtime-work/c125714-right-three-compat-v1'
EARLIER = REPO / '.runtime-work/c125714-right-earlier-compat-v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def check(base, earlier):
    base, earlier = Path(base), Path(earlier)
    configs = [json.loads((root / 'config.json').read_text()) for root in (base, earlier)]
    if ([c['selected_case_id'].rsplit('__', 1)[-1] for c in configs]
            != ['source_verified_other_right_near_time', 'source_verified_other_right_earlier']):
        raise ValueError('Wrong exact timing comparison cases')
    for key in ('law_id', 'cell_id', 'actor', 'rate_hz', 'duration_s', 'cameras',
                'required_atoms', 'source_packets', 'recording_description',
                'ego_target_speed_mps', 'other_target_speed_mps'):
        if configs[0][key] != configs[1][key]:
            raise ValueError('Fixed timing config changed: ' + key)
    if configs[0]['other_release_frame'] == configs[1]['other_release_frame']:
        raise ValueError('Other release command did not change')
    fixed_files = ('road_geometry.json', 'road.xodr', 'video_frames.jsonl', 'trace.jsonl',
                   'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
                   'driver_reference.mkv')
    for name in fixed_files:
        if sha(base / name) != sha(earlier / name):
            raise ValueError('Fixed timing source changed: ' + name)
    histories = [rows(root / 'crossing_history.jsonl') for root in (base, earlier)]
    if len(histories[0]) != 60 or len(histories[1]) != 60:
        raise ValueError('Timing comparison lacks 60 original frames')
    for a, b in zip(*histories):
        if a['frame'] != b['frame'] or a['time_s'] != b['time_s'] or a['ego'] != b['ego']:
            raise ValueError('Fixed ego body history changed')
    reports = [json.loads((root / 'analysis-report.json').read_text()) for root in (base, earlier)]
    timings = [report['measurements']['body_entry_timing']['value'] for report in reports]
    sides = [report['measurements']['approach_side']['value']['other_is_to_ego_right'] for report in reports]
    if (sides != [True, True] or
            timings[0]['first_body_entry']['ego'] != timings[1]['first_body_entry']['ego'] or
            timings[0]['ego_minus_other_entry_time_s'] != 0.5 or
            timings[1]['ego_minus_other_entry_time_s'] != 1.0):
        raise ValueError('Original source timing difference absent')
    return {'format': 'worker-c125714-right-timing-comparison',
            'case_ids': [c['selected_case_id'] for c in configs],
            'fixed_source_sha256': {name: sha(base / name) for name in fixed_files},
            'source_history_sha256': [sha(root / 'crossing_history.jsonl') for root in (base, earlier)],
            'ego_minus_other_entry_delta_s': [0.5, 1.0],
            'software_comparison_passed': True, 'physical_acceptance_claimed': False,
            'approximately_same_time_judgment': 'unresolved'}


def main():
    positive = check(BASE, EARLIER)
    with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work', prefix='c125714-timing-negative-') as temp:
        root = Path(temp)
        for name in ('config.json', 'road_geometry.json', 'road.xodr', 'video_frames.jsonl',
                     'trace.jsonl', 'crossing_history.jsonl', 'analysis-report.json',
                     'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
                     'driver_reference.mkv'):
            shutil.copyfile(EARLIER / name, root / name)
        geometry = json.loads((root / 'road_geometry.json').read_text())
        geometry['intersection_id'] = 999
        (root / 'road_geometry.json').write_text(json.dumps(geometry) + '\n')
        try:
            check(BASE, root)
        except ValueError as error:
            if 'Fixed timing source changed: road_geometry.json' not in str(error):
                raise
            negative = str(error)
        else:
            raise AssertionError('Changed crossing source passed')
    path = ROOT / 'cases/source_verified_other_right_earlier/comparison-receipt.json'
    path.write_text(json.dumps(dict(positive, negative_rejected=negative), indent=2) + '\n')
    print(json.dumps({'comparison': 'right_hand_entry_timing',
                      'deltas_s': positive['ego_minus_other_entry_delta_s'],
                      'negative_rejected': negative, 'legal_judgment': 'unresolved'}))


if __name__ == '__main__':
    main()
