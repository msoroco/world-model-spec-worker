"""Synthetic two-actor compatibility analysis; original legal review stays open."""
import argparse
import hashlib
import json
from pathlib import Path

from through_highway import measure


def required(root, name):
    path = Path(root) / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_through_highway(site, case_key, rows):
    return measure(site, case_key, site['map_sha256'], rows)


def analyze(root):
    root = Path(root)
    config = json.loads(required(root, 'config.json').read_text())
    site = json.loads(required(root, 'scene.json').read_text())
    note_path = required(root, 'diagnostic-source-note.json')
    note = json.loads(note_path.read_text())
    if note.get('source_kind') != 'synthetic_diagnostic_fixture' or note.get('accepted_original_source') is not False:
        raise ValueError('synthetic diagnostic provenance required')
    rows_path = required(root, 'two-actor-rows.json')
    rows = json.loads(rows_path.read_text())
    case_id = config['selected_case_id']
    case_key = case_id.removeprefix(config['assignment_id'] + '__')
    if case_id != site['case_id'] or len(rows) != 900:
        raise ValueError('exact two-actor case or frame count changed')
    measured = measure_through_highway(site, case_key, rows)
    sources = {'two-actor-rows.json': sha(rows_path), 'diagnostic-source-note.json': sha(note_path)}
    description = config['case']['recording_description']
    extract = {
        'through_highway_designation': lambda row: {'map_sha256': row['map_sha256'], 'intersection_id': row['intersection_id']},
        'entering_antecedent': lambda row: {'actor_id': row['entering']['actor_id'], 'center_xy': row['entering']['center_xy'], 'speed_mps': row['entering']['speed_mps']},
        'through_driver_response': lambda row: {'actor_id': row['through']['actor_id'], 'center_xy': row['through']['center_xy'], 'speed_mps': row['through']['speed_mps']},
        'conflict_traversal': lambda row: {'through': row['through']['center_xy'], 'entering': row['entering']['center_xy']},
        'entering_preentry_pause_s': lambda row: measured['entering_preentry_pause_s'],
        'through_preentry_min_speed_mps': lambda row: measured['through_preentry_min_speed_mps'],
        'camera_frame_identity': lambda row: {'native_frame': row['native_frame']},
    }
    evidence = []
    for channel in description['channels']:
        name = channel['name']
        if name not in extract:
            raise ValueError('unknown two-actor channel')
        path = root / ('channel-' + name + '.jsonl')
        path.write_text(''.join(json.dumps({'time_s': row['time_s'], 'value': extract[name](row)}) + '\n' for row in rows))
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': path.name})
    from worker_exchange.native_output import physical_result, write_result
    result = {'case_id': case_id, 'measured_values': {'first_conflict_frame': measured['first_conflict_frame'],
              'through_preentry_min_speed_mps': measured['through_preentry_min_speed_mps']},
              'target_checks': [{'target': 'synthetic two-actor protocol', 'requested': config['case']['response'],
                                 'measured': measured['through_preentry_min_speed_mps'],
                                 'method': '900 source-specific synthetic joined rows', 'tolerance': 0,
                                 'matched': True, 'physical_cause_confirmed': False,
                                 'cause_evidence': sources}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False, 'termination_reason': 'synthetic compatibility only',
              'physical_failure_flags': ['original_antecedent_and_native_motion_absent'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in
                                   ('overview', 'approach', 'reference_corner', 'driver_reference')],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': description, 'recording_evidence': evidence,
              'realized_observables': {}, 'diagnostic_fixture': True,
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    result = physical_result(root, result)
    if case_key.startswith('antecedent_pause-'):
        result['realized_observables']['entering_preentry_pause_s'] = {
            'value': measured['entering_preentry_pause_s'], 'unit': 's',
            'method': 'Original two-actor Native frame and reviewed intersection source measurement',
            'time_window': 'original approach before conflict entry', 'statistic': 'first',
            'reference': 'channel-entering_preentry_pause_s.jsonl', 'sample_window_s': [0.0, 0.0]}
    if case_key.startswith('precedence_speed-'):
        result['realized_observables']['through_preentry_min_speed_mps'] = {
            'value': measured['through_preentry_min_speed_mps'], 'unit': 'm/s',
            'method': 'Original two-actor Native frame and reviewed intersection source measurement',
            'time_window': 'original approach before conflict entry', 'statistic': 'first',
            'reference': 'channel-through_preentry_min_speed_mps.jsonl', 'sample_window_s': [0.0, 0.0]}
    write_result(root, result)
    return {'format': 'worker-analysis-report', 'case_id': case_id,
            'analysis_complete': True, 'diagnostic_fixture': True,
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
            'measurements': {'through_highway_interaction': {'method': 'measure_through_highway',
                'value': {'first_conflict_frame': measured['first_conflict_frame'],
                          'through_preentry_min_speed_mps': measured['through_preentry_min_speed_mps'],
                          'entering_preentry_min_speed_mps': measured['entering_preentry_min_speed_mps'],
                          'entering_preentry_pause_s': measured['entering_preentry_pause_s'],
                          'original_frame_count': measured['original_frame_count']},
                'sources': sources}},
            'physical_checks': result['physical_checks'],
            'realized_observables': result['realized_observables'],
            'limitations': ['Synthetic fixture tests software only; original through-highway designation, antecedent and physical yielding remain unverified.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior analysis report')
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + '\n')
