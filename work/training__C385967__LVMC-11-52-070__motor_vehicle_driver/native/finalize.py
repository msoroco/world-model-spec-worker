"""Finalize retained angle-parking sources after Native ownership has ended."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from saved_measure import process as measure_saved
from physical_preparation import assess as assess_physical

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    if not path.is_file():
        raise ValueError('Missing required source: ' + path.name)
    return [json.loads(line) for line in path.read_text().splitlines()]


def decoded_frames(path):
    if not path.is_file():
        raise ValueError('Missing required source: ' + path.name)
    answer = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
        '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
        capture_output=True, text=True, timeout=120)
    if answer.returncode or not answer.stdout.strip().isdigit():
        raise ValueError('Camera decode failed: ' + path.name)
    return int(answer.stdout.strip())


def measure_engineer_designation_source(attempt, config):
    authority = json.loads((attempt / 'permission_authority.json').read_text())
    return {'value': {'document_sha256': sha(attempt / 'permission-source.bin'),
        'authority_claim': authority['authority_claim'],
        'permission_verified': False,
        'independent_street_review_required': True},
        'method': 'measure_engineer_designation_source',
        'sources': {name: sha(attempt/name) for name in
            ('permission_authority.json', 'permission-source.bin')}}


def measure_parked_front_direction(attempt, config):
    fixture = json.loads((attempt / 'road_geometry.json').read_text()).get('provenance') == 'synthetic_cpu_fixture'
    joined = measure_saved(attempt, config, allow_fixture=fixture)
    return {'value': joined['measurement']['direction'],
        'method': 'measure_parked_front_direction',
        'sources': joined['source_hashes'], 'detail': joined}


def derive_channels(attempt, description, samples, mapping):
    folder = attempt / 'channels'
    folder.mkdir(exist_ok=True)
    geometry = json.loads((attempt / 'road_geometry.json').read_text())
    permission = json.loads((attempt / 'permission_authority.json').read_text())
    (folder / 'context.json').write_text(json.dumps({'permission_authority': permission},
                                              indent=2, allow_nan=False) + '\n')
    for channel in description['channels']:
        name = channel['name']
        values = []
        for row, frame in zip(samples, mapping):
            by_name = {
                'dev.regulatory_sign': {'authored_sign_proposed': True,
                    'actual_marking_review_required': True, 'permission_verified': False},
                'st.parking_space': {'bay_center_xy_m': geometry['bay_center_xy_m'],
                    'bay_heading_deg': geometry['bay_heading_deg']},
                'st.lane_marking': {'actual_marking_review_required': True,
                    'native_parking_lane_id': geometry['parking_lane_id']},
                'drv.standing_or_parked': {'speed_mps': row['ego_speed_mps'],
                    'activity_review_required': True},
                'kin.heading': row['ego_front_yaw_deg'],
                'st.lane_direction': geometry['lawful_traffic_heading_deg'],
                'rel.occupies': {'native_parking_lane_id': row['native_lane_id'],
                    'ego_center_xy_m': row['ego_center_xy_m']},
                'native_body_pose': row,
                'camera_frame_join': frame,
            }
            if name not in by_name:
                raise ValueError('Unsupported saved channel: ' + name)
            values.append(json.dumps({'time_s': row['time_s'],
                                      'value': by_name[name]}, allow_nan=False))
        (folder / (name + '.jsonl')).write_text('\n'.join(values) + '\n')


def finalize(attempt, output):
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain original finalization; use a fresh attempt')
    config = json.loads((attempt / 'config.json').read_text())
    if config['duration_s'] * config['rate_hz'] != 600:
        raise ValueError('Exact 600-frame window changed')
    samples = rows(attempt / 'native_samples.jsonl')
    mapping = rows(attempt / 'video_frames.jsonl')
    trace = rows(attempt / 'trace.jsonl')
    evidence = rows(attempt / 'capture/evidence.jsonl')
    if any(len(items) != 600 for items in (samples, mapping, trace, evidence)):
        raise ValueError('Original source frame count differs')
    for index, (sample, frame, trace_row, item) in enumerate(zip(samples, mapping, trace, evidence)):
        native = sample['native_frame']
        if frame['video_frame'] != index or any(n != native for n in
                (frame['native_frame'], trace_row['frame'], item['original_frame'])):
            raise ValueError('Original source/frame join differs')
        if any(abs(float(t)-sample['time_s']) > .001 for t in
                (frame['time_s'], trace_row['time_s'], item['recording_time_s'])):
            raise ValueError('Original source/time join differs')
    fixture = json.loads((attempt/'road_geometry.json').read_text()).get('provenance') == 'synthetic_cpu_fixture'
    joined = measure_saved(attempt, config, allow_fixture=fixture)
    physical = assess_physical(attempt, config, allow_fixture=fixture)
    video_counts = {name+'.mkv': decoded_frames(attempt/(name+'.mkv')) for name in CAMERAS}
    if any(count != 600 for count in video_counts.values()):
        raise ValueError('Four-camera 600-frame source incomplete')
    description = config['recording_description']
    derive_channels(attempt, description, samples, mapping)
    refs = [{'name': c['name'], 'unit': c['unit'],
             'reference': 'channels/'+c['name']+'.jsonl'} for c in description['channels']]
    refs += [{'name': c['name'], 'unit': c['unit'],
              'reference': 'channels/context.json'} for c in description['context_inputs']]
    direction = joined['measurement']['direction']
    expected = 'front_with_lawful_flow' if config['requested_front_yaw_deg'] == 45 else 'front_against_lawful_flow'
    target = {'target': 'sampled parked-front direction relative to one-way lawful flow',
        'requested': expected, 'measured': direction,
        'method': 'saved 600-frame Native front-vector projection',
        'tolerance': None, 'matched': direction == expected,
        'physical_cause_confirmed': False,
        'cause_evidence': list(joined['source_hashes'])}
    physical_result = {key: value for key, value in physical.items()
                       if key != 'legal_verdict'}
    result = {'case_id': config['case_id'],
        'measured_values': {'sampled_front_direction': direction},
        'target_checks': [target], 'setup_confirmed': False,
        'behavior_attempted': not fixture,
        'maneuver_completed': physical['original_physical_completion_claimed'],
        'termination_reason': 'full saved source window analyzed',
        'physical_failure_flags': ['city_permission_and_marking_review_required']+
            (['synthetic_fixture_not_physical'] if fixture else []),
        'trace_reference': 'trace.jsonl',
        'video_references': list(video_counts),
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': description, 'recording_evidence': refs,
        'realized_observables': {},
        'physical_checks': {'maneuver': physical_result},
        'provenance_kind': 'synthetic_cpu_fixture' if fixture else 'native',
        'accepted': False, 'legal_verdict_claimed': False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report = {'format': 'c385967-saved-analysis-v1', 'case_id': config['case_id'],
        'measurements': {'engineer_designation_source': measure_engineer_designation_source(attempt, config),
                         'parked_front_direction': measure_parked_front_direction(attempt, config)},
        'source_hashes': joined['source_hashes'], 'physical': physical,
        'four_camera_frames': video_counts,
        'scope': 'saved source diagnostic; independent City authority and marking review required'}
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    (attempt/'result.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--attempt', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    print(json.dumps(finalize(a.attempt, a.output), sort_keys=True))
