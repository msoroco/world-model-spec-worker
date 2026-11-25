"""Saved-only diagonal instruction measurement for current-runtime compatibility."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from crossing_audit import audit_history
from saved_crossing import CAMERAS


SOURCES = ('diagonal-source.json', 'walker-diagonal.jsonl',
           'device-diagonal.jsonl', 'camera-frame-joins.jsonl',
           'trace.jsonl', 'video_frames.jsonl')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = root / name
    if not path.is_file() or not path.stat().st_size:
        raise ValueError('Missing required source: ' + name)
    return path


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def measure_diagonal_instruction(source, walker, device):
    plan = {'start_xy': source['start_xy'], 'destination_xy': source['destination_xy'],
            'device_id': source['device_id'],
            'source_sha256': source['source_sha256'],
            'exception_484b_290_review': source['exception_484b_290_review']}
    return audit_history(plan, source['crossing_polygon'], walker, device)


def build_report(root):
    marker = json.loads(required(root, 'acquisition-provenance.json').read_text())
    if (marker.get('provenance_kind'), marker.get('diagnostic_fixture')) not in (
            ('synthetic_fixture', True), ('native', False)):
        raise ValueError('contradictory acquisition provenance')
    paths = {name: required(root, name) for name in SOURCES}
    for name in CAMERAS:
        required(root, name + '.mkv')
    source = json.loads(paths['diagonal-source.json'].read_text())
    config = json.loads(required(root, 'config.json').read_text())
    if source.get('case_id') != config['selected_case_id']:
        raise ValueError('diagonal source case differs')
    walker = rows(paths['walker-diagonal.jsonl'])
    device = rows(paths['device-diagonal.jsonl'])
    joins = rows(paths['camera-frame-joins.jsonl'])
    trace = rows(paths['trace.jsonl'])
    mapping = rows(paths['video_frames.jsonl'])
    if min(map(len, (walker, device, joins, trace, mapping))) < 3 or len({len(walker), len(device), len(joins), len(trace), len(mapping)}) != 1:
        raise ValueError('incomplete diagonal original frame groups')
    for i, (w, d, join, motion, frame_map) in enumerate(zip(walker, device, joins, trace, mapping)):
        frame = frame_map['carla_frame']
        time_s = frame_map['time_s']
        if frame_map['video_frame'] != i or any(row.get('original_frame', row.get('frame')) != frame
                                              for row in (w, d, join, motion)):
            raise ValueError('original diagonal frame join differs')
        if any(abs(row.get('time_s', time_s) - time_s) > 1e-6 for row in (w, d, join, motion)):
            raise ValueError('original diagonal time join differs')
        if set(join.get('cameras', {})) != set(CAMERAS) or any(
                join['cameras'][name]['frame'] != frame for name in CAMERAS):
            raise ValueError('four original diagonal cameras missing')
    measured = measure_diagonal_instruction(source, walker, device)
    states = measured['observed_instructions']
    suffix = config['selected_case_id'].split('__')[-1]
    if suffix == 'permissive_whole_crossing' and set(states) != {'diagonal_walk'}:
        raise ValueError('permissive instruction contrast absent')
    if suffix == 'prohibitive_whole_crossing' and set(states) != {'diagonal_dont_walk'}:
        raise ValueError('prohibitive instruction contrast absent')
    if suffix == 'instruction_changes_during_crossing' and not (
            states[0] == 'diagonal_walk' and 'diagonal_dont_walk' in states[1:]):
        raise ValueError('phase change absent')
    measurement_sources = ('diagonal-source.json', 'walker-diagonal.jsonl',
                           'device-diagonal.jsonl', 'camera-frame-joins.jsonl')
    report = {'format': 'worker-analysis-report', 'analysis_complete': True,
              'case_id': config['selected_case_id'],
              'provenance_kind': marker['provenance_kind'],
              'diagnostic_fixture': marker['diagnostic_fixture'],
              'measurements': {'diagonal_crossing_device_history': {
                  'method': 'measure_diagonal_instruction', 'value': measured,
                  'sources': {name: sha(paths[name]) for name in measurement_sources}}},
              'legal_verdict_claimed': False,
              'limitations': ['Synthetic fixture is software-only.',
                              'Official diagonal authorization and NRS 484B.290 exception remain source-gated.']}
    return report, config, walker, trace


def saved_result(root, report, config, walker, trace):
    safe = next((parent for parent in root.parents if parent.name == '.runtime-work'), None)
    if safe is None:
        raise ValueError('analysis attempt must be under .runtime-work')
    os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(safe.resolve())
    from worker_exchange.native_output import physical_result, validate_result
    description = config['case']['recording_description']
    construction = json.loads(required(root, 'construction.json').read_text())
    if description != construction['recording_description']:
        raise ValueError('recording description differs from exact construction')
    measured = report['measurements']['diagonal_crossing_device_history']['value']
    folder = root / 'channels'
    folder.mkdir(exist_ok=True)
    series = {
        'walker_center_xy': [(row['time_s'], row['center_xy']) for row in walker],
        'governing_diagonal_instruction': [(row['time_s'], row['instruction'])
                                           for row in rows(root / 'device-diagonal.jsonl')],
        'camera_original_frame_map': [(row['time_s'], row['cameras'])
                                      for row in rows(root / 'camera-frame-joins.jsonl')],
    }
    evidence = []
    for item in description['channels']:
        name = item['name']
        path = folder / (name + '.jsonl')
        with path.open('x') as stream:
            for time_s, value in series[name]:
                stream.write(json.dumps({'time_s': time_s, 'value': value}) + '\n')
        evidence.append({'name': name, 'unit': item['unit'],
                         'reference': str(path.relative_to(root))})
    context = {'reviewed_original_diagonal_site': {'source_sha256': measured['source_sha256']},
               'NRS_484B_290_exception': measured['exception_484b_290_review']}
    context_path = folder / 'context.json'
    context_path.write_text(json.dumps(context) + '\n')
    for item in description['context_inputs']:
        evidence.append({'name': item['name'], 'unit': item['unit'],
                         'reference': str(context_path.relative_to(root))})
    target = {'target': 'source-bound diagonal instruction through observed crossing',
              'requested': True, 'measured': measured,
              'method': 'original walker and governing-device frame joins',
              'tolerance': 0, 'matched': True,
              'physical_cause_confirmed': False,
              'cause_evidence': report['measurements']['diagonal_crossing_device_history']['sources']}
    result = {'case_id': config['selected_case_id'], 'measured_values': measured,
              'target_checks': [target], 'setup_confirmed': False,
              'behavior_attempted': False, 'maneuver_completed': False,
              'termination_reason': 'Saved original source review pending',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': description, 'recording_evidence': evidence,
              'realized_observables': {}}
    result = physical_result(root, result)
    validate_result(result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    root = Path(args.attempt).resolve()
    report, config, walker, trace = build_report(root)
    result = saved_result(root, report, config, walker, trace)
    report['physical_checks'] = result['physical_checks']
    report['realized_observables'] = result['realized_observables']
    (root / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    Path(args.output).write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
