"""Finalize source-joined hose observations; reserve legal and command conclusions."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_hose import CAMERAS, FRAMES, measure

LAW = 'A vehicle shall not be driven over any unprotected hose of a fire department when laid down on any highway or private way or place for use at any fire or alarm of fire or practice runs, without the consent of the fire department official in command.'
SOURCES = ('road.xodr', 'actor-sources.jsonl', 'camera-frames.jsonl',
           'hose-source.json', 'way-review.json', 'hose-review.json',
           'command-review.json', 'video_frames.jsonl', 'reference_corner.mkv')
CHANNELS = ('st.obstruction', 'rel.occupies', 'kin.path_length', 'st.highway',
            'ru.fire_apparatus', 'dev.human_direction', 'kin.velocity')


def required(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in required(path.parent, path.name).read_text().splitlines()]


def measured(root):
    root = Path(root)
    sources = {name: required(root, name) for name in SOURCES}
    config = json.loads(required(root, 'config.json').read_text())
    hose = json.loads(sources['hose-source.json'].read_text())
    way = json.loads(sources['way-review.json'].read_text())
    hose_review = json.loads(sources['hose-review.json'].read_text())
    command = json.loads(sources['command-review.json'].read_text())
    diagnostic = (root / 'fixture-provenance.json').is_file()
    expected = 'synthetic_diagnostic' if diagnostic else 'independently_reviewed'
    for review in (way, hose_review, command):
        if review.get('review_status') != expected or not review.get('reviewer') or not review.get('source'):
            raise ValueError('Independent way, hose and command review required')
    if len({way['source'], hose_review['source'], command['source']}) != 3:
        raise ValueError('Way, hose and command sources must be separate')
    if way.get('road_sha256') != sha(sources['road.xodr']) or way.get('way_kind') not in ('highway', 'private_way', 'private_place'):
        raise ValueError('Qualifying way source differs')
    if not way.get('road_access_basis') or way.get('hose_on_actual_route') is not True:
        raise ValueError('Highway dedication, access and placement review absent')
    if hose_review.get('hose_source_sha256') != sha(sources['hose-source.json']) or hose_review.get('pixel_sha256') != sha(sources['reference_corner.mkv']):
        raise ValueError('Hose inventory or original pixels differ')
    if hose_review.get('department_affiliation') is not True or hose_review.get('fire_use_purpose') not in ('fire', 'alarm', 'practice_run'):
        raise ValueError('Department affiliation or use purpose review absent')
    if hose_review.get('protection_arrangements') is None or type(hose_review.get('unprotected')) is not bool:
        raise ValueError('Independent protection arrangement review absent')
    if command.get('actor_sha256') != sha(sources['actor-sources.jsonl']) or command.get('case_id') != config['case_id']:
        raise ValueError('Command review actor/case source differs')
    if not command.get('official_identity') or command.get('command_status') != 'official_in_command':
        raise ValueError('Command-official identity and status review absent')
    if command.get('vehicle_class') != 'ordinary_motor_vehicle' or command.get('human_driver') is not True:
        raise ValueError('Covered motor vehicle and human driver review absent')
    if command.get('communication_status') not in ('explicit_none', 'documented_consent'):
        raise ValueError('Command communication source absent')
    if command['communication_status'] == 'documented_consent':
        if command.get('permission') != 'drive_over_hose' or command.get('scope_case_id') != config['case_id'] or not command.get('timing_source'):
            raise ValueError('Consent content, scope or timing source absent')
    if command['communication_status'] == 'explicit_none' and command.get('monitoring_window') != 'full_original_capture':
        raise ValueError('Explicit no-communication monitoring source absent')
    frame_map = rows(sources['video_frames.jsonl'])
    if len(frame_map) != FRAMES:
        raise ValueError('Original frame map incomplete')
    for i, row in enumerate(frame_map):
        if row.get('video_frame') != i or abs(row.get('time_s', -1) - i / 20) > 1e-6:
            raise ValueError('Original frame/time join differs')
        if set(row.get('camera_native_frames', {})) != set(CAMERAS):
            raise ValueError('Original four-camera join differs')
    result = measure(root, config['case_id'], 'synthetic_cpu' if diagnostic else 'original_native')
    for name in CAMERAS:
        required(root, name + '.mkv')
    return result, way, hose_review, command, {name: sha(path) for name, path in sources.items()}


def way_observation(root):
    _, way, _, _, _ = measured(root)
    return {'way_kind': way['way_kind'], 'access_basis': way['road_access_basis'],
            'hose_on_actual_route': way['hose_on_actual_route']}


def hose_observation(root):
    _, _, hose, _, _ = measured(root)
    return {'department_affiliation': hose['department_affiliation'],
            'fire_use_purpose': hose['fire_use_purpose'],
            'protection_arrangements': hose['protection_arrangements'],
            'unprotected': hose['unprotected']}


def command_observation(root):
    _, _, _, command, _ = measured(root)
    return {'official_identity': command['official_identity'],
            'command_status': command['command_status'],
            'communication_status': command['communication_status'],
            'permission': command.get('permission'), 'timing_source': command.get('timing_source')}


def passage_observation(root):
    value, _, _, _, _ = measured(root)
    return {'first_driven_hose_overlap_frame': value['first_driven_hose_overlap_frame'],
            'driven_hose_overlap_frames': value['driven_hose_overlap_frames']}


def motion_observation(root):
    value, _, _, _, _ = measured(root)
    return {'ego_center_path_length_m': value['ego_center_path_length_m'], 'frames': value['frames']}


def driver_observation(root):
    _, _, _, command, _ = measured(root)
    return {'vehicle_class': command['vehicle_class'], 'human_driver': command['human_driver']}


def report(root):
    root = Path(root)
    cfg = json.loads(required(root, 'config.json').read_text())
    law = json.loads(required(root, 'law-text.json').read_text())
    if law.get('text') != LAW or law.get('source') != 'NRS 484B.913':
        raise ValueError('Exact statutory text differs')
    value, way, hose, command, hashes = measured(root)
    outputs = {
        'source_bound_hose_passage': ('measured', value),
        'qualifying_way_and_route': ('way_observation', {'way_kind': way['way_kind'], 'access_basis': way['road_access_basis'], 'hose_on_actual_route': way['hose_on_actual_route']}),
        'department_hose_purpose_protection': ('hose_observation', {'department_affiliation': hose['department_affiliation'], 'fire_use_purpose': hose['fire_use_purpose'], 'protection_arrangements': hose['protection_arrangements'], 'unprotected': hose['unprotected']}),
        'command_official_communication': ('command_observation', {'official_identity': command['official_identity'], 'command_status': command['command_status'], 'communication_status': command['communication_status'], 'permission': command.get('permission'), 'timing_source': command.get('timing_source')}),
        'original_driven_hose_overlap': ('passage_observation', {'first_driven_hose_overlap_frame': value['first_driven_hose_overlap_frame'], 'driven_hose_overlap_frames': value['driven_hose_overlap_frames']}),
        'original_vehicle_motion': ('motion_observation', {'ego_center_path_length_m': value['ego_center_path_length_m'], 'frames': value['frames']})}
    outputs['covered_vehicle_and_driver'] = ('driver_observation',
        {'vehicle_class': command['vehicle_class'], 'human_driver': command['human_driver']})
    measurements = {key: {'method': method, 'value': observed, 'sources': hashes}
                    for key, (method, observed) in outputs.items()}
    measurements['statutory_context'] = {'method': 'statutory_context',
        'value': {'legal_outcome': 'reserved', 'no_legal_crossing_cutoff': True},
        'sources': {'law-text.json': sha(root / 'law-text.json')}}
    channels = {name: [] for name in CHANNELS}
    actor_rows = rows(root / 'actor-sources.jsonl')
    for i, actor in enumerate(actor_rows):
        values = {
            'st.obstruction': {'hose_review_sha256': sha(root / 'hose-review.json')},
            'rel.occupies': {'driven_overlap': value['first_driven_hose_overlap_frame'] is not None and i >= value['first_driven_hose_overlap_frame']},
            'kin.path_length': {'total_path_m': value['ego_center_path_length_m']},
            'st.highway': {'way_kind': way['way_kind']},
            'ru.fire_apparatus': {'department_affiliation': hose['department_affiliation']},
            'dev.human_direction': {'communication_status': command['communication_status']},
            'kin.velocity': {'speed_mps': actor['ego_speed_mps']}}
        for name, val in values.items():
            channels[name].append({'time_s': i / 20, 'value': val})
    return {'format': 'worker-analysis-report-v1', 'case_id': cfg['case_id'],
            'measurements': measurements,
            'scope': 'Original hose passage with independently reviewed way, hose protection and command communication; legal outcome reserved'}, channels


def finalize(root, output):
    from worker_exchange.native_output import physical_result, provenance_record, write_result
    root, output = Path(root), Path(output)
    if output.exists() or (root / 'result.json').exists():
        raise ValueError('Use a fresh finalization stage')
    cfg = json.loads(required(root, 'config.json').read_text())
    analysis, channels = report(root)
    if {row['name'] for row in cfg['recording_description']['channels']} != set(CHANNELS):
        raise ValueError('Declared hose channels differ')
    directory = root / 'channels'
    directory.mkdir(exist_ok=True)
    for name, values in channels.items():
        (directory / (name + '.jsonl')).write_text(''.join(json.dumps(v, allow_nan=False) + '\n' for v in values))
    value = analysis['measurements']['source_bound_hose_passage']['value']
    requested = cfg['cross_hose_requested']
    measured_crossing = value['first_driven_hose_overlap_frame'] is not None
    target = {'target': 'original driven full-body hose overlap',
              'requested': 'cross' if requested else 'route_around',
              'measured': 'cross' if measured_crossing else 'route_around',
              'method': 'source-bound 600-frame vehicle footprint and velocity',
              'tolerance': 0, 'matched': requested == measured_crossing,
              'physical_cause_confirmed': False, 'cause_evidence': list(SOURCES)}
    evidence = [{'name': name, 'unit': 'source', 'reference': name} for name in SOURCES]
    evidence += [{'name': row['name'], 'unit': row['unit'], 'reference': row['source']}
                 for row in cfg['recording_description']['channels']]
    result = {'case_id': cfg['case_id'], 'measured_values': value,
              'target_checks': [target], 'setup_confirmed': False,
              'behavior_attempted': False, 'maneuver_completed': False,
              'termination_reason': 'Awaiting original source and physical review',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': cfg['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              **provenance_record(root), 'accepted': False, 'legal_verdict_claimed': False}
    physical_result(root, result)
    output.write_text(json.dumps(analysis, indent=2, allow_nan=False) + '\n')
    write_result(root, result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
