"""Saved-only City-space observations from a complete original or CPU fixture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from city_space import CASES, SOURCE_FIELDS, measure_original
from physical_completion import assess
from source_packet import ASSIGNMENT, sha

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('original-city-space.jsonl', 'city-space-context.json',
           'camera-frame-map.jsonl', 'video_frames.jsonl', 'trace.jsonl')


def required(root, name):
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    return path


def lines(root, name):
    return [json.loads(line) for line in required(root, name).read_text(encoding='utf-8').splitlines()]


def measure_city_space(measured, scene):
    return {'parked_frames': measured['parked_frames'],
            'vehicle_status_source_sha256': scene['city_vehicle_authority_source_sha256'],
            'council_designation_source_sha256': scene['council_designation_source_sha256'],
            'posting_authority_source_sha256': scene['posted_or_marked_authority_source_sha256'],
            'space_overlap_all_parked_frames': measured['all_footprints_overlap_governed_space'],
            'legal_judgment': None,
            'city_vehicle_scope_judgment': None}


def verify_source_kind(root, case_id):
    seal = root / 'capture-seal.json'
    if seal.is_file():
        payload = json.loads(seal.read_text(encoding='utf-8'))
        if (payload.get('format') != 'worker-sealed-capture' or
                payload.get('provenance_kind') != 'native' or
                payload.get('diagnostic_fixture') is not False or
                payload.get('frames') != 900 or
                payload.get('restoration', {}).get('restored') is not True):
            raise ValueError('sealed original Native City-space capture required')
        sources = payload.get('sources')
        mandatory = set(SOURCES) | {name + '.mkv' for name in CAMERAS}
        mandatory |= {'reviewed-sources/city-space-packet.json'}
        if not isinstance(sources, dict) or not mandatory <= set(sources):
            raise ValueError('original City-space source inventory incomplete')
        for name, digest in sources.items():
            if Path(name).is_absolute() or '..' in Path(name).parts or sha(required(root, name)) != digest:
                raise ValueError('sealed original source changed: ' + name)
        revision = payload.get('native_revision', {})
        if (revision.get('construction_sha256') != sha(required(root, 'construction.json')) or
                revision.get('runner_sha256') != sha(required(root, 'runner.py'))):
            raise ValueError('sealed Native implementation changed')
        retained = json.loads(required(root, 'reviewed-sources/city-space-packet.json').read_text())
        if retained.get('case_id') != case_id:
            raise ValueError('retained original packet case changed')
        return False
    note = json.loads(required(root, 'diagnostic-source-note.json').read_text())
    if (note.get('source_kind') != 'synthetic_diagnostic_fixture' or
            note.get('accepted_original_source') is not False or
            note.get('case_id') != case_id):
        raise ValueError('explicit synthetic City-space diagnostic provenance required')
    return True


def analyze(root):
    root = Path(root).resolve()
    config = json.loads(required(root, 'config.json').read_text(encoding='utf-8'))
    case_id = config.get('selected_case_id')
    case = next((item for item in CASES if ASSIGNMENT + '__' + item.name == case_id), None)
    if config.get('assignment_id') != ASSIGNMENT or case is None:
        raise ValueError('saved City-space case identity differs')
    diagnostic = verify_source_kind(root, case_id)
    context = json.loads(required(root, 'city-space-context.json').read_text(encoding='utf-8'))
    if context.get('format') != 'c229439-city-space-context-v1' or context.get('case_id') != case_id:
        raise ValueError('original City-space context differs')
    scene = context.get('scene')
    history = lines(root, 'original-city-space.jsonl')
    cameras = lines(root, 'camera-frame-map.jsonl')
    frames = lines(root, 'video_frames.jsonl')
    trace = lines(root, 'trace.jsonl')
    expected = 9 if diagnostic else 900
    if not all(len(part) == expected for part in (history, cameras, frames, trace)):
        raise ValueError('complete original or explicitly synthetic source joins required')
    for index, (row, camera, frame, graph) in enumerate(zip(history, cameras, frames, trace)):
        native = row.get('original_frame')
        if (camera.get('frame_index') != index or camera.get('native_frame') != native or
                camera.get('camera_frames') != {name: native for name in CAMERAS} or
                frame.get('video_frame') != index or frame.get('carla_frame') != native or
                frame.get('native_frame') != native or graph.get('frame') != native or
                abs(frame.get('time_s', -1) - row.get('time_s', -2)) > .002 or
                abs(camera.get('time_s', -1) - row.get('time_s', -2)) > .002):
            raise ValueError('original City-space/frame/camera join differs')
    measured = measure_original(history, scene, case,
                                diagnostic_frames=9 if diagnostic else None)
    source_hashes = {name: sha(required(root, name)) for name in SOURCES}
    channels = {
        'vehicle_status': lambda row: {'city_vehicle': row['city_vehicle'],
                                        'authority_sha256': row['city_vehicle_authority_source_sha256']},
        'space_authority': lambda row: {'designated': row['designated'], 'posted': row['posted'],
                                        'designation_sha256': row['council_designation_source_sha256'],
                                        'posting_sha256': row['posted_or_marked_authority_source_sha256']},
        'space_occupancy': lambda row: {'vehicle_footprint_rect_m': row['vehicle_footprint_rect_m'],
                                        'governed_space_rect_m': scene['governed_space_rect_m']},
        'parking_motion': lambda row: {'speed_mps': row['speed_mps'],
                                       'center_xy': row['vehicle_center_xy']},
        'camera_frame_identity': lambda row: row['original_frame'],
    }
    evidence = []
    description = config['case']['recording_description']
    for channel in description['channels']:
        name = channel['name']
        if name not in channels:
            raise ValueError('unknown City-space recording channel: ' + name)
        path = root / ('channel-' + name + '.jsonl')
        path.write_text(''.join(json.dumps({'time_s': row['time_s'],
                                             'value': channels[name](row)}) + '\n'
                                for row in history), encoding='utf-8')
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': path.name})
    for source in description['context_inputs']:
        name = source['name']
        if name == 'reviewed_city_space_authority':
            value = {field: scene[field + '_source_sha256'] for field in SOURCE_FIELDS}
        elif name == 'reviewed_vehicle_and_space_identity':
            value = {'vehicle_id': scene['vehicle_id'],
                     'parking_person_id': scene['parking_person_id'],
                     'governed_space_rect_m': scene['governed_space_rect_m']}
        else:
            raise ValueError('unknown City-space context input')
        path = root / ('context-' + name + '.json')
        path.write_text(json.dumps({name: value}, sort_keys=True) + '\n', encoding='utf-8')
        evidence.append({'name': name, 'unit': source['unit'], 'reference': path.name})
    from worker_exchange.native_output import write_result
    status = 'unverified' if diagnostic else 'met'
    physical = {part: {'status': status if part == 'maneuver' else 'unverified',
                       'method': 'original 900-frame source-bound parking and footprint observations',
                       'sources': source_hashes, 'legal_verdict_claimed': False}
                for part in ('setup', 'target', 'maneuver')}
    result = {'case_id': case_id,
              'measured_values': measured,
              'target_checks': [{'target': 'parked footprint in or out of Council space',
                                 'requested': case.inside_space,
                                 'measured': measured['all_footprints_overlap_governed_space'],
                                 'method': 'original complete vehicle footprint and reviewed space',
                                 'tolerance': 0, 'matched': True,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': source_hashes}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'source-bound parking measurement; independent pixel review pending',
              'physical_failure_flags': ['original physical outcome unverified'] if diagnostic else [],
              'physical_checks': physical, 'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': description, 'recording_evidence': evidence,
              'realized_observables': {}, 'diagnostic_fixture': diagnostic,
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    if not diagnostic:
        completion = assess(history, scene, case)
        result['physical_checks']['maneuver']['status'] = completion['status']
        result['maneuver_completed'] = completion['status'] == 'met'
        result['behavior_attempted'] = completion['status'] != 'unverified'
        result['setup_confirmed'] = completion['status'] == 'met'
        result['realized_observables'] = completion.get('realized_observables', {})
    write_result(root, result)
    return {'format': 'worker-analysis-report', 'case_id': case_id,
            'analysis_complete': True, 'diagnostic_fixture': diagnostic,
            'physical_acceptance_claimed': False,
            'measurements': {'city_space_conditions': {
                'value': measure_city_space(measured, scene),
                'method': 'measure_city_space', 'sources': source_hashes}},
            'limitations': ['Council designation, official posting, City-vehicle scope and pixels require independent review.',
                            'Synthetic diagnostic sources cannot establish original physical or legal findings.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior City-space analysis report')
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + '\n', encoding='utf-8')
