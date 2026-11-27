"""Saved-only right-side position and cycle pass measurements."""

import argparse
import hashlib
import json
from pathlib import Path

from rightside import CASES, SOURCE_ROLES, measure_original, need, validate_scene


AID = 'testing__C229023__NRS-484B-777-1__cycle_or_scooter_operator'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(root, name, manifest=None):
    need(isinstance(name, str) and name and not Path(name).is_absolute(),
         'original source name missing')
    path = (root / name).resolve()
    need(path.is_relative_to(root) and path.is_file() and not path.is_symlink(),
         'Missing required source: ' + name)
    if manifest is not None:
        need(manifest.get(name, {}).get('sha256') == sha(path),
             'original source hash differs: ' + name)
    return path


def selected(config):
    case_id = config.get('selected_case_id')
    case = next((item for item in CASES if case_id == AID + '__' + item.name), None)
    need(case is not None, 'exact selected right-side case differs')
    return case


def diagnostic(attempt):
    root = Path(attempt).resolve()
    marker = json.loads(source(root, 'diagnostic-source-note.json').read_text())
    need(marker.get('source_kind') == 'synthetic_diagnostic_fixture' and
         marker.get('accepted_original_source') is False,
         'diagnostic source marker differs')
    config = json.loads(source(root, 'config.json').read_text())
    case = selected(config)
    need(marker.get('case_id') == config['selected_case_id'],
         'diagnostic exact case differs')
    rows = json.loads(source(root, 'rightside-rows.json').read_text())
    need(isinstance(rows, list) and len(rows) == 900,
         'diagnostic 900-frame right-side stream missing')
    for i, row in enumerate(rows):
        need(row.get('frame') == i and row.get('time_s') == i / 20 and
             row.get('cycle_kind') == case.cycle_kind and
             row.get('target_motion') == case.target_motion and
             row.get('right_impediment') == case.right_impediment and
             row.get('narrow_lane') is case.narrow_lane,
             'diagnostic right-side frame/condition changed')
        for field in ('right_edge_distance_m', 'relative_station_m',
                      'surface_clearance_m', 'cycle_speed_mps',
                      'other_vehicle_speed_mps', 'right_access_width_m'):
            need(type(row.get(field)) in (int, float),
                 'diagnostic physical quantity missing: ' + field)
    observation = {
        'case_id': case.name, 'frame_count': len(rows),
        'cycle_kind': case.cycle_kind, 'target_motion': case.target_motion,
        'right_impediment': case.right_impediment, 'narrow_lane': case.narrow_lane,
        'traffic_speed_context': case.traffic_speed_context,
        'left_turn_preparation': case.left_turn_preparation,
        'requested_lateral_target_m': case.lateral_target_m,
        'minimum_right_edge_distance_m': min(row['right_edge_distance_m'] for row in rows),
        'minimum_surface_clearance_m': min(row['surface_clearance_m'] for row in rows),
        'initial_relative_station_m': rows[0]['relative_station_m'],
        'terminal_relative_station_m': rows[-1]['relative_station_m'],
        'mean_cycle_speed_mps': sum(row['cycle_speed_mps'] for row in rows) / len(rows),
        'mean_other_speed_mps': sum(row['other_vehicle_speed_mps'] for row in rows) / len(rows),
        'road_geometry_source_sha256': marker['road_geometry_source_sha256'],
        'lawful_speed_basis_source_sha256': marker['lawful_speed_basis_source_sha256'],
        'legal_practicability': None, 'legal_due_care': None,
        'legal_speed_commensurate': None, 'legal_safety': None,
    }
    need(observation['initial_relative_station_m'] < 0 and
         observation['terminal_relative_station_m'] > 0 and
         any(abs(row['relative_station_m']) <= 1 for row in rows),
         'diagnostic pass phases missing')
    refs = {name: sha(source(root, name)) for name in (
        'rightside-rows.json', 'diagnostic-source-note.json',
        'trace.jsonl', 'video_frames.jsonl')}
    extract = {
        'right_edge_distance': lambda row: row['right_edge_distance_m'],
        'relative_station': lambda row: row['relative_station_m'],
        'surface_clearance': lambda row: row['surface_clearance_m'],
        'cycle_speed': lambda row: row['cycle_speed_mps'],
        'other_vehicle_speed': lambda row: row['other_vehicle_speed_mps'],
        'right_access_width': lambda row: row['right_access_width_m'],
        'lane_width': lambda row: 3.5 if not case.narrow_lane else 2.5,
        'left_turn_preparation': lambda row: case.left_turn_preparation,
        'camera_frame_identity': lambda row: row['frame'],
    }
    evidence = []
    for channel in config['case']['recording_description']['channels']:
        name = channel['name']
        dest = root / ('channel-' + name + '.jsonl')
        dest.write_text(''.join(json.dumps({'time_s': row['time_s'],
                                           'value': extract[name](row)}, sort_keys=True) + '\n'
                                for row in rows))
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': dest.name})
    context = root / 'channel-reviewed_roadway.json'
    context.write_text(json.dumps({'reviewed_roadway': {
        'source_kind': 'synthetic_diagnostic_fixture',
        'road_geometry_source_sha256': marker['road_geometry_source_sha256']}},
        sort_keys=True) + '\n')
    evidence.append({'name': 'reviewed_roadway', 'unit': 'source record',
                     'reference': context.name})
    from worker_exchange.native_output import physical_result, write_result
    native = {'case_id': config['selected_case_id'], 'measured_values': observation,
              'target_checks': [{'target': 'synthetic right-side passing source join',
                                 'requested': config['case'], 'measured': observation,
                                 'method': '900 synthetic source-shaped rows',
                                 'tolerance': 0, 'matched': True,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': refs}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'synthetic compatibility only',
              'physical_failure_flags': ['original_right_side_scene_absent'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in VIEWS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['case']['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'diagnostic_fixture': True, 'physical_acceptance_claimed': False,
              'legal_verdict_claimed': False}
    write_result(root, physical_result(root, native))
    measurements = {'right_side_req_' + str(index): {'method': 'measure_case',
                    'value': observation, 'sources': refs}
                    for index in config['case']['disposition_indices']}
    return {'format': 'worker-analysis-report',
            'case_id': config['selected_case_id'], 'analysis_complete': True,
            'diagnostic_fixture': True, 'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False,
            'measurements': measurements,
            'limitations': ['Source-shaped fixture proves software joins only; legal judgments remain unresolved.']}, None


def original(attempt):
    root = Path(attempt).resolve()
    sealed = source(root, 'original-sources.json')
    manifest = json.loads(sealed.read_text())
    need(manifest.get('source_kind') == 'original_native_capture' and
         manifest.get('accepted_original_source') is True,
         'sealed original Native source manifest missing')
    files = manifest['files']
    config = json.loads(source(root, 'config.json', files).read_text())
    case = selected(config)
    scene = json.loads(source(root, 'scene-context.json', files).read_text())
    need(scene.get('reviewed_scene_packet_sha256') ==
         manifest.get('reviewed_scene_packet_sha256'),
         'reviewed original packet binding differs')
    validate_scene(scene, case)
    rows = [json.loads(line) for line in source(root, 'rightside-readback.jsonl', files).read_text().splitlines()]
    observation = measure_original(rows, scene, case)
    source(root, 'trace.jsonl', files)
    source(root, 'video_frames.jsonl', files)
    for name in VIEWS:
        source(root, name + '.mkv', files)
    need(manifest.get('frame_count') == 900 and
         manifest.get('camera_frame_counts') == {name: 900 for name in VIEWS},
         'original four-view capture incomplete')
    extract = {
        'right_edge_distance': lambda row: row['cycle_center_y_m'] - scene['roadway_right_y_m'] - scene['cycle_body_half_width_m'],
        'relative_station': lambda row: row['cycle_station_m'] - row['other_station_m'],
        'surface_clearance': lambda row: row['surface_clearance_m'],
        'cycle_speed': lambda row: row['cycle_speed_mps'],
        'other_vehicle_speed': lambda row: row['other_speed_mps'],
        'right_access_width': lambda row: row['right_access_width_m'],
        'lane_width': lambda row: scene['lane_width_m'],
        'left_turn_preparation': lambda row: row['left_turn_preparation'],
        'camera_frame_identity': lambda row: row['original_frame'],
    }
    evidence = []
    for channel in config['case']['recording_description']['channels']:
        name = channel['name']
        need(name in extract, 'unknown original right-side channel')
        dest = root / ('channel-' + name + '.jsonl')
        content = ''.join(json.dumps({'time_s': row['time_s'],
                                      'value': extract[name](row)}, sort_keys=True) + '\n'
                          for row in rows)
        if dest.exists():
            need(dest.read_text() == content, 'retained original channel differs: ' + name)
        else:
            dest.write_text(content)
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': dest.name})
    hashes = {name: sha(source(root, name)) for name in
              ('rightside-readback.jsonl', 'scene-context.json',
               'original-sources.json', 'trace.jsonl')}
    evidence_hashes = {name: item['sha256'] for name, item in files.items()}
    measurements = {'right_side_req_' + str(index): {'method': 'measure_case',
                    'value': observation, 'sources': hashes}
                    for index in config['case']['disposition_indices']}
    report = {'format': 'worker-analysis-report',
              'case_id': config['selected_case_id'], 'analysis_complete': True,
              'diagnostic_fixture': False, 'physical_acceptance_claimed': False,
              'legal_verdict_claimed': False,
              'measurements': measurements,
              'limitations': ['Due care, safety, lawful speed and practicability need independent original review.']}
    native = {'case_id': config['selected_case_id'],
              'measured_values': observation,
              'target_checks': [{'target': 'original cycle, right edge and passing history',
                                 'requested': config['case'], 'measured': observation,
                                 'method': 'measure_original', 'tolerance': None,
                                 'matched': False, 'physical_cause_confirmed': False,
                                 'cause_evidence': evidence_hashes}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'independent original physical review pending',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in VIEWS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['case']['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'diagnostic_fixture': False, 'physical_acceptance_claimed': False,
              'legal_verdict_claimed': False}
    return report, native


def measure_case(attempt):
    root = Path(attempt).resolve()
    if (root / 'diagnostic-source-note.json').is_file():
        return diagnostic(root)
    return original(root)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    need(not args.output.exists(), 'retain prior analysis report')
    report, native = measure_case(args.attempt)
    if native is not None:
        from worker_exchange.native_output import write_result
        write_result(args.attempt, native)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
