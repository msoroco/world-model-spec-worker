"""Unselected CPU construction for the official regulatory vehicle alternative."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from geometry import native_track_requests, open_drive, requested_tracks  # noqa: E402

ASSIGNMENT = ROOT.name
SOURCE = Path('inputs') / ASSIGNMENT / 'assignment.json'
OUT = Path(__file__).resolve().parent / 'drafts'
CASES = ('official_1', 'official_2')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return sha(data)


def lines(rows):
    return ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows).encode()


def build():
    assignment_bytes = SOURCE.read_bytes()
    assignment = json.loads(assignment_bytes)
    clause = assignment['law_record']['text']
    assert 'or an official vehicle of a regulatory agency' in clause
    assert 'flashing lights meeting the requirements of subsection 3 of NRS 484A.480' in clause
    map_bytes = open_drive().encode()
    map_sha = write(OUT / 'road.xodr', map_bytes)
    manifest = {'format': 'c405647-official-unselected-cpu-v1',
                'assignment_source_sha256': sha(assignment_bytes),
                'map_sha256': map_sha, 'cell': {'layout': 'road', 'maneuver': 'travel',
                                             'control': 'emergency_vehicle'},
                'actor': 'motor_vehicle_driver', 'rate_hz': 20, 'duration_s': 24,
                'source_branch': 'official_regulatory_vehicle_approach',
                'incorporated_source_status': 'exact_NRS_484A_480_3_not_in_assignment',
                'authority_lamps_native_or_legal_outcome_verified': False,
                'cases': []}
    for candidate in CANDIDATES:
        knobs = {'approach_start_x_m': -10 if candidate == 'fallback2' else -20,
                 'subject_speed_mps': 2.5 if candidate == 'fallback3' else 3,
                 'lane_change_start_s': 1 if candidate == 'fallback1' else 2,
                 'lane_change_duration_s': 3}
        pair = []
        for case in CASES:
            rows = requested_tracks(case, **knobs)
            native = native_track_requests(case, **knobs)
            folder = OUT / case / candidate
            source_sha = write(folder / 'requested-tracks.jsonl', lines(rows))
            native_sha = write(folder / 'native-requests.jsonl', lines(native))
            gaps = [r['subject_request']['x_m'] - r['approach_request']['x_m'] for r in rows]
            catchup = next((i for i, gap in enumerate(gaps) if gap <= 4.5), None)
            cleared = next((i for i, r in enumerate(rows)
                            if r['subject_request']['y_m'] + .9 < -3.5), None)
            # These bounds decide whether to change capture knobs, never legal applicability.
            triggers = {'fallback1': {'metric': 'full_body_clearance_before_catchup',
                                      'triggered': (cleared is None or catchup is None or cleared >= catchup)
                                      if case == 'official_1' else cleared is not None},
                        'fallback2': {'metric': 'catchup_before_last_six_seconds',
                                      'triggered': catchup is None or catchup >= 360},
                        'fallback3': {'metric': 'source_bound_lamp_visibility',
                                      'triggered': None}}
            if candidate == 'fallback3':
                # A synthetic visibility observation tests the source join and
                # capture target. It is not an original camera or equipment proof.
                visible_count = 300 if case == 'official_1' else 400
                visibility_rows = [{'frame': i, 'time_s': round(i / 20, 4),
                                    'lamp_in_frame': i < visible_count,
                                    'source_kind': 'synthetic_cpu_visibility'}
                                   for i in range(480)]
                visibility_sha = write(folder / 'synthetic-lamp-visibility.jsonl',
                                       lines(visibility_rows))
                triggers['fallback3'] = {
                    'metric': 'source_bound_lamp_visibility',
                    'triggered': visible_count * 4 < 480 * 3,
                    'visible_frames': visible_count, 'inspected_frames': 480,
                    'visibility_source_file': 'synthetic-lamp-visibility.jsonl',
                    'visibility_source_sha256': visibility_sha,
                    'capture_target_fraction': 0.75,
                    'visibility_source_kind': 'synthetic_cpu_visibility'}
            config = {'format': 'c405647-official-native-request-v1',
                      'case_id': ASSIGNMENT + '__' + case, 'candidate_id': candidate,
                      'status': 'unselected_cpu_draft', 'source_branch': manifest['source_branch'],
                      'assignment_source_sha256': manifest['assignment_source_sha256'],
                      'map_sha256': map_sha, 'knobs': knobs,
                      'requested_tracks_sha256': source_sha,
                      'native_requests_sha256': native_sha,
                      'camera_profile': 'four_camera_c405647_native_profile',
                      'requested_behavior': 'clear_inner_lane' if case == 'official_1' else 'maintain_inner_lane',
                      'trigger': None if candidate == 'primary' else {
                          **triggers[candidate], 'catchup_frame': catchup,
                          'first_full_body_clearance_frame': cleared,
                          'source_file': 'requested-tracks.jsonl', 'source_sha256': source_sha,
                          'engineering_target_only': True},
                      'authority_lamps_native_or_legal_outcome_verified': False}
            write(folder / 'config.json', (json.dumps(config, indent=2) + '\n').encode())
            manifest['cases'].append({'case_id': config['case_id'], 'candidate_id': candidate,
                                      'config_sha256': sha((folder / 'config.json').read_bytes()),
                                      'requested_tracks_sha256': source_sha,
                                      'native_requests_sha256': native_sha})
            pair.append(rows)
        assert all(a['approach_request'] == b['approach_request'] and
                   a['lamp_request'] == b['lamp_request'] for a, b in zip(*pair))
    write(OUT / 'manifest.json', (json.dumps(manifest, indent=2) + '\n').encode())
    return {'case_candidates': len(manifest['cases']), 'map_sha256': map_sha,
            'manifest_sha256': sha((OUT / 'manifest.json').read_bytes())}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
