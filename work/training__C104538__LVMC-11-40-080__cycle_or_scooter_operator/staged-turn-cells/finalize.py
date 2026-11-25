"""Saved-only finalization of an original staged signed-turn attempt.

The output preserves unreviewed posture, sign authorization, and pixels. It
does not assign legal compliance or turn causation to an authored route.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from saved_native import audit_attempt, rows, sha


def _write_json(path, value):
    with path.open('x') as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + '\n')


def _write_rows(path, values):
    with path.open('x') as stream:
        for value in values:
            stream.write(json.dumps(value, allow_nan=False) + '\n')


def measure_signed_turn(root, geometry):
    sources = ('native_samples.jsonl', 'rider_native_samples.jsonl',
               'sign-survey.json', 'reference_corner.mkv')
    return {'method': 'measure_signed_turn',
            'value': {'direction': geometry['direction'],
                      'behavior': geometry['behavior'],
                      'heading_change_deg': geometry['heading_change_deg'],
                      'destination_road_id': geometry['destination_road_id'],
                      'engineering_geometry_matched': True,
                      'original_posture_verified': False,
                      'official_sign_authorization_verified': False},
            'sources': {name: sha(root / name) for name in sources}}


def _channel(name, n, m, r, t, survey, geometry):
    if name == 'ru.bicycle':
        return {'actor_id': r['actor_id'], 'machine_class': r['machine_class'],
                'body_vertices_m': n['native_body_vertices_m']}
    if name == 'ru.rider_posture':
        return {'mounted': None, 'original_pixel_review': 'pending'}
    if name == 'ru.pedestrian':
        return {'walking_machine': None, 'original_pixel_review': 'pending'}
    if name == 'ru.electric_bicycle':
        return {'selected_class': False, 'machine_class': r['machine_class']}
    if name == 'ru.electric_scooter':
        return {'selected_class': False, 'machine_class': r['machine_class']}
    if name == 'dev.regulatory_sign':
        return {'landmark_id': survey['landmark_id'],
                'authorization_proven': False}
    if name == 'dev.governs':
        return {'approach_road_id': survey['approach_road_id'],
                'approach_lane_id': survey['approach_lane_id'],
                'governance_review': 'pending'}
    if name == 'dev.position':
        return {'station_m': survey['landmark_station_m'],
                'original_pixel_review': 'pending'}
    if name == 'drv.turning':
        return {'behavior_requested': geometry['behavior'],
                'observed_destination_road_id': n['native_road_id'],
                'saved_geometry_matched': geometry['engineering_geometry_matched'],
                'physical_cause_confirmed': False}
    if name == 'kin.heading':
        return {'heading_deg': n['native_heading_deg']}
    if name == 'kin.speed':
        return {'velocity_mps': t.get('velocity_mps'), 'source': 'trace.jsonl'}
    if name == 'rel.occupies':
        return {'road_id': n['native_road_id'], 'lane_id': n['native_lane_id'],
                'body_vertices_m': n['native_body_vertices_m']}
    if name == 'native_body_pose_control':
        return n
    if name == 'camera_frame_join':
        return m
    raise ValueError('Unknown staged signed-turn channel: ' + name)


def finalize(attempt, output):
    root, target = Path(attempt), Path(output)
    if target.exists() or (root / 'result.json').exists():
        raise ValueError('Retain prior saved result; use a fresh attempt')
    review = audit_attempt(root)
    config = json.loads((root / 'config.json').read_text())
    description = config['recording_description']
    native = rows(root / 'native_samples.jsonl')
    mapping = rows(root / 'video_frames.jsonl')
    rider = rows(root / 'rider_native_samples.jsonl')
    trace = rows(root / 'trace.jsonl')
    survey = json.loads((root / 'sign-survey.json').read_text())
    geometry = review['geometry']
    if (root / 'channels').exists() or (root / 'context.json').exists():
        raise ValueError('Fixture-supplied derived observations are not accepted')
    (root / 'channels').mkdir()
    evidence = []
    for channel in description['channels']:
        name = channel['name']
        values = [{'time_s': n['time_s'],
                   'value': _channel(name, n, m, r, t, survey, geometry)}
                  for n, m, r, t in zip(native, mapping, rider, trace)]
        reference = 'channels/' + name + '.jsonl'
        _write_rows(root / reference, values)
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': reference})
    _write_json(root / 'context.json', {
        'signed_hill_crest': {'direction': config['direction'],
                              'source_kind': 'original_live_run',
                              'official_sign_authorization_verified': False,
                              'original_pixel_review': 'pending',
                              'legal_verdict_claimed': False}})
    for context in description.get('context_inputs', []):
        evidence.append({'name': context['name'], 'unit': context['unit'],
                         'reference': 'context.json'})
    result = {'case_id': config['case_id'],
              'measured_values': {'heading_change_deg': geometry['heading_change_deg'],
                                  'destination_road_id': geometry['destination_road_id'],
                                  'official_sign_authorization_verified': False},
              'target_checks': [{
                  'target': 'requested signed-turn behavior from observed original pose',
                  'requested': config['behavior'],
                  'measured': geometry['behavior'],
                  'method': 'saved original Native pose and road readback',
                  'tolerance': 'engineering route geometry only; no legal threshold',
                  'matched': geometry['engineering_geometry_matched'],
                  'physical_cause_confirmed': False,
                  'cause_evidence': ['native_samples.jsonl', 'sign-survey.json']}],
              'setup_confirmed': False, 'behavior_attempted': True,
              'maneuver_completed': geometry['engineering_geometry_matched'],
              'termination_reason': 'full original source duration retained',
              'physical_failure_flags': [
                  'original_posture_sign_authorization_and_pixels_unreviewed'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in review['cameras']],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': description,
              'recording_evidence': evidence,
              'realized_observables': {'signed_turn_geometry': geometry},
              'provenance_kind': 'native', 'accepted': False,
              'legal_verdict_claimed': False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report = {'format': 'c104538-staged-signed-turn-saved-v1',
              'case_id': config['case_id'], 'source_kind': 'original_live_run',
              'passed': True, 'accepted': False,
              'measurements': {'signed_turn_observation': measure_signed_turn(root, geometry)},
              'saved_review': review, 'original_pixel_review': 'pending',
              'legal_verdict_claimed': False}
    _write_json(target, report)
    _write_json(root / 'result.json', result)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
