"""Saved-only, source-bound trail analysis and canonical observation streams.

Diagnostic fixtures exercise software joins. A positive source join does not
establish sign adequacy, physical visibility, or legal compliance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from saved_source_finalizer import finalize


INPUTS = ('acquisition.json', 'original-history.jsonl',
          'original-history-packets.jsonl')
KEYS = ('trail_corridor_entry', 'official_plan_designation',
        'city_trail_dedication', 'prohibits_motor_vehicles',
        'sign_face_readback', 'emergency_use', 'maintenance_use')
VIDEOS = ('overview.mkv', 'approach.mkv',
          'reference_corner.mkv', 'driver_reference.mkv')


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def report(attempt: Path) -> dict:
    attempt = Path(attempt).resolve()
    for name in INPUTS:
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    case_id = config['selected_case_id']
    source = finalize(attempt, case_id)
    hashes = {name: _sha(attempt / name) for name in INPUTS}
    values = {}
    for key in KEYS:
        item = source['measurements'][key]
        values[key] = {'method': 'report', 'value': item['value'], 'sources': hashes}
    return {'format': 'worker-analysis-report', 'case_id': case_id,
            'measurements': values, 'analysis_complete': True,
            'diagnostic_fixture': source['diagnostic_fixture'],
            'physical_acceptance': False, 'legal_verdict_claimed': False,
            'source_join_sha256': source['acquisition_sha256'],
            'limitations': ['Original administrative authority, actual pixels and legal sufficiency require independent review.']}


def saved_result(attempt: Path, analysis: dict) -> dict:
    from worker_exchange.native_output import physical_result, validate_result

    attempt = Path(attempt).resolve()
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    planned = construction['recording_description']
    history = _rows(attempt / 'original-history.jsonl')
    mapping = _rows(attempt / 'video_frames.jsonl')
    trace = _rows(attempt / 'trace.jsonl')
    if len(history) != 900 or len(mapping) != 900 or len(trace) != 900:
        raise ValueError('original 900-frame trail/trace/camera map missing')
    if any(h['original_frame'] != m['carla_frame'] or
           h['original_frame'] != t['frame'] or
           abs(h['time_s'] - m['time_s']) > 1e-6 or
           abs(h['time_s'] - t['time_s']) > 1e-6
           for h, m, t in zip(history, mapping, trace)):
        raise ValueError('original trail/trace/camera frame join differs')
    context = json.loads((attempt / 'acquisition.json').read_text())
    stream_values = {
        'original_vehicle_position': [t['position_m'][:2] for t in trace],
        'trail_administrative_context': [{
            'official_plan_designation': h['official_plan_designation'],
            'city_trail_dedication': h['city_trail_dedication']} for h in history],
        'sign_face_and_access': [{
            'sign_face_visible': h['sign_face_visible'],
            'prohibits_motor_vehicles': h['prohibits_motor_vehicles']} for h in history],
        'exception_use': [{
            'emergency_use': h['emergency_use'],
            'maintenance_use': h['maintenance_use']} for h in history],
    }
    channels = attempt / 'channels'
    channels.mkdir(exist_ok=False)
    evidence = []
    for channel in planned['channels']:
        name = channel['name']
        values = stream_values[name]
        path = channels / (name + '.jsonl')
        with path.open('x') as stream:
            for row, value in zip(history, values):
                stream.write(json.dumps({'time_s': row['time_s'], 'value': value},
                                        allow_nan=False) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': str(path.relative_to(attempt))})
    context_path = channels / 'trail_source_packet.json'
    context_path.write_text(json.dumps({'trail_source_packet': context,
                                        'diagnostic_fixture': analysis['diagnostic_fixture']},
                                       allow_nan=False) + '\n')
    evidence.append({'name': 'trail_source_packet', 'unit': 'source',
                     'reference': str(context_path.relative_to(attempt))})
    result = {'case_id': config['selected_case_id'],
              'measured_values': {key: item['value'] for key, item in analysis['measurements'].items()},
              'target_checks': [{'target': 'original trail corridor entry',
                                 'requested': True,
                                 'measured': analysis['measurements']['trail_corridor_entry']['value'],
                                 'method': 'source-joined original XY inside reviewed corridor',
                                 'tolerance': 0,
                                 'matched': analysis['measurements']['trail_corridor_entry']['value'] is True,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': 'original pixels and source authority require independent review'}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'Saved sources assessed; legal and pixel review pending',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': list(VIDEOS),
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': planned, 'recording_evidence': evidence,
              'realized_observables': {}}
    result = physical_result(attempt, result)
    validate_result(result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    attempt = args.attempt.resolve()
    output = args.output.resolve()
    if output.parent != attempt or output.exists() or (attempt / 'result.json').exists():
        raise ValueError('fresh analysis output and result required inside attempt')
    value = report(attempt)
    result = saved_result(attempt, value)
    (attempt / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    output.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
