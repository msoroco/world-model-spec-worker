"""Saved-only measurements from sealed original cycle and motor-vehicle sources."""

import argparse
import hashlib
import json
from pathlib import Path

from overtake import CASES, measure_original, require

ASSIGNMENT = 'testing__C229023__NRS-484B-270-7b__cycle_or_scooter_operator'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def source(root, name, manifest):
    require(isinstance(name, str) and name and not Path(name).is_absolute(),
            'original source name missing')
    target = (root / name).resolve()
    require(target.is_relative_to(root) and target.is_file() and
            not target.is_symlink(), 'original source file missing: ' + name)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    require(manifest.get(name, {}).get('sha256') == digest,
            'original source hash differs: ' + name)
    return target


def build(attempt):
    root = Path(attempt).resolve()
    manifest_path = root / 'original-sources.json'
    require(manifest_path.is_file(), 'sealed original source manifest missing')
    manifest = json.loads(manifest_path.read_text())
    require(manifest.get('source_kind') == 'original_native_capture' and
            manifest.get('accepted_original_source') is True,
            'original Native capture provenance missing')
    config = json.loads(source(root, 'config.json', manifest['files']).read_text())
    case = next((item for item in CASES if
                 config['selected_case_id'] == ASSIGNMENT + '__' + item.case_id), None)
    require(case is not None, 'exact selected case differs')
    scene = json.loads(source(root, 'scene-context.json', manifest['files']).read_text())
    require(manifest.get('reviewed_scene_packet_sha256') and
            scene.get('reviewed_scene_packet_sha256') ==
            manifest['reviewed_scene_packet_sha256'],
            'reviewed original scene packet binding missing')
    rows_path = source(root, 'pass-readback.jsonl', manifest['files'])
    rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
    observation = measure_original(rows, scene, case)
    source(root, 'trace.jsonl', manifest['files'])
    source(root, 'video_frames.jsonl', manifest['files'])
    for name in VIEWS:
        source(root, name + '.mkv', manifest['files'])
    require(manifest.get('frame_count') == 900 and
            manifest.get('camera_frame_counts') == {name: 900 for name in VIEWS},
            'original four-camera frame identity incomplete')
    evidence = [{'name': 'relative_station', 'unit': 'm',
                 'reference': 'pass-readback.jsonl'},
                {'name': 'surface_clearance', 'unit': 'm',
                 'reference': 'pass-readback.jsonl'},
                {'name': 'closing_speed', 'unit': 'm/s',
                 'reference': 'pass-readback.jsonl'},
                {'name': 'camera_frame_identity', 'unit': 'original frame ID',
                 'reference': 'video_frames.jsonl'}]
    hashes = {key: value['sha256'] for key, value in manifest['files'].items()}
    report = {'format': 'worker-analysis-report',
              'case_id': config['selected_case_id'], 'analysis_complete': True,
              'physical_acceptance_claimed': False,
              'legal_verdict_claimed': False,
              'measurements': {'cycle_motor_pass': {
                  'method': 'measure_original', 'value': observation,
                  'sources': hashes}},
              'limitations': ['Safety and endangerment remain original physical and legal review.']}
    native = {'case_id': config['selected_case_id'],
              'measured_values': observation,
              'target_checks': [{'target': 'original cycle/motor passing history',
                                 'requested': config['case'],
                                 'measured': observation,
                                 'method': 'measure_original',
                                 'tolerance': None, 'matched': False,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': hashes}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'independent original physical review pending',
              'physical_failure_flags': [],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in VIEWS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['case']['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'diagnostic_fixture': False, 'physical_acceptance_claimed': False,
              'legal_verdict_claimed': False}
    return report, native


def compare(left, right, comparison):
    require(left['format'] == right['format'] == 'worker-analysis-report' and
            left['case_id'] != right['case_id'], 'two distinct original reports required')
    cases = comparison['case_ids']
    require(set(cases) == {left['case_id'], right['case_id']},
            'comparison exact cases differ')
    a = left['measurements']['cycle_motor_pass']['value']
    b = right['measurements']['cycle_motor_pass']['value']
    require(a['frame_count'] == b['frame_count'] == 900 and
            a['other_occupant_ids'] == b['other_occupant_ids'] and
            a['road_geometry_source_sha256'] == b['road_geometry_source_sha256'],
            'fixed frame or occupant condition differs')
    kind = comparison['comparison_id']
    if kind == 'bicycle_clearance':
        require(a['cycle_kind'] == b['cycle_kind'] == 'bicycle' and
                a['pass_policy'] == b['pass_policy'] == 'complete' and
                a['requested_lateral_offset_m'] != b['requested_lateral_offset_m'],
                'requested offset comparison differs')
    elif kind == 'pass_vs_abort':
        require(a['cycle_kind'] == b['cycle_kind'] == 'bicycle' and
                a['requested_lateral_offset_m'] == b['requested_lateral_offset_m'] and
                {a['pass_policy'], b['pass_policy']} == {'complete', 'abort'},
                'pass/abort comparison differs')
    elif kind in ('bicycle_vs_electric', 'electric_bicycle_vs_scooter'):
        expected = ({'bicycle', 'electric_bicycle'} if kind == 'bicycle_vs_electric'
                    else {'electric_bicycle', 'electric_scooter'})
        require({a['cycle_kind'], b['cycle_kind']} == expected and
                a['requested_lateral_offset_m'] == b['requested_lateral_offset_m'] and
                a['pass_policy'] == b['pass_policy'] == 'complete',
                'cycle classification comparison differs')
    else:
        raise ValueError('unknown exact comparison')
    for report in (left, right):
        require(report['measurements']['cycle_motor_pass']['sources'],
                'source-bound comparison input missing')
    return {'format': 'worker-c229023-comparison-audit-v1',
            'comparison_id': comparison['comparison_id'], 'case_ids': cases,
            'fixed_conditions': comparison['fixed_conditions'],
            'deliberate_differences': comparison['deliberate_differences'],
            'measured': [a, b], 'legal_verdict_claimed': False,
            'physical_acceptance_claimed': False}


def measure_case(attempt):
    marker = Path(attempt) / 'diagnostic-source-note.json'
    if marker.is_file():
        import diagnostic_analysis
        return diagnostic_analysis.analyze(attempt), None
    report, native = build(attempt)
    report['measurements']['cycle_motor_pass']['method'] = 'measure_case'
    return report, native


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'retain prior original analysis')
    report, native = measure_case(args.attempt)
    if native is not None:
        from worker_exchange.native_output import write_result
        write_result(args.attempt, native)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
