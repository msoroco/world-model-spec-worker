"""Saved-only, source-bound outside-lane measurements; no legal evaluator."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from outside_lane import CASES, measure_original


def source(root: Path, name: str) -> Path:
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    return path


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def source_sealed_lane_measurement(value):
    return value


def analyze(attempt: Path) -> dict:
    root = Path(attempt).resolve()
    config = json.loads(source(root, 'config.json').read_text())
    case_id = config['selected_case_id']
    suffix = case_id.split('__')[-1]
    exact = next((case for case in CASES if case.name == suffix), None)
    if exact is None:
        raise ValueError('unknown selected lane case')
    receipt = json.loads(source(root, 'original-source-receipt.json').read_text())
    diagnostic = receipt.get('diagnostic_fixture') is True
    if receipt.get('case_id') != case_id or receipt.get('source_kind') != (
            'synthetic_diagnostic_fixture' if diagnostic else 'original_native_capture'):
        raise ValueError('exact original/diagnostic source receipt differs')
    inputs = ('original-history.jsonl', 'original-source-receipt.json', 'trace.jsonl')
    if receipt.get('history_sha256') != digest(source(root, inputs[0])):
        raise ValueError('sealed original history differs')
    for key, name in (('trace_sha256', 'trace.jsonl'), ('frame_map_sha256', 'video_frames.jsonl')):
        if receipt.get(key) != digest(source(root, name)):
            raise ValueError('sealed original source differs: ' + key)
    rows = [json.loads(line) for line in source(root, 'original-history.jsonl').read_text().splitlines()]
    trace = [json.loads(line) for line in source(root, 'trace.jsonl').read_text().splitlines()]
    frame_map = [json.loads(line) for line in source(root, 'video_frames.jsonl').read_text().splitlines()]
    if not (len(rows) == len(trace) == len(frame_map) == receipt.get('frame_count')) or len(rows) < 2:
        raise ValueError('original source row count differs')
    if not diagnostic and len(rows) != 900:
        raise ValueError('original Native history needs 900 frames')
    for index, (row, motion, mapped) in enumerate(zip(rows, trace, frame_map)):
        native = row['original_frame']
        if not (native == motion['frame'] == mapped['carla_frame'] and mapped['video_frame'] == index):
            raise ValueError('original vehicle/trace/video frame join differs')
        if 'speed_mps' in motion and abs(motion['speed_mps'] - row['ego_speed_mps']) > 1e-5:
            raise ValueError('original speed source differs')
    measured = measure_original(rows, exact)
    values = {
        'controlled_access_authority': {
            'source_sha256': measured['fixed']['legal_controlled_access_source_sha256'],
            'public_boundary_sha256': measured['fixed']['public_highway_boundary_source_sha256']},
        'public_highway_boundary': {
            'source_sha256': measured['fixed']['public_highway_boundary_source_sha256']},
        'lane_function': {'source_sha256': measured['fixed']['lane_function_source_sha256'],
                          'origin': measured['fixed']['origin'],
                          'destination': measured['fixed']['destination']},
        'solid_white_separator': {
            'source_sha256': measured['fixed']['separator_source_sha256'],
            'kind': measured['fixed']['separator_kind'],
            'route_id': measured['fixed']['route_id']},
        'vehicle_body_line_relation': {
            'samples': measured['samples'], 'frame_count': measured['frame_count'],
            'center_crossing_observed': measured['center_crossing_observed'],
            'body_line_contact_observed': measured['body_line_contact_observed']},
        'vehicle_class_and_driver': {
            'source_sha256': measured['fixed']['vehicle_class_source_sha256'],
            'vehicle_class': measured['fixed']['vehicle_class'],
            'ego_id': measured['fixed']['ego_id']},
        'emergency_necessity': {
            'required': measured['emergency_required'],
            'source_sha256': measured['fixed']['emergency_record_source_sha256']},
        'subsection3_shoulder_scope': {
            'authorized': measured['subsection3_shoulder_authorized'],
            'source_sha256': measured['fixed']['subsection3_authorization_source_sha256'],
            'paved_shoulder_source_sha256': measured['fixed']['paved_shoulder_source_sha256'],
            'lawful_sign_source_sha256': measured['fixed']['lawful_shoulder_sign_source_sha256'],
            'shoulder_paved': measured['shoulder_paved'],
            'lawful_sign_permits_shoulder': measured['lawful_sign_permits_shoulder'],
            'crossing_permission_inferred': False},
    }
    hashes = {name: digest(source(root, name)) for name in inputs}
    measurements = {name: {'method': 'source_sealed_lane_measurement',
                           'value': source_sealed_lane_measurement(value), 'sources': hashes}
                    for name, value in values.items()}
    evidence = []
    for channel in config['recording_description']['channels']:
        name = channel['name']
        output = root / ('channel-' + name + '.jsonl')
        value = values.get(name, {'source_sha256': hashes['original-history.jsonl'],
                                  'case': suffix})
        content = ''.join(json.dumps({'time_s': i / 20, 'value': value}, sort_keys=True) + '\n'
                          for i in range(len(rows)))
        if output.exists():
            if output.read_text() != content:
                raise ValueError('derived channel differs from saved source: ' + name)
        else:
            output.write_text(content)
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': output.name})
    context = root / 'channel-reviewed_controlled_access_site.json'
    context_value = {'reviewed_controlled_access_site': {
        'map_sha256': measured['fixed']['map_sha256'],
        'authority_sha256': measured['fixed']['legal_controlled_access_source_sha256']}}
    context_content = json.dumps(context_value, sort_keys=True) + '\n'
    if context.exists():
        if context.read_text() != context_content:
            raise ValueError('reviewed site context differs from saved source')
    else:
        context.write_text(context_content)
    evidence.append({'name': 'reviewed_controlled_access_site', 'unit': 'source record',
                     'reference': context.name})
    from worker_exchange.native_output import physical_result, write_result
    result = {'case_id': case_id, 'measured_values': values,
              'target_checks': [{'target': 'source-specified separator crossing route',
                                 'requested': exact.origin != exact.destination,
                                 'measured': measured['center_crossing_observed'],
                                 'method': 'original vehicle center and body vertices relative to sourced solid-white separator',
                                 'tolerance': 0,
                                 'matched': measured['center_crossing_observed'] == (exact.origin != exact.destination),
                                 'physical_cause_confirmed': False, 'cause_evidence': hashes}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False, 'termination_reason': 'independent physical review pending',
              'physical_failure_flags': ['physical_acceptance_unverified'],
              'trace_reference': 'trace.jsonl',
              'video_references': ['overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv'],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'diagnostic_fixture': diagnostic, 'physical_acceptance_claimed': False,
              'legal_verdict_claimed': False}
    result = physical_result(root, result)
    write_result(root, result)
    return {'format': 'worker-analysis-report', 'case_id': case_id,
            'analysis_complete': True, 'diagnostic_fixture': diagnostic,
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
            'measurements': measurements, 'physical_checks': result['physical_checks'],
            'realized_observables': result['realized_observables'],
            'limitations': ['Original pixels and legal source qualification need independent review.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior analysis report')
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + '\n')
