"""Saved-only blind-person encounter finalization from original sources.

Engineering event measurements are retained without a legal verdict. The
independent attestation and observed carried cue remain separate sources.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from blind_encounter import CASE_BY_ID, measure_saved


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _source(root, name):
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    return path


def _json(root, name):
    return json.loads(_source(root, name).read_text(encoding='utf-8'))


def _rows(root, name):
    return [json.loads(line) for line in _source(root, name).read_text(encoding='utf-8').splitlines() if line]


def _measured(value, method, root, inputs):
    return {'value': value, 'method': method,
            'sources': {name: _sha(_source(root, name)) for name in inputs}}


def measure_approach(root, measurement, route, rows):
    return {'first_approach_frame': measurement['first_approach_frame'],
            'first_contact_frame': measurement['first_contact_frame'],
            'gap_at_approach_m': measurement['gap_at_approach_m'],
            'driver_actor_id': route['driver_actor_id'],
            'person_actor_id': measurement['person_actor_id'],
            'route_map_id': route['map_id'],
            'physical_acceptance': 'pending_original_review'}


def measure_protected_person(root, measurement, attestation, cue):
    return {'person_actor_id': measurement['person_actor_id'],
            'blindness_basis': attestation['basis'], 'attestation_issuer': attestation['issuer'],
            'actually_carried_cue': cue['cue'], 'observer_source': cue['observer_source'],
            'original_blindness_sha256': attestation['source_sha256'],
            'original_cue_sha256': cue['source_sha256']}


def measure_full_stop(root, measurement, route, rows):
    return {'first_approach_frame': measurement['first_approach_frame'],
            'first_stop_frame': measurement['first_stop_frame'],
            'minimum_speed_mps': min(row['driver_speed_mps'] for row in rows),
            'immediacy_legal_judgment': 'unresolved'}


def measure_precautions(root, measurement, route, rows):
    return {'first_proceed_frame': measurement['first_proceed_frame'],
            'person_clear_at_proceed': measurement['person_clear_at_proceed'],
            'precaution_at_proceed': measurement['precaution_at_proceed'],
            'necessity_legal_judgment': 'unresolved'}


def measure_consequence(root, measurement, route, rows):
    return {'contact_frames': [row['frame'] for row in rows if row['contact']],
            'observed_injury_frames': [row['frame'] for row in rows if row.get('injury_observed') is True],
            'injury_source_limit': 'Original contact history alone cannot establish absence of injury.'}


def build(root):
    config = _json(root, 'config.json')
    case_id = config['selected_case_id']
    suffix = case_id.removeprefix(config['assignment_id'] + '__')
    if case_id != config['assignment_id'] + '__' + suffix or suffix not in CASE_BY_ID:
        raise ValueError('Wrong exact encounter case')
    rows = _rows(root, 'original-history.jsonl')
    frame_map = _rows(root, 'video_frames.jsonl')
    if len(rows) != len(frame_map) or any(row['frame'] != frame['carla_frame'] or
            abs(row['time_s'] - frame['time_s']) > 1e-6 for row, frame in zip(rows, frame_map)):
        raise ValueError('Original history and camera frame join differs')
    att = _json(root, 'blindness-attestation.json')
    cue = _json(root, 'carried-cue.json')
    route = _json(root, 'reviewed-map-route.json')
    if att.get('basis') not in ('wholly_blind', 'partially_blind') or not att.get('issuer'):
        raise ValueError('Independent blindness attestation is incomplete')
    if cue.get('observation') != 'actually_carried' or not cue.get('observer_source') or cue.get('cue') != CASE_BY_ID[suffix].cue:
        raise ValueError('Actually carried cue source is incomplete')
    if route.get('driver_actor_id') == route.get('pedestrian_actor_id') or route.get('pedestrian_actor_id') != att.get('person_actor_id'):
        raise ValueError('Reviewed map actor identity differs')
    measurement = measure_saved(suffix, rows, attestation=att, cue_source=cue)
    if measurement['person_actor_id'] != route['pedestrian_actor_id']:
        raise ValueError('Original history person identity differs from reviewed route')
    methods = [measure_approach, measure_protected_person, measure_full_stop,
               measure_precautions, measure_consequence]
    inputs = [
        ['original-history.jsonl', 'video_frames.jsonl', 'reviewed-map-route.json'],
        ['blindness-attestation.json', 'carried-cue.json'],
        ['original-history.jsonl', 'video_frames.jsonl'],
        ['original-history.jsonl', 'video_frames.jsonl'],
        ['original-history.jsonl']]
    values = [method(root, measurement, att, cue) if method is measure_protected_person else
              method(root, measurement, route, rows) for method in methods]
    names = ['approach_contact_measurement', 'protected_person_measurement',
             'full_stop_measurement', 'precaution_measurement', 'consequence_measurement']
    report = {'format': 'worker-analysis-report', 'case_id': case_id,
              'measurements': {name: _measured(value, method.__name__, root, source)
                               for name, value, method, source in zip(names, values, methods, inputs)},
              'analysis_complete': True, 'legal_verdict_claimed': False,
              'limitations': ['Immediacy and necessary precautions require legal review.',
                              'Physical actor motion, carried cue and injury need original review.']}
    return report, rows, frame_map, measurement


def result_from_saved(root, report, rows, frame_map, measurement):
    from worker_exchange.native_output import physical_result, validate_result
    config = _json(root, 'config.json')
    construction = _json(root, 'construction.json')
    planned = construction['recording_description']
    channels = root / 'channels'
    channels.mkdir(exist_ok=True)
    streams = {
        'driver_speed_mps': [r['driver_speed_mps'] for r in rows],
        'body_gap_m': [r['body_gap_m'] for r in rows],
        'precaution_observation': [{'person_clear': r['person_clear'], 'precaution': r['precaution']} for r in rows],
        'contact_observation': [r['contact'] for r in rows],
        'original_camera_frames': frame_map}
    evidence = []
    for channel in planned['channels']:
        name = channel['name']
        if name not in streams:
            raise ValueError('Unsupported planned channel: ' + name)
        path = channels / (name + '.jsonl')
        with path.open('x', encoding='utf-8') as stream:
            for row, value in zip(rows, streams[name]):
                stream.write(json.dumps({'time_s': row['time_s'], 'value': value}, allow_nan=False) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': str(path.relative_to(root))})
    context_path = channels / 'context.json'
    context_path.write_text(json.dumps({
        'blindness_attestation': _json(root, 'blindness-attestation.json'),
        'reviewed_map_route': _json(root, 'reviewed-map-route.json'),
        'carried_cue': _json(root, 'carried-cue.json')}, allow_nan=False) + '\n')
    for context in planned['context_inputs']:
        name = context['name']
        evidence.append({'name': name, 'unit': context['unit'],
                         'reference': str(context_path.relative_to(root))})
    target = measurement['first_approach_frame'] is not None
    result = {'case_id': config['selected_case_id'], 'measured_values': measurement,
              'target_checks': [{'target': 'source-bound protected-person approach',
                                 'requested': True, 'measured': target,
                                 'method': 'measure_approach', 'tolerance': 0,
                                 'matched': target, 'physical_cause_confirmed': False,
                                 'cause_evidence': report['measurements']['approach_contact_measurement']['sources']}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'Original saved source assessment; physical review pending',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': ['overview.mkv', 'approach.mkv',
                                   'reference_corner.mkv', 'driver_reference.mkv'],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': planned, 'recording_evidence': evidence,
              'realized_observables': {}}
    result = physical_result(root, result)
    validate_result(result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.attempt.resolve()
    report, rows, frame_map, measurement = build(root)
    result = result_from_saved(root, report, rows, frame_map, measurement)
    report['physical_checks'] = result['physical_checks']
    report['realized_observables'] = result['realized_observables']
    (root / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
