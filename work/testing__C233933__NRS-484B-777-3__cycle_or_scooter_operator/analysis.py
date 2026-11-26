"""Saved-only rider identity, formation, surface and source measurements."""
import argparse
import hashlib
import json
from pathlib import Path
from abreast import CASES, SOURCES, measure_original, validate_scene
from package_spec import CAMERA_NAMES

def need(ok, message):
    if not ok:
        raise ValueError(message)

def source(root, name):
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    return path

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def source_sealed_rider_measurement(value):
    return value

def diagnostic_measure(rows, scene, case):
    if len(rows) < 3:
        raise ValueError('diagnostic formation frames missing')
    spans = []
    lateral = []
    for row in rows:
        positions = row['rider_xy']
        if len(positions) != case.riders or row['rider_ids'] != scene['rider_ids']:
            raise ValueError('diagnostic rider identity differs')
        spans.append(max(x[0] for x in positions) - min(x[0] for x in positions))
        lateral.append(max(x[1] for x in positions) - min(x[1] for x in positions))
    return {'case_id': case.name, 'rider_count': case.riders,
            'max_longitudinal_spread_m': max(spans), 'min_lateral_spread_m': min(lateral),
            'abreast_legal_judgment': None, 'exclusive_use_judgment': None}

def analyze(attempt):
    root = Path(attempt).resolve()
    config = json.loads(source(root, 'config.json').read_text())
    selected = config['selected_case_id']
    case = next((item for item in CASES if selected.endswith('__' + item.name)), None)
    need(case is not None, 'unknown exact rider case')
    receipt = json.loads(source(root, 'original-source-receipt.json').read_text())
    diagnostic = receipt.get('diagnostic_fixture') is True
    need(receipt.get('source_kind') == ('synthetic_diagnostic_fixture' if diagnostic else 'original_native_capture') and receipt.get('case_id') == selected, 'rider source provenance differs')
    for key, name in [('history_sha256', 'rider-history.json'),
                      ('trace_sha256', 'trace.jsonl'),
                      ('frame_map_sha256', 'video_frames.jsonl'),
                      ('measurement_sha256', 'rider-measurement.json')]:
        need(receipt.get(key) == sha(source(root, name)), 'sealed rider source differs: ' + name)
    history = json.loads(source(root, 'rider-history.json').read_text())
    rows, scene = history['samples'], history['scene']
    validate_scene(scene, case)
    traces = [json.loads(x) for x in source(root, 'trace.jsonl').read_text().splitlines()]
    mapping = [json.loads(x) for x in source(root, 'video_frames.jsonl').read_text().splitlines()]
    need(history.get('assignment_id') == config['assignment_id'] and history.get('case_id') == selected and len(rows) == len(traces) == len(mapping) and len(rows) >= 3, 'rider case or frame count differs')
    need(history.get('rider_ids') == scene['rider_ids'] and len(history['native_actor_ids']) == case.riders and len(set(history['native_actor_ids'])) == case.riders, 'separate Native rider identity missing')
    for i, (row, trace, mapped) in enumerate(zip(rows, traces, mapping)):
        need(row['frame'] == mapped['video_frame'] == i and row['native_frame'] == row['original_frame'] == trace['frame'] == mapped['native_frame'] == mapped['carla_frame'] and row['time_s'] == trace['time_s'] == mapped['time_s'] and row['ego_speed_mps'] == trace['speed_mps'], 'original rider frame/trace/video join differs')
        need(row['native_actor_ids'] == history['native_actor_ids'] and row['rider_ids'] == scene['rider_ids'], 'original rider identity changed')
        for name in SOURCES:
            need(row[name + '_source_sha256'] == scene[name + '_source_sha256'], 'rider context source changed: ' + name)
        if not diagnostic:
            need(row['ego_position_xyz_m'] == trace['position_m'], 'original ego rider pose differs')
    measured = diagnostic_measure(rows, scene, case) if diagnostic else None
    if not diagnostic:
        try:
            measured = measure_original(rows, scene, case)
        except ValueError as error:
            measured = {'measured': False, 'physical_gap': str(error), 'abreast_legal_judgment': None, 'exclusive_use_judgment': None}
    need(json.loads(source(root, 'rider-measurement.json').read_text()) == measured, 'saved rider measurement differs')
    values = {
        'highway_roadway_shoulder': {'highway': scene['highway'], 'roadway_rect_m': scene['roadway_rect_m'], 'shoulder_rect_m': scene['shoulder_rect_m'], 'sidewalk_absent': scene['sidewalk_absent']},
        'occupied_surface': {'roadway': case.roadway, 'surface_rect_m': scene['occupied_surface_rect_m']},
        'exclusive_use_designation': {'exclusive': case.exclusive, 'source_sha256': scene['exclusive_use_designation_source_sha256'], 'legal_judgment': None},
        'bicycle_classification': {'vehicle_type': scene['vehicle_type'], 'moped': scene['moped'], 'source_sha256': scene['bicycle_classification_source_sha256']},
        'rider_identity': {'rider_ids': scene['rider_ids'], 'native_actor_ids': history['native_actor_ids']},
        'rider_formation': measured,
        'rider_motion': {'first_position_m': traces[0]['position_m'], 'last_position_m': traces[-1]['position_m'], 'maximum_speed_mps': max(row['ego_speed_mps'] for row in rows)}}
    sources = {name: sha(source(root, name)) for name in ('rider-history.json', 'rider-measurement.json', 'original-source-receipt.json', 'trace.jsonl')}
    measurements = {name: {'method': 'source_sealed_rider_measurement', 'value': source_sealed_rider_measurement(value), 'sources': sources} for name, value in values.items()}
    evidence = []
    for channel in config['case']['recording_description']['channels']:
        name = channel['name']
        path = root / ('channel-' + name + '.jsonl')
        content = ''.join(json.dumps({'time_s': row['time_s'], 'value': row['rider_xy'] if name == 'rider_formation' else row['rider_speed_mps'] if name == 'rider_motion' else values[name]}, sort_keys=True) + '\n' for row in rows)
        if path.exists():
            need(path.read_text() == content, 'derived rider channel differs')
        else:
            path.write_text(content)
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': path.name})
    context = root / 'channel-reviewed_rider_site.json'
    content = json.dumps({'reviewed_rider_site': {'reviewed_site_sha256': history['reviewed_site_sha256'], 'source_hashes': {name: scene[name + '_source_sha256'] for name in SOURCES}}}, sort_keys=True) + '\n'
    if context.exists():
        need(context.read_text() == content, 'reviewed rider site context differs')
    else:
        context.write_text(content)
    evidence.append({'name': 'reviewed_rider_site', 'unit': 'source record', 'reference': context.name})
    from worker_exchange.native_output import physical_result, write_result
    result = {'case_id': selected, 'measured_values': values,
              'target_checks': [{'target': 'source-identified rider count and original physical formation',
                                 'requested': case.riders, 'measured': measured.get('rider_count'),
                                 'method': 'source-sealed rider identity and formation frames',
                                 'tolerance': 0, 'matched': measured.get('rider_count') == case.riders,
                                 'physical_cause_confirmed': False, 'cause_evidence': sources}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False, 'termination_reason': 'saved physical and legal review pending',
              'physical_failure_flags': ['physical_acceptance_unverified'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in CAMERA_NAMES],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['case']['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'diagnostic_fixture': diagnostic, 'physical_acceptance_claimed': False,
              'legal_verdict_claimed': False}
    result = physical_result(root, result)
    write_result(root, result)
    return {'format': 'worker-analysis-report', 'case_id': selected,
            'analysis_complete': True, 'diagnostic_fixture': diagnostic,
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
            'measurements': measurements, 'physical_checks': result['physical_checks'],
            'realized_observables': result['realized_observables'],
            'limitations': ['0.25 m is a physical formation tolerance, not a legal abreast cutoff.']}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior rider analysis report')
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + '\n')
