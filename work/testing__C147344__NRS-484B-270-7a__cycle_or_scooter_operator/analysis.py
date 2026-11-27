"""Recorded-only analysis of sealed original bicycle/vehicle interaction."""

import argparse
import hashlib
import json
from pathlib import Path

from interference import CASES, measure_original, require


ASSIGNMENT = 'testing__C147344__NRS-484B-270-7a__cycle_or_scooter_operator'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def original_file(root, name, files):
    require(isinstance(name, str) and name and
            not Path(name).is_absolute(), 'original source name missing')
    target = (root / name).resolve()
    require(target.is_relative_to(root) and target.is_file() and
            not target.is_symlink(),
            'original source file missing: ' + name)
    require(files.get(name, {}).get('sha256') ==
            hashlib.sha256(target.read_bytes()).hexdigest(),
            'original source hash differs: ' + name)
    return target


def analyze(attempt):
    root = Path(attempt).resolve()
    manifest_path = root / 'original-sources.json'
    require(manifest_path.is_file(), 'sealed original source manifest missing')
    manifest = json.loads(manifest_path.read_text())
    require(manifest.get('source_kind') == 'original_native_capture' and
            manifest.get('accepted_original_source') is True and
            manifest.get('frame_count') == 600 and
            manifest.get('camera_frame_counts') ==
            {name: 600 for name in VIEWS},
            'original Native acquisition provenance incomplete')
    files = manifest.get('files', {})
    config = json.loads(original_file(root, 'config.json', files).read_text())
    case = next((item for item in CASES if
                 config.get('selected_case_id') ==
                 ASSIGNMENT + '__' + item.suffix), None)
    require(case is not None and manifest.get('case_id') ==
            config['selected_case_id'], 'exact selected case differs')
    scene = json.loads(original_file(root, 'scene-context.json', files).read_text())
    require(scene.get('reviewed_scene_packet_sha256') ==
            manifest.get('reviewed_scene_packet_sha256'),
            'reviewed original scene packet binding missing')
    require(scene.get('electric_bicycle_classification') ==
            scene.get('electric_bicycle') and
            scene.get('distinct_motor_vehicle_identity') ==
            scene.get('motor_vehicle', {}).get('vehicle_id') and
            scene.get('authored_plan_interval') ==
            (scene.get('intention_declaration') or {'status': 'undeclared'}),
            'original context differs from source-bound scene')
    rows = [json.loads(line) for line in original_file(
        root, 'interaction-readback.jsonl', files).read_text().splitlines()]
    observation = measure_original(rows, scene, case)
    original_file(root, 'trace.jsonl', files)
    original_file(root, 'video_frames.jsonl', files)
    for name in VIEWS:
        original_file(root, name + '.mkv', files)
    channels = config['case']['recording_description']['channels']
    allowed = {'motor_vehicle_speed': 'motor_speed_mps',
               'motor_brake': 'motor_brake',
               'bicycle_lane': 'bicycle_lane',
               'body_gap': 'body_gap_m',
               'camera_frame_identity': 'original_frame'}
    evidence = []
    for channel in channels:
        name = channel['name']
        require(name in allowed, 'unknown original observation channel')
        require(all(allowed[name] in row for row in rows),
                'original observation channel missing: ' + name)
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': 'interaction-readback.jsonl'})
    for context_item in config['case']['recording_description']['context_inputs']:
        require(scene.get(context_item['name']) is not None,
                'original context missing: ' + context_item['name'])
        evidence.append({'name': context_item['name'],
                         'unit': context_item['unit'],
                         'reference': 'scene-context.json'})
    hashes = {name: item['sha256'] for name, item in files.items()}
    report = {'format': 'worker-analysis-report',
              'case_id': config['selected_case_id'],
              'analysis_complete': True,
              'original_sources_sha256':
              hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
              'physical_acceptance_claimed': False,
              'legal_judgment': None,
              'measurements': {'electric_bicycle_motor_interaction': {
                  'method': 'measure_case',
                  'value': observation, 'sources': hashes}},
              'limitations': [
                  'Recorded action cannot prove subjective intent.',
                  'Physical causation and legal interference require independent original review.']}
    native = {'case_id': config['selected_case_id'],
              'measured_values': observation,
              'target_checks': [{
                  'target': 'original electric bicycle and motor vehicle interaction',
                  'requested': config['case'],
                  'measured': observation,
                  'method': 'measure_original',
                  'tolerance': None, 'matched': False,
                  'physical_cause_confirmed': False,
                  'cause_evidence': hashes}],
              'setup_confirmed': False,
              'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'independent original physical review pending',
              'physical_failure_flags': [],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in VIEWS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['case']['recording_description'],
              'recording_evidence': evidence,
              'realized_observables': {},
              'diagnostic_fixture': False,
              'physical_acceptance_claimed': False,
              'legal_verdict_claimed': False}
    return report, native


def measure_case(attempt):
    """Select synthetic diagnostic or original-source path by provenance."""
    if (Path(attempt) / 'diagnostic-source-note.json').is_file():
        from diagnostic_analysis import analyze_fixture
        return analyze_fixture(attempt), None
    return analyze(attempt)


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
