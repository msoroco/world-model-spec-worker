"""Independent retained-source and full-media diagnostic delivery audit."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.media import audit as media_audit

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    if not path.is_file():
        raise ValueError('missing original: ' + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def check(attempt, case):
    attempt = Path(attempt).resolve()
    for name in ('construction.json', 'native-index.json', 'geometry.json',
                 'signal.json', 'native-rows.jsonl', 'trace.jsonl',
                 'video_frames.jsonl', 'interaction_history.jsonl',
                 'capture/manifest.json', 'acquisition-provenance.json'):
        if not (attempt / name).is_file():
            raise ValueError('missing original: ' + name)
    construction = json.loads((attempt / 'construction.json').read_text())
    if construction['case_id'] != case:
        raise ValueError('wrong exact delivery case')
    index = json.loads((attempt / 'native-index.json').read_text())
    if index['case_id'] != case or index['frames'] != 600 or index['rate_hz'] != 20:
        raise ValueError('incomplete original Native index')
    for name, expected in index['files'].items():
        if not (attempt / name).is_file():
            raise ValueError('missing original: ' + name)
        if sha(attempt / name) != expected:
            raise ValueError('altered original: ' + name)
    native, trace, mapping, motion = (rows(attempt / name) for name in
                                      ('native-rows.jsonl', 'trace.jsonl',
                                       'video_frames.jsonl', 'interaction_history.jsonl'))
    if not all(len(group) == 600 for group in (native, trace, mapping, motion)):
        raise ValueError('incomplete original frame stream')
    if any(native[i]['frame'] != i or trace[i]['frame'] != mapping[i]['carla_frame']
           or motion[i]['frame'] != mapping[i]['carla_frame']
           or abs(trace[i]['time_s'] - mapping[i]['time_s']) > 1e-6
           or abs(motion[i]['time_s'] - mapping[i]['time_s']) > 1e-6
           for i in range(600)):
        raise ValueError('original time/frame join differs')
    if not all('ego_front_x_m' in row and 'other_speed_mps' in row
               and 'other_in_intersection' in row for row in native):
        raise ValueError('original participants omitted')
    geometry = json.loads((attempt / 'geometry.json').read_text())
    signal = json.loads((attempt / 'signal.json').read_text())
    if geometry['stop_line_present'] is not False or geometry['near_crosswalk_present'] is not True:
        raise ValueError('selected geometry differs')
    if signal['installed'] is not True or signal['uncovered'] is not True or signal['inoperative_observed'] is not True:
        raise ValueError('selected signal source differs')
    media = {}
    mapping_hash = sha(attempt / 'video_frames.jsonl')
    for name in CAMERAS:
        video = attempt / (name + '.mkv')
        if not video.is_file():
            raise ValueError('missing original: ' + name + '.mkv')
        media[name] = media_audit(video, 600, mapping_sha256=mapping_hash)
    provenance = json.loads((attempt / 'acquisition-provenance.json').read_text())
    return {'format': 'nrs-484b-250-4-delivery-source-diagnostic-v1',
            'case_id': case, 'passed': True, 'frames': 600,
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'selected_signal_and_crosswalk'],
            'source_hashes': {name: sha(attempt / name) for name in
                              ('native-index.json', 'native-rows.jsonl', 'trace.jsonl',
                               'video_frames.jsonl', 'interaction_history.jsonl',
                               'signal.json', 'geometry.json')},
            'video_source_hashes': {name: sha(attempt / (name + '.mkv')) for name in CAMERAS},
            'provenance_kind': provenance.get('provenance_kind'),
            'diagnostic_fixture': provenance.get('diagnostic_fixture'),
            'actual_pixels_confirmed': False, 'physical_completion_confirmed': False,
            'canonical_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = check(args.attempt, args.case)
    Path(args.output).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': True, 'case_id': args.case, 'frames': 600}))
