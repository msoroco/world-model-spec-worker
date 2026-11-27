"""Saved-only original group-spacing measurement with unresolved legal standards."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from motorcade_spacing import CASES, measure_original_frames
from runner import AID

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
HISTORY = 'original-group-history.jsonl'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = Path(root) / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    return path


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def check_source(root, case_id):
    seal_path = root / 'capture-seal.json'
    if seal_path.is_file():
        seal = json.loads(seal_path.read_text())
        if (seal.get('format') != 'worker-sealed-capture'
                or seal.get('provenance_kind') != 'native'
                or seal.get('diagnostic_fixture') is not False
                or seal.get('frames') != 600
                or seal.get('restoration', {}).get('restored') is not True):
            raise ValueError('sealed original Native group capture required')
        sources = seal.get('sources') or {}
        mandatory = {HISTORY, 'camera-frame-map.jsonl', 'video_frames.jsonl',
                     *[name + '.mkv' for name in VIEWS]}
        if not mandatory <= set(sources):
            raise ValueError('sealed original group source inventory incomplete')
        for name, digest in sources.items():
            if Path(name).is_absolute() or '..' in Path(name).parts:
                raise ValueError('unsafe source path')
            if sha(required(root, name)) != digest:
                raise ValueError('sealed Native group source changed: ' + name)
        revision = seal.get('native_revision') or {}
        if (revision.get('construction_sha256') != sha(required(root, 'construction.json'))
                or revision.get('runner_sha256') != sha(required(root, 'runner.py'))):
            raise ValueError('sealed Native implementation changed')
        return False, {HISTORY: sha(required(root, HISTORY)),
                       'capture-seal.json': sha(seal_path)}
    note = json.loads(required(root, 'diagnostic-source-note.json').read_text())
    if (note.get('source_kind') != 'synthetic_diagnostic_fixture'
            or note.get('accepted_original_source') is not False
            or note.get('case_id') != case_id):
        raise ValueError('explicit synthetic group diagnostic provenance required')
    return True, {HISTORY: sha(required(root, HISTORY)),
                  'diagnostic-source-note.json': sha(required(root, 'diagnostic-source-note.json'))}


def check_frame_joins(root, history):
    cameras = rows(required(root, 'camera-frame-map.jsonl'))
    videos = rows(required(root, 'video_frames.jsonl'))
    if len(history) != 600 or len(cameras) != 600 or len(videos) != 600:
        raise ValueError('all original group, camera and video frames required')
    for index, (row, camera, video) in enumerate(zip(history, cameras, videos)):
        frame = row.get('native_frame')
        if (row.get('frame') != index or camera.get('frame_index') != index
                or camera.get('native_frame') != frame
                or camera.get('camera_frames') != {view: frame for view in VIEWS}
                or video.get('video_frame') != index
                or video.get('carla_frame') != frame
                or abs(camera.get('time_s', -100) - row['time_s']) > 1e-5
                or abs(video.get('time_s', -100) - row['time_s']) > 1e-5):
            raise ValueError('group/camera/Native original frame join changed')


def measure_motor_vehicles(history, context):
    return {'roles': ['front', 'ego', 'rear', 'entrant'],
            'native_classes': context['vehicle_classes'],
            'observed_frame_count': len(history)}


def measure_highway_region(history, context):
    return {'native_road_id': context['native_road_id'],
            'public_highway_source': context['public_highway_source'],
            'outside_business_district_source': context['outside_business_district_source'],
            'legal_classification': None}


def measure_membership(history, context):
    return {'group_kind': context['group_kind'],
            'coordination_source': context['coordination_source'],
            'ordered_roles': context['ordered_roles'],
            'observed_role_ids': history[160]['group_role_ids']}


def measure_towing(history, context):
    return {'configured_group_towing': context['group_towing'],
            'observed_couplings': history[160]['couplings'],
            'all_coupling_history_retained': True}


def measure_space(history, context):
    case = next(item for item in CASES if item.suffix == context['case_suffix'])
    data = measure_original_frames(history, case)
    return {'front_steady_mean_m': data['steady_front_mean_m'],
            'rear_steady_mean_m': data['steady_rear_mean_m'],
            'entrant_kind': context['entrant_kind'],
            'entrant_lane_history': [row['bodies']['entrant']['native_lane_id'] for row in history],
            'legal_sufficiency': None}


def measure_danger(history, context):
    return {'collision_event_count': sum(len(row.get('collision_events', [])) for row in history),
            'source_frames': len(history),
            'relative_motion_available': all(row.get('velocities') is not None for row in history),
            'legal_without_danger': None}


def analyze(root):
    root = Path(root)
    config = json.loads(required(root, 'config.json').read_text())
    case_id = config.get('selected_case_id')
    matches = [case for case in CASES if case_id == AID + '__' + case.suffix]
    if config.get('assignment_id') != AID or len(matches) != 1:
        raise ValueError('saved exact caravan/motorcade case differs')
    diagnostic, source = check_source(root, case_id)
    history = rows(required(root, HISTORY))
    check_frame_joins(root, history)
    measured = measure_original_frames(history, matches[0])
    context_path = required(root, 'caravan-context.json')
    context = json.loads(context_path.read_text())
    if (context.get('case_suffix') != matches[0].suffix or
            context.get('group_kind') != matches[0].group_kind or
            context.get('group_towing') != matches[0].towing or
            context.get('entrant_kind') != ('combination' if matches[0].combination_entrant else 'vehicle')):
        raise ValueError('exact group context differs from selected case')
    measure_source = {HISTORY: source[HISTORY]}
    channels = {
        'sealed_native_original_frames': lambda row: row['frame'],
        'group_role_ids': lambda row: row['group_role_ids'],
        'vehicle_inventory': lambda row: row.get('vehicle_inventory'),
        'original_body_vertices': lambda row: {role: body['route_station_vertices_m'] for role, body in row['bodies'].items()},
        'front_group_clear_gap_m': lambda row: row['bodies']['front']['route_station_vertices_m'][0] - row['bodies']['ego']['route_station_vertices_m'][4],
        'rear_group_clear_gap_m': lambda row: row['bodies']['ego']['route_station_vertices_m'][0] - row['bodies']['rear']['route_station_vertices_m'][4],
        'velocity_history': lambda row: row.get('velocities'),
        'entrant_entry_occupancy': lambda row: {'lane_id': row['bodies']['entrant'].get('native_lane_id'), 'body': row['bodies']['entrant']['route_station_vertices_m']},
        'coupling_history': lambda row: row.get('couplings'),
        'collision_history': lambda row: row.get('collision_events', []),
        'controller_commands': lambda row: row['controls'],
        'video_four_views': lambda row: row['frame'],
    }
    evidence = []
    for channel in config['case']['recording_description']['channels']:
        name = channel['name']
        if name not in channels:
            raise ValueError('unknown group recording channel: ' + name)
        path = root / ('channel-' + name + '.jsonl')
        path.write_text(''.join(json.dumps({'time_s': row['time_s'],
                                            'value': channels[name](row)}) + '\n'
                                for row in history))
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': path.name})
    from worker_exchange.native_output import physical_result, write_result
    target = matches[0].gap_target_m
    checks = [
        {'target': 'measured pre-entry front group body clear gap',
         'requested': target, 'measured': measured['steady_front_mean_m'],
         'method': 'original 8..14 s Native all-vertex body intervals',
         'tolerance': 3.0, 'matched': abs(measured['steady_front_mean_m'] - target) < 3,
         'physical_cause_confirmed': False, 'cause_evidence': measure_source},
        {'target': 'measured pre-entry rear group body clear gap',
         'requested': target, 'measured': measured['steady_rear_mean_m'],
         'method': 'original 8..14 s Native all-vertex body intervals',
         'tolerance': 3.0, 'matched': abs(measured['steady_rear_mean_m'] - target) < 3,
         'physical_cause_confirmed': False, 'cause_evidence': measure_source},
    ]
    result = {
        'case_id': case_id,
        'measured_values': {'steady_front_mean_m': measured['steady_front_mean_m'],
                            'steady_rear_mean_m': measured['steady_rear_mean_m']},
        'target_checks': checks, 'setup_confirmed': False,
        'behavior_attempted': False, 'maneuver_completed': False,
        'termination_reason': 'saved measurement pending physical review',
        'physical_failure_flags': [] if not diagnostic else ['original_group_source_absent'],
        'trace_reference': 'trace.jsonl',
        'video_references': [view + '.mkv' for view in VIEWS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['case']['recording_description'],
        'recording_evidence': evidence, 'realized_observables': {},
        'diagnostic_fixture': diagnostic,
        'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
    }
    result = physical_result(root, result)
    write_result(root, result)
    facts = {
        'qualifying_motor_vehicles': (measure_motor_vehicles, [HISTORY, 'caravan-context.json']),
        'highway_and_region': (measure_highway_region, [HISTORY, 'caravan-context.json']),
        'caravan_membership': (measure_membership, [HISTORY, 'caravan-context.json']),
        'motorcade_membership': (measure_membership, [HISTORY, 'caravan-context.json']),
        'towing_alternative': (measure_towing, [HISTORY, 'caravan-context.json']),
        'entry_and_occupancy_space': (measure_space, [HISTORY, 'caravan-context.json']),
        'danger_context': (measure_danger, [HISTORY, 'caravan-context.json']),
    }
    measured_facts = {}
    for key, (method, inputs) in facts.items():
        measured_facts[key] = {'method': method.__name__,
                               'value': method(history, context),
                               'sources': {name: sha(required(root, name)) for name in inputs}}
    return {'format': 'worker-analysis-report', 'case_id': case_id,
            'analysis_complete': True, 'diagnostic_fixture': diagnostic,
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
            'measurements': measured_facts,
            'physical_checks': result['physical_checks'],
            'realized_observables': result['realized_observables'],
            'limitations': ['Original physical group motion, camera coverage and legal judgments require independent review.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior group analysis report')
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + '\n')
