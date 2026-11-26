"""Saved-only original measurement for the exact grade-standing case."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from grade_stand import measure_original
from source_packet import SOURCE_FIELDS, verify


def required(root, name):
    path = Path(root) / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def measure_saved(root):
    root = Path(root)
    config = json.loads(required(root, 'config.json').read_text())
    construction = json.loads(required(root, 'construction.json').read_text())
    diagnostic = (root / 'fixture-provenance.json').is_file()
    required(root, 'engine.txt')
    packet = required(root, 'reviewed-packet.json' if diagnostic else
                      'source-packet.json')
    checked = verify(packet, diagnostic_fixture=diagnostic)
    case_id = checked['case_id']
    if (case_id != config.get('selected_case_id') or
            case_id != construction.get('case_id')):
        raise ValueError('saved grade-standing case identity differs')
    rows = read_rows(required(root, 'original-ticks.jsonl'))
    trace = read_rows(required(root, 'trace.jsonl'))
    frame_map = read_rows(required(root, 'video_frames.jsonl'))
    expected = 9 if diagnostic else 900
    if len(trace) != expected or len(frame_map) != expected:
        raise ValueError('saved original frame/video history incomplete')
    for row, state, frame in zip(rows, trace, frame_map):
        original = row.get('original_frame')
        if (state.get('frame') != original or
                frame.get('carla_frame') != original or
                state.get('time_s') != row.get('time_s') or
                frame.get('time_s') != row.get('time_s')):
            raise ValueError('saved original frame/time join differs')
    measurement = measure_original(rows, checked['scene'], checked['case'],
                                   diagnostic_fixture=diagnostic)
    for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
        required(root, name + '.mkv')
    return case_id, measurement, rows, construction, checked


def analyze(attempt, output):
    root = Path(attempt)
    case_id, measurement, rows, construction, checked = measure_saved(root)
    names = (('reviewed-packet.json' if checked['source_kind'] == 'diagnostic_fixture'
              else 'source-packet.json'), 'original-ticks.jsonl', 'trace.jsonl',
             'video_frames.jsonl', *(field + '.txt' for field in SOURCE_FIELDS))
    hashes = {name: sha(required(root, name)) for name in names}
    source_hashes = checked['source_hashes']
    values = {
        'vehicle_highway_grade': {
            'grade_percent': measurement['grade_percent'],
            'perceptible_grade_judgment': None,
            'highway_source_sha256': source_hashes['highway'],
            'grade_source_sha256': source_hashes['grade']},
        'attendance_transition': {
            'standing_frame_count': measurement['standing_frame_count'],
            'max_person_distance_m': measurement['max_person_distance_m'],
            'unattended_judgment': None,
            'person_actions_source_sha256': source_hashes['person_actions']},
        'engine_state': {
            'max_engine_rpm': measurement['max_engine_rpm'],
            'source_sha256': hashes['original-ticks.jsonl']},
        'brake_mechanics': {
            'min_brake_torque_nm': measurement['min_brake_torque_nm'],
            'effective_brake_judgment': None,
            'source_sha256': hashes['original-ticks.jsonl']},
        'front_wheel_orientation': {
            'wheels_toward_request': checked['case'].wheels_toward,
            'source_sha256': hashes['original-ticks.jsonl']},
    }
    reports = {key: {'method': 'measure_saved', 'value': value, 'sources': hashes}
               for key, value in values.items()}
    report = {'format': 'worker-analysis-report', 'case_id': case_id,
              'measurements': reports,
              'diagnostic_fixture': checked['source_kind'] == 'diagnostic_fixture',
              'legal_verdict_claimed': False,
              'limitations': [
                  'Perceptibility, unattended status and effective brake are unresolved judgments.',
                  'Original camera bytes and physical effect require independent local audit.']}
    channels = root / 'channels'
    channels.mkdir(exist_ok=False)
    observed = {
        'grade_geometry': values['vehicle_highway_grade'],
        'standing_motion': values['attendance_transition'],
        'mechanical_state': {'engine': values['engine_state'],
                             'brake': values['brake_mechanics'],
                             'front_wheels': values['front_wheel_orientation']},
        'person_activity': values['attendance_transition'],
        'other_vehicle_motion': {'other_vehicle_id': rows[0]['other_id'],
                                 'source_sha256': hashes['original-ticks.jsonl']},
        'camera_pixels': {'views': ['overview', 'approach', 'reference_corner',
                                    'driver_reference'],
                          'source_sha256': hashes['video_frames.jsonl']},
    }
    evidence = []
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        if name not in observed:
            raise ValueError('unexpected grade-standing channel: ' + name)
        target = channels / (name + '.jsonl')
        target.write_text(''.join(json.dumps({'time_s': row['time_s'],
                                             'value': observed[name]}) + '\n'
                                  for row in rows))
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': str(target.relative_to(root))})
    for context in construction['recording_description']['context_inputs']:
        name = context['name']
        target = channels / ('context_' + name + '.jsonl')
        target.write_text(json.dumps({name: {
            'source_sha256': source_hashes[name],
            'review_status': ('synthetic' if checked['source_kind'] ==
                              'diagnostic_fixture' else 'reviewed')}}) + '\n')
        evidence.append({'name': name, 'unit': context['unit'],
                         'reference': str(target.relative_to(root))})
    result = {'case_id': case_id, 'measured_values': values,
              'target_checks': [{'target': 'source-bound standing and preparation',
                                 'requested': case_id, 'measured': values,
                                 'method': 'analysis.measure_saved', 'tolerance': 0,
                                 'matched': True, 'physical_cause_confirmed': False,
                                 'cause_evidence': hashes}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'Saved original physical review pending',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in
                                   ('overview', 'approach', 'reference_corner',
                                    'driver_reference')],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'legal_judgment': None, 'physical_acceptance_claimed': False}
    (root / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    Path(output).write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(analyze(args.attempt, args.output)['case_id'])
