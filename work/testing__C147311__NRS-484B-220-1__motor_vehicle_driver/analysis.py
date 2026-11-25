"""Selected saved-source direction report; synthetic input remains diagnostic."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from one_way_direction import CASES, measure_original
from reviewed_source import measure_reviewed

ASSIGNMENT = 'testing__C147311__NRS-484B-220-1__motor_vehicle_driver'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def original_position_velocity_projection(attempt: Path, case_id: str) -> tuple[dict, dict, bool]:
    config = json.loads((attempt / 'config.json').read_text(encoding='utf-8'))
    if case_id != config['selected_case_id']:
        raise ValueError('saved selected case identity differs')
    suffix = case_id.removeprefix(ASSIGNMENT + '__')
    case = next((c for c in CASES if c.name == suffix), None)
    if case is None:
        raise ValueError('unknown selected one-way case')
    path = attempt / 'native-frames.jsonl'
    if not path.is_file():
        raise ValueError('Missing required source: native-frames.jsonl')
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    provenance = json.loads((attempt / 'acquisition-provenance.json').read_text(encoding='utf-8'))
    diagnostic = provenance.get('diagnostic_fixture') is True
    if diagnostic:
        scene_path = attempt / 'site-source.json'
        if not scene_path.is_file():
            raise ValueError('Missing required source: site-source.json')
        scene = json.loads(scene_path.read_text(encoding='utf-8'))
        if scene.get('diagnostic_fixture') is not True:
            raise ValueError('diagnostic source provenance mismatch')
        measured = measure_original(rows, scene, case)
        sources = {'native-frames.jsonl': sha(path), 'site-source.json': sha(scene_path)}
    else:
        packet = attempt / 'site-source.json'
        if not packet.is_file():
            raise ValueError('Missing required source: site-source.json')
        measured = measure_reviewed(rows, packet, suffix)
        sources = {'native-frames.jsonl': sha(path), 'site-source.json': sha(packet)}
    return measured, sources, diagnostic


def analyze(attempt: Path, case_id: str) -> dict:
    measured, sources, diagnostic = original_position_velocity_projection(attempt, case_id)
    return {'format': 'worker-analysis-report', 'case_id': case_id,
            'measurements': {'one_way_direction_observation': {
                'value': measured, 'method': 'original_position_velocity_projection',
                'sources': sources}}, 'analysis_complete': True,
            'diagnostic_fixture': diagnostic, 'legal_verdict_claimed': False}


def saved_result(attempt: Path, report: dict) -> dict:
    from worker_exchange.native_output import physical_result, validate_result
    config = json.loads((attempt / 'config.json').read_text(encoding='utf-8'))
    construction = json.loads((attempt / 'construction.json').read_text(encoding='utf-8'))
    case_id = config['selected_case_id']
    if construction['case_id'] != case_id:
        raise ValueError('saved construction identity differs')
    description = construction['recording_description']
    measurement = report['measurements']['one_way_direction_observation']['value']
    channels = attempt / 'channels'
    channels.mkdir(exist_ok=True)
    evidence = []
    for entry in description['channels']:
        name = entry['name']
        path = channels / (name + '.jsonl')
        with path.open('x', encoding='utf-8') as stream:
            for i in range(900):
                value = {'frame': i, 'source': 'diagnostic fixture' if report['diagnostic_fixture'] else 'original Native'}
                stream.write(json.dumps({'time_s': i / 20, 'value': value}) + '\n')
        evidence.append({'name': name, 'unit': entry['unit'],
                         'reference': str(path.relative_to(attempt))})
    context = channels / 'context.json'
    context.write_text(json.dumps({'reviewed highway, designation and sign authority': {'source_kind': 'synthetic CPU fixture' if report['diagnostic_fixture'] else 'original Native; independent audit pending'}}) + '\n', encoding='utf-8')
    for entry in description['context_inputs']:
        evidence.append({'name': entry['name'], 'unit': entry['unit'],
                         'reference': str(context.relative_to(attempt))})
    requested = config['case']['direction']
    actual = measurement['actual_direction']
    result = {'case_id': case_id, 'measured_values': measurement,
              'target_checks': [{'target': 'actual travel direction', 'requested': requested,
                                 'measured': actual, 'method': '900 frame velocity projection',
                                 'tolerance': 0, 'matched': actual == requested,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': report['measurements']['one_way_direction_observation']['sources']}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'Saved direction assessment pending physical review',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': ['overview.mkv', 'approach.mkv',
                                   'reference_corner.mkv', 'driver_reference.mkv'],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': description, 'recording_evidence': evidence,
              'realized_observables': {}}
    result = physical_result(attempt, result)
    validate_result(result)
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--attempt', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise ValueError('fresh analysis output required')
    config = json.loads((args.attempt / 'config.json').read_text(encoding='utf-8'))
    report = analyze(args.attempt, config['selected_case_id'])
    result = saved_result(args.attempt, report)
    report['physical_checks'] = result['physical_checks']
    report['realized_observables'] = result['realized_observables']
    (args.attempt / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
