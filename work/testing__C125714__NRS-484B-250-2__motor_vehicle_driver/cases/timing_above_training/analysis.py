"""Saved-only selected C125714 analysis and canonical Native result writer."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from saved_finalizer import finalize

CASE = 'testing__C125714__NRS-484B-250-2__motor_vehicle_driver__timing_above_training'
MEASUREMENT = ('road.xodr', 'site-context.json', 'ego-body-history.jsonl',
               'other-body-history.jsonl', 'video_frames.jsonl', 'trace.jsonl')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]


def required(root, name):
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    return path


def measure_original(root, diagnostic_fixture=False):
    """Use the same sealed entry algorithm in real and diagnostic modes."""
    return finalize(root, CASE, diagnostic_fixture=diagnostic_fixture)


def build_report(root):
    root = Path(root).resolve()
    for name in MEASUREMENT:
        required(root, name)
    provenance = json.loads(required(root, 'acquisition-provenance.json').read_text())
    native = provenance.get('provenance_kind') == 'native' and provenance.get('diagnostic_fixture') is False
    diagnostic = provenance.get('provenance_kind') == 'synthetic_fixture' and provenance.get('diagnostic_fixture') is True
    if not native and not diagnostic:
        raise ValueError('contradictory acquisition provenance')
    diagnostic_value = measure_original(root, diagnostic_fixture=diagnostic)
    mapping, trace = rows(root / 'video_frames.jsonl'), rows(root / 'trace.jsonl')
    ego, other = rows(root / 'ego-body-history.jsonl'), rows(root / 'other-body-history.jsonl')
    if not (len(mapping) == len(trace) == len(ego) == len(other)):
        raise ValueError('full original frame count differs')
    for frame, (m, t, e, o) in enumerate(zip(mapping, trace, ego, other)):
        if (m.get('video_frame') != frame or
                (m.get('carla_frame'), m.get('time_s')) != (t.get('frame'), t.get('time_s')) or
                (e.get('frame'), e.get('time_s')) != (t.get('frame'), t.get('time_s')) or
                (o.get('frame'), o.get('time_s')) != (t.get('frame'), t.get('time_s'))):
            raise ValueError('original trace/video/body time join differs')
    return {'format': 'worker-analysis-report', 'analysis_complete': True,
            'measurements': {'c125714_selected_entry_timing': {
                'value': diagnostic_value, 'method': 'measure_original',
                'sources': {name: sha(root / name) for name in MEASUREMENT}}},
            'provenance_kind': 'synthetic_fixture' if diagnostic else 'native',
            'limitations': ['Training target is not a legal approximately-same-time threshold.',
                            'Fixture motion and pixels cannot establish physical or legal acceptance.'],
            'legal_verdict_claimed': False}


def write_native_result(root, report):
    from worker_exchange.native_output import physical_result, write_result
    root = Path(root).resolve()
    config = json.loads((root / 'config.json').read_text())
    if config.get('selected_case_id') != CASE:
        raise ValueError('materialized selected case differs')
    description = config['case']['recording_description']
    diagnostic = report['measurements']['c125714_selected_entry_timing']['value']
    values = {'ego_original_footprint': [
                  {'time_s': row['time_s'], 'value': row['body_vertices_xy_m']}
                  for row in rows(root / 'ego-body-history.jsonl')],
              'other_original_footprint': [
                  {'time_s': row['time_s'], 'value': row['body_vertices_xy_m']}
                  for row in rows(root / 'other-body-history.jsonl')],
              'intersection_entry_time_difference_s': [
                  {'time_s': diagnostic['ego_entry']['upper_time_s'],
                   'value': diagnostic['measured_value_s']} ]}
    channel_dir = root / 'channels'
    channel_dir.mkdir(exist_ok=True)
    evidence = []
    for channel in description['channels']:
        name = channel['name']
        path = channel_dir / (name + '.jsonl')
        with path.open('x') as stream:
            for row in values[name]:
                stream.write(json.dumps(row, allow_nan=False) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': str(path.relative_to(root))})
    context_path = channel_dir / 'context.json'
    context_path.write_text(json.dumps({'reviewed_crossing': {
        'map_sha256': sha(root / 'road.xodr'),
        'site_context_sha256': sha(root / 'site-context.json')}}) + '\n')
    for context in description['context_inputs']:
        evidence.append({'name': context['name'], 'unit': context['unit'],
                         'reference': str(context_path.relative_to(root))})
    result = {'case_id': CASE, 'measured_values': diagnostic,
              'target_checks': [{'target': 'requested training entry offset',
                'requested': config['case']['requested_entry_offset_s'],
                'measured': diagnostic['measured_value_s'],
                'method': 'sealed original footprint entry transition',
                'tolerance': .05,
                'matched': abs(diagnostic['measured_value_s'] -
                               config['case']['requested_entry_offset_s']) <= .05,
                'physical_cause_confirmed': False,
                'cause_evidence': report['measurements']['c125714_selected_entry_timing']['sources']}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'Saved evidence assessment pending',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': ['overview.mkv', 'approach.mkv',
                                   'reference_corner.mkv', 'driver_reference.mkv'],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': description, 'recording_evidence': evidence,
              'realized_observables': {}}
    result = physical_result(root, result)
    write_result(root, result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = build_report(args.attempt)
    result = write_native_result(args.attempt, report)
    report['physical_checks'] = result['physical_checks']
    report['realized_observables'] = result['realized_observables']
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
