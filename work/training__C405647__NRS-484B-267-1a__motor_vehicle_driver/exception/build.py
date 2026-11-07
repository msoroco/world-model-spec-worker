"""Authored CPU requests for the officer-direction exception comparison.

All direction packets are synthetic requests. An officer's identity, actual
communication, recipient, and timing require later source observations.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = 'training__C405647__NRS-484B-267-1a__motor_vehicle_driver'
from official_motion import open_drive, requested_tracks

CASES = ('exception_1_1', 'exception_1_2')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
OUT = HERE / 'drafts'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return sha(data)


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def jsonl(rows):
    return ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows).encode()


def knobs_for(candidate):
    return {
        'officer_position_x_m': 54 if candidate == 'fallback1' else 48,
        'direction_start_frame': 40 if candidate == 'fallback2' else 80,
        'direction_duration_frames': 100 if candidate == 'fallback3' else 80,
        'officer_camera_fov_deg': 48 if candidate == 'fallback3' else 70,
    }


def requests(case, candidate):
    if case not in CASES or candidate not in CANDIDATES:
        raise ValueError('Unknown exception case or candidate')
    knobs = knobs_for(candidate)
    # Both branches use exactly the same approach, lamp and subject requests.
    motion = requested_tracks('official_2')
    rows = []
    for row in motion:
        frame = row['frame']
        directed = (case == 'exception_1_2' and
                    knobs['direction_start_frame'] <= frame <
                    knobs['direction_start_frame'] + knobs['direction_duration_frames'])
        rows.append({**row,
                     'approach_role_request': 'emergency_vehicle_authority_unverified',
                     'officer_direction_request': {
                         'requested': directed,
                         'recipient': 'subject_driver' if directed else None,
                         'content': 'remain_in_inner_lane' if directed else None,
                         'officer_identity_observed': False,
                         'actual_direction_observed': False,
                         'source_kind': 'authored_cpu_request'},
                     'officer_position_request_xy_m':
                         [knobs['officer_position_x_m'], -8.75]})
    return rows


def native_requests(case, candidate):
    """Reflect authored right-hand OpenDRIVE lanes into proposed Native world y."""
    result = []
    for row in requests(case, candidate):
        copied = {**row, 'subject_request': dict(row['subject_request']),
                  'approach_request': dict(row['approach_request']),
                  'officer_position_request_xy_m': list(row['officer_position_request_xy_m']),
                  'source_kind': 'authored_native_request'}
        copied['subject_request']['y_m'] *= -1
        copied['approach_request']['y_m'] *= -1
        copied['officer_position_request_xy_m'][1] *= -1
        result.append(copied)
    return result


def synthetic_observations(case, candidate):
    """Exercise visibility/timing logic without claiming original-pixel evidence."""
    rows = requests(case, candidate)
    knobs = knobs_for(candidate)
    first = knobs['direction_start_frame']
    last = first + knobs['direction_duration_frames']
    visible = (80 if candidate in ('fallback1', 'fallback3') else 60)
    return [{'frame': row['frame'], 'time_s': row['time_s'],
             'officer_in_frame': first <= row['frame'] < first + visible,
             'direction_cue_in_frame': (case == 'exception_1_2' and
                                        first <= row['frame'] < min(last, first + visible)),
             'source_kind': 'synthetic_cpu_visibility'} for row in rows]


def measure(rows, observations):
    requested = [r['frame'] for r in rows if r['officer_direction_request']['requested']]
    cues = [r['frame'] for r in observations if r['direction_cue_in_frame']]
    officers = [r['frame'] for r in observations if r['officer_in_frame']]
    return {'requested_direction_frames': len(requested),
            'synthetic_cue_frames': len(cues),
            'synthetic_officer_visible_frames': len(officers),
            'first_requested_frame': requested[0] if requested else None,
            'first_synthetic_cue_frame': cues[0] if cues else None,
            'cue_overlaps_request': bool(set(requested) & set(cues)),
            'original_pixels_or_identity_observed': False}


def build():
    source = Path('inputs') / ASSIGNMENT / 'assignment.json'
    assignment_bytes = source.read_bytes()
    clause = json.loads(assignment_bytes)['law_record']['text']
    assert 'when otherwise directed by a law enforcement officer' in clause
    map_sha = write(OUT / 'road.xodr', open_drive().encode())
    result = {'format': 'c405647-officer-exception-unselected-cpu-v1',
              'assignment_source_sha256': sha(assignment_bytes),
              'map_sha256': map_sha, 'rate_hz': 20, 'frames_per_case': 480,
              'cell': {'layout': 'road', 'maneuver': 'travel', 'control': 'emergency_vehicle'},
              'actor': 'motor_vehicle_driver', 'cases': []}
    for candidate in CANDIDATES:
        pair = []
        for case in CASES:
            folder = OUT / case / candidate
            rows = requests(case, candidate)
            observations = synthetic_observations(case, candidate)
            source_sha = write(folder / 'requested-tracks.jsonl', jsonl(rows))
            native_sha = write(folder / 'native-requests.jsonl',
                               jsonl(native_requests(case, candidate)))
            visibility_sha = write(folder / 'synthetic-officer-visibility.jsonl',
                                   jsonl(observations))
            metrics = measure(rows, observations)
            baseline = measure(requests(case, 'primary'),
                               synthetic_observations(case, 'primary'))
            trigger = None
            if candidate != 'primary':
                trigger = {
                    'fallback1': {'metric': 'synthetic_officer_visible_frames',
                                  'baseline_value': baseline['synthetic_officer_visible_frames'],
                                  'candidate_value': metrics['synthetic_officer_visible_frames'],
                                  'capture_target_frames': 80,
                                  'baseline_triggered': baseline['synthetic_officer_visible_frames'] < 80},
                    'fallback2': {'metric': 'first_requested_frame',
                                  'baseline_value': baseline['first_requested_frame'],
                                  'candidate_value': metrics['first_requested_frame'],
                                  'capture_target_latest_frame': 60,
                                  'baseline_triggered': (baseline['first_requested_frame'] is not None and
                                                         baseline['first_requested_frame'] > 60)},
                    'fallback3': {'metric': 'synthetic_cue_frames',
                                  'baseline_value': baseline['synthetic_cue_frames'],
                                  'candidate_value': metrics['synthetic_cue_frames'],
                                  'capture_target_frames': 80,
                                  'baseline_triggered': (baseline['synthetic_cue_frames'] < 80
                                                         if case == 'exception_1_2' else None)},
                }[candidate]
                trigger['source_file'] = 'synthetic-officer-visibility.jsonl'
                trigger['source_sha256'] = visibility_sha
                trigger['synthetic_engineering_target_only'] = True
            config = {'format': 'c405647-officer-exception-request-v1',
                      'case_id': ASSIGNMENT + '__' + case, 'candidate_id': candidate,
                      'status': 'unselected_cpu_draft', 'source_branch':
                      'when otherwise directed by a law enforcement officer',
                      'assignment_source_sha256': result['assignment_source_sha256'],
                      'map_sha256': map_sha, 'knobs': knobs_for(candidate),
                      'requested_tracks_sha256': source_sha,
                      'native_requests_sha256': native_sha,
                      'synthetic_visibility_sha256': visibility_sha,
                      'metrics': metrics,
                      'measured_trigger': trigger,
                      'fallback_trigger': None if candidate == 'primary' else {
                          'fallback1': 'source_bound_officer_framing_or_identity_gap',
                          'fallback2': 'direction_cue_after_requested_decision_window',
                          'fallback3': 'source_bound_direction_cue_visibility_below_capture_target'
                      }[candidate],
                      'physical_officer_identity_or_direction_verified': False,
                      'legal_exception_verified': False}
            config_sha = write(folder / 'config.json', encoded(config))
            result['cases'].append({'case_id': config['case_id'],
                                    'candidate_id': candidate,
                                    'config_sha256': config_sha,
                                    'requested_tracks_sha256': source_sha,
                                    'native_requests_sha256': native_sha,
                                    'synthetic_visibility_sha256': visibility_sha})
            pair.append(rows)
        assert all({k: a[k] for k in ('subject_request', 'approach_request', 'lamp_request')}
                   == {k: b[k] for k in ('subject_request', 'approach_request', 'lamp_request')}
                   for a, b in zip(*pair))
    manifest_sha = write(OUT / 'manifest.json', encoded(result))
    return {'case_candidates': len(result['cases']), 'manifest_sha256': manifest_sha}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
