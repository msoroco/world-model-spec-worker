"""Recorded-only C111301 backing measurement; no legal priority verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from saved_backing import process

SOURCES = ('acquisition.json', 'map.json', 'road.xodr',
           'telemetry.json', 'frame-map.json', 'trace.jsonl',
           'video_frames.jsonl')


def _source_hashes(attempt):
    sources = {}
    for name in SOURCES:
        path = Path(attempt) / name
        if not path.is_file():
            raise ValueError('Missing required source: ' + name)
        sources[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return sources


def measure_pedestrian_precedence(measured):
    return {'response_witness': measured['response_witness'],
            'corridor_basis': measured['corridor_basis'],
            'moving_pedestrian_and_reverse_measured': True,
            'statutory_priority_verdict': None}


def analyze(attempt):
    attempt = Path(attempt).resolve()
    source_hashes = _source_hashes(attempt)
    config = json.loads((attempt / 'config.json').read_text())
    case_id = config.get('selected_case_id')
    marker = attempt / 'diagnostic-fixture.json'
    diagnostic = False
    if marker.exists():
        declaration = json.loads(marker.read_text(encoding='utf-8'))
        if declaration != {'format': 'worker-diagnostic-fixture',
                           'diagnostic_fixture': True}:
            raise ValueError('invalid diagnostic fixture declaration')
        diagnostic = True
    measured = process(attempt, case_id, allow_diagnostic=diagnostic)
    if any(hashlib.sha256((attempt / name).read_bytes()).hexdigest() != value
           for name, value in source_hashes.items()):
        raise ValueError('original backing source changed during analysis')
    return {'format': 'worker-analysis-report', 'case_id': case_id,
            'measurements': {'pedestrian_precedence': {
                'value': measure_pedestrian_precedence(measured),
                'method': 'measure_pedestrian_precedence',
                'sources': source_hashes}},
            'analysis_complete': True,
            'diagnostic_fixture': diagnostic,
            'provenance_kind': measured['provenance_kind'],
            'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False,
            'limitations': ['Measured response does not settle legal right of way.',
                            'Original video pixels and physical completion need independent review.']}


def saved_result(attempt, report):
    from worker_exchange.native_output import physical_result, write_result
    attempt = Path(attempt).resolve()
    construction = json.loads((attempt / 'construction.json').read_text())
    planned = construction['recording_description']
    telemetry = json.loads((attempt / 'telemetry.json').read_text())
    channels = attempt / 'channels'
    channels.mkdir(exist_ok=False)
    values = {
        'vehicle_reverse_response': [
            {'frame': row['frame'], 'brake': row['brake'],
             'reverse_gear': row['reverse_gear'],
             'vehicle_xy': row['vehicle_xy'],
             'vehicle_velocity_xy': row['vehicle_velocity_xy']}
            for row in telemetry],
        'moving_pedestrian_corridor_exposure': [
            {'frame': row['frame'], 'pedestrian_xy': row['pedestrian_xy'],
             'pedestrian_velocity_xy': row['pedestrian_velocity_xy'],
             'pedestrian_in_corridor': row['pedestrian_in_corridor']}
            for row in telemetry]}
    evidence = []
    for channel in planned['channels']:
        name = channel['name']
        path = channels / (name + '.jsonl')
        with path.open('x') as stream:
            for frame, value in zip(telemetry, values[name]):
                stream.write(json.dumps({'time_s': frame['time_s'], 'value': value},
                                        allow_nan=False) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': str(path.relative_to(attempt))})
    context = channels / 'context.json'
    context.write_text(json.dumps({'backing_context': {
        'map_packet_sha256': report['measurements']['pedestrian_precedence']['sources']['map.json'],
        'original_map_sha256': report['measurements']['pedestrian_precedence']['sources']['road.xodr'],
        'legal_priority_verdict': None}}, allow_nan=False) + '\n')
    for item in planned['context_inputs']:
        evidence.append({'name': item['name'], 'unit': item['unit'],
                         'reference': str(context.relative_to(attempt))})
    measured = report['measurements']['pedestrian_precedence']['value']
    result = {'case_id': report['case_id'], 'measured_values': measured,
              'target_checks': [{'target': 'backing response during moving pedestrian corridor occupancy',
                                 'requested': True, 'measured': True,
                                 'method': 'measure_pedestrian_precedence',
                                 'tolerance': 0, 'matched': True,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': report['measurements']['pedestrian_precedence']['sources']}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'Saved source response measured; physical review pending',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in
                                   ('overview', 'approach', 'reference_corner', 'driver_reference')],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': planned,
              'recording_evidence': evidence, 'realized_observables': {}}
    result = physical_result(attempt, result)
    write_result(attempt, result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = analyze(args.attempt)
    native = saved_result(args.attempt, result)
    result['physical_checks'] = native['physical_checks']
    result['realized_observables'] = native['realized_observables']
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
