"""Saved right-pass source analysis for diagnostic and original Native attempts.

The diagnostic path verifies explicit synthetic sources and four generated video
views. The production path invokes the independent full original PNG audit.
Neither path emits a legal verdict or treats requested control as observation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pass_right_audit import audit_delivery
from pass_right_measure import observe
from pass_right_route import build_case


def required(root: Path, relative: str) -> Path:
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + relative)
    return path


def bound_source(root: Path, reference: dict, label: str) -> Path:
    if not isinstance(reference, dict) or set(reference) != {'path', 'sha256'}:
        raise ValueError(label + ' source path and sha256 required')
    try:
        path = required(root, reference['path'])
    except ValueError as error:
        if str(error).startswith('Missing required source: '):
            raise ValueError('Missing required source: original-attempt/' + reference['path']) from error
        raise
    if hashlib.sha256(path.read_bytes()).hexdigest() != reference['sha256']:
        raise ValueError(label + ' source sha256 mismatch')
    return path


def measure_paragraph_a(root, sources):
    measured = sources['measured']
    return {'right_pass_observed': measured['right_pass_observed'],
            'intersection_crossed_during_pass': measured['intersection_crossed_during_pass'],
            'target_left_signal_during_pass': measured['target_left_signal_during_pass'],
            'target_left_motion_during_pass': measured['target_left_motion_during_pass'],
            'paragraph_a_condition_observed': measured['paragraph_a_condition_observed'],
            'pass_frames': measured['pass_frames'],
            'other_permission_alternatives': 'unresolved'}


def _source_audit(root: Path, expected_case: str):
    original = root / 'original-attempt'
    manifest_path = required(root, 'original-attempt/source-manifest.json')
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('case_id') != expected_case:
        raise ValueError('saved source selects another exact case')
    variant = expected_case.rsplit('__', 1)[-1]
    if manifest.get('variant') != variant or variant not in ('left_signal', 'left_turn', 'neither'):
        raise ValueError('saved source variant differs')
    map_path = bound_source(original, manifest.get('map'), 'map')
    trace_path = bound_source(original, manifest.get('trace'), 'trace')
    route_path = bound_source(original, manifest.get('route_request'), 'route')
    map_packet = json.loads(map_path.read_text())
    requested = json.loads(route_path.read_text())
    if requested != build_case(map_packet, variant):
        raise ValueError('route request differs from source map')
    trace = json.loads(trace_path.read_text())
    measured = observe(trace)
    if (measured['target_left_signal_during_pass'] != (variant == 'left_signal') or
            measured['target_left_motion_during_pass'] != (variant == 'left_turn')):
        raise ValueError('observed target behavior differs from exact case')
    if manifest.get('diagnostic_fixture') is True:
        provenance = json.loads(required(root, 'fixture-provenance.json').read_text())
        if provenance.get('diagnostic_fixture') is not True or map_packet.get('diagnostic_fixture') is not True:
            raise ValueError('diagnostic source provenance missing')
        mapping = json.loads(bound_source(original, manifest.get('frame_map'), 'frame map').read_text())
        rows = mapping.get('frames')
        if len(trace['frames']) != 900 or len(rows) != 900:
            raise ValueError('diagnostic original source needs 900 joined frames')
        for index, (sample, row) in enumerate(zip(trace['frames'], rows)):
            if (sample['frame'] != index or row['original_index'] != index or
                    sample['native_frame_id'] != row['native_frame_id'] or
                    sample['camera_frame_ids'] != row['camera_frame_ids'] or
                    abs(sample['t_s'] - row['time_s']) > 1e-6):
                raise ValueError('diagnostic source frame join differs')
        return map_packet, trace, measured, manifest_path, trace_path
    if manifest.get('diagnostic_fixture') is not False or map_packet.get('diagnostic_fixture') is True:
        raise ValueError('production source provenance is not original')
    audited = audit_delivery(original, manifest)
    if not audited['production_camera_profile_verified'] or audited['frame_count'] != 900:
        raise ValueError('production original camera proof incomplete')
    return map_packet, trace, measured, manifest_path, trace_path


def recording_evidence(root: Path, description: dict, map_packet: dict,
                       trace: dict) -> list:
    folder = root / 'channels'
    folder.mkdir(exist_ok=True)
    ego_id, target_id = trace['ego_id'], trace['target_id']
    interval = map_packet['intersection_s_m']
    def values(name, row):
        lookup = {
            'ego_target_identity': {'ego_id': ego_id, 'target_id': target_id},
            'relative_longitudinal_order': row['target_s_m'] - row['ego_s_m'],
            'relative_lateral_order': row['ego_lateral_m'] - row['target_lateral_m'],
            'target_left_signal': row['target_left_signal'],
            'target_left_motion': {'heading_deg': row['target_heading_deg'],
                                   'lateral_m': row['target_lateral_m']},
            'intersection_bounds': interval,
            'paved_surface_occupation': row['ego_paved'] and row['target_paved'],
            'road_direction_and_lane_count': {'direction': map_packet['direction'],
                                              'same_direction_marked_lanes': map_packet['same_direction_marked_lanes']},
            'original_road_and_intersection': {'intersection_s_m': interval,
                                               'source_kind': map_packet['source_kind']},
            'ego_target_identity_and_order': {'ego_id': ego_id, 'target_id': target_id,
                                              'ego_s_m': row['ego_s_m'],
                                              'target_s_m': row['target_s_m']},
            'target_left_signal_state': row['target_left_signal'],
            'target_left_turn_motion': {'heading_deg': row['target_heading_deg'],
                                        'lateral_m': row['target_lateral_m']},
            'pass_and_pavement_history': {'ego_s_m': row['ego_s_m'],
                                          'ego_paved': row['ego_paved'],
                                          'target_paved': row['target_paved']},
            'four_camera_frame_join': row['camera_frame_ids']}
        if name not in lookup:
            raise ValueError('unknown original recording channel: ' + name)
        return lookup[name]
    evidence = []
    for item in description['channels']:
        name = item['name']
        relative = 'channels/' + name + '.jsonl'
        with (root / relative).open('x') as stream:
            for row in trace['frames']:
                stream.write(json.dumps({'time_s': row['t_s'],
                                         'value': values(name, row)}, allow_nan=False) + '\n')
        evidence.append({'name': name, 'unit': item['unit'], 'reference': relative})
    contexts = {
        'reviewed_map_packet': {'source_kind': map_packet['source_kind'],
                                'diagnostic_fixture': map_packet.get('diagnostic_fixture') is True,
                                'intersection_s_m': interval},
        'reviewed_vehicle_setup': {'ego_id': ego_id, 'target_id': target_id,
                                   'actor_half_width_m': map_packet['actor_half_width_m']}}
    for item in description['context_inputs']:
        name = item['name']
        if name not in contexts:
            raise ValueError('unknown original recording context: ' + name)
        relative = 'channels/' + name + '.json'
        (root / relative).write_text(json.dumps({name: contexts[name]}, allow_nan=False) + '\n')
        evidence.append({'name': name, 'unit': item['unit'], 'reference': relative})
    return evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root = args.attempt.resolve()
    config = json.loads(required(root, 'config.json').read_text())
    case = config['selected_case_id']
    map_packet, trace, measured, manifest_path, trace_path = _source_audit(root, case)
    sources = {'measured': measured}
    measurement = {'method': 'measure_paragraph_a',
                   'value': measure_paragraph_a(root, sources),
                   'sources': {
                       'original-attempt/source-manifest.json': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                       str(trace_path.relative_to(root)): hashlib.sha256(trace_path.read_bytes()).hexdigest()}}
    report = {'format': 'worker-analysis-report', 'case_id': case,
              'measurements': {'observed_paragraph_a_condition': measurement},
              'legal_judgment': None, 'physical_acceptance': None,
              'analysis_complete': True,
              'limitations': ['Other right-pass permission alternatives remain unresolved.',
                              'Diagnostic sources do not prove original Native execution.']}
    from worker_exchange.native_output import physical_result, validate_result
    requested = case.endswith('__left_signal') or case.endswith('__left_turn')
    observed = measured['paragraph_a_condition_observed']
    result = physical_result(root, {
        'case_id': case,
        'measured_values': {'observed_paragraph_a_condition': measurement['value']},
        'target_checks': [{'target': 'paragraph_a_condition_observed',
                           'requested': requested, 'measured': observed,
                           'method': 'original saved target signal and left-motion samples during right pass',
                           'tolerance': 0, 'matched': observed == requested,
                           'physical_cause_confirmed': False,
                           'cause_evidence': 'Original physical causation requires independent review'}],
        'physical_failure_flags': {}, 'trace_reference': 'trace.jsonl',
        'video_references': ['raw.mkv'],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': recording_evidence(root, config['recording_description'],
                                                 map_packet, trace),
        'realized_observables': {}})
    validate_result(result)
    (root / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
