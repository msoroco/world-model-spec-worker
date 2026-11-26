"""Analyze saved trail sources without converting requests into legal findings."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_trail import box, overlap

FRAMES = 600
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('vehicle-poses.jsonl', 'video_frames.jsonl', 'camera-frames.jsonl',
           'trail-inventory.json', 'trail-authority-context.json', 'road.xodr')


def required(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(root, name):
    return [json.loads(line) for line in required(root, name).read_text().splitlines()]


def measure_occupancy(observed, context):
    return {'occupancy_frames': observed['occupancy_frames'],
            'first_occupancy_frame': observed['first_occupancy_frame'],
            'original_footprint_joined': True, 'legal_verdict_claimed': False}


def measure_designation(observed, context):
    return {'requested': context['request']['official_designation'],
            'official_record_reviewed': context['official_record_reviewed'],
            'official_plan_source': context.get('official_plan_source'),
            'legal_verdict_claimed': False}


def measure_dedication(observed, context):
    return {'requested': context['request']['city_dedication'],
            'city_record_reviewed': context['city_record_reviewed'],
            'city_dedication_source': context.get('city_dedication_source'),
            'legal_verdict_claimed': False}


def measure_posting(observed, context):
    return {'requested': context['request']['appropriate_posting'],
            'sign_marker_observed': observed['sign_marker_observed'],
            'sign_wording_and_authority_reviewed': context['sign_wording_and_authority_reviewed'],
            'legal_verdict_claimed': False}


def measure_emergency(observed, context):
    return {'requested_kind': context['request']['exception_kind'],
            'original_blueprint_id': observed['vehicle_blueprint_id'],
            'emergency_identity_reviewed': context['emergency_identity_reviewed'],
            'legal_verdict_claimed': False}


def measure_maintenance(observed, context):
    return {'requested_kind': context['request']['exception_kind'],
            'this_right_of_way_use_reviewed': context['this_right_of_way_use_reviewed'],
            'maintenance_source': context.get('maintenance_source'),
            'legal_verdict_claimed': False}


def measure_mobility_device(observed, context):
    return {'requested_kind': context['request']['exception_kind'],
            'device_design_reviewed': context['device_design_reviewed'],
            'impaired_person_use_reviewed': context['impaired_person_use_reviewed'],
            'legal_verdict_claimed': False}


METHODS = {
    'trail_occupancy': ('measure_occupancy', measure_occupancy),
    'official_trails_plan_designation': ('measure_designation', measure_designation),
    'city_trail_dedication': ('measure_dedication', measure_dedication),
    'appropriate_prohibition_sign': ('measure_posting', measure_posting),
    'emergency_vehicle_exception': ('measure_emergency', measure_emergency),
    'right_of_way_maintenance_exception': ('measure_maintenance', measure_maintenance),
    'mobility_device_exception': ('measure_mobility_device', measure_mobility_device),
}


def observe(attempt, config, inventory):
    poses = rows(attempt, 'vehicle-poses.jsonl')
    mapping = rows(attempt, 'video_frames.jsonl')
    images = rows(attempt, 'camera-frames.jsonl')
    if len(poses) != FRAMES or len(mapping) != FRAMES or len(images) != FRAMES * len(CAMERAS):
        raise ValueError('Incomplete original trail/camera source frames')
    corridor = box(inventory.get('trail_right_of_way_m'), 'trail right-of-way')
    occupied = []
    first_blueprint = None
    for index, (pose, frame) in enumerate(zip(poses, mapping)):
        if pose.get('video_frame') != index or frame.get('video_frame') != index:
            raise ValueError('Original trail frame identity mismatch')
        native = frame.get('native_frame')
        if pose.get('native_frame') != native:
            raise ValueError('Original trail pose/frame join mismatch')
        if abs(pose['time_s'] - frame['time_s']) > 1e-4:
            raise ValueError('Original trail time join mismatch')
        if set(frame.get('camera_native_frames', {})) != set(CAMERAS):
            raise ValueError('Four source camera frame join absent')
        point = pose['vehicle_xyz_m']
        half_length, half_width = pose['bbox_half_length_m'], pose['bbox_half_width_m']
        footprint = box({'min_x': point[0] - half_length,
                         'max_x': point[0] + half_length,
                         'min_y': point[1] - half_width,
                         'max_y': point[1] + half_width}, 'vehicle footprint')
        occupied.append(overlap(footprint, corridor))
        first_blueprint = first_blueprint or pose.get('vehicle_blueprint_id')
    for image in images:
        index = image.get('frame')
        if type(index) is not int or not 0 <= index < FRAMES or image.get('camera') not in CAMERAS:
            raise ValueError('Invalid source camera image identity')
        if image.get('native_frame') != mapping[index]['native_frame']:
            raise ValueError('Source camera Native frame differs')
    return {'occupancy_frames': sum(occupied),
            'first_occupancy_frame': next((i for i, value in enumerate(occupied) if value), None),
            'sign_marker_observed': bool(inventory.get('sign_marker_native_readback')),
            'vehicle_blueprint_id': first_blueprint or inventory.get('subject_blueprint_id') or 'not_recorded'}


def finalize(attempt, output):
    from worker_exchange.native_output import provenance_record, write_result

    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Use fresh recorded-only analysis output')
    config = json.loads(required(attempt, 'config.json').read_text())
    inventory = json.loads(required(attempt, 'trail-inventory.json').read_text())
    context = json.loads(required(attempt, 'trail-authority-context.json').read_text())
    if context.get('request') != config.get('source_context_request'):
        raise ValueError('Trail authority context differs from selected request')
    if context.get('source_kind') not in ('original_native', 'synthetic_cpu'):
        raise ValueError('Trail authority source kind absent')
    observed = observe(attempt, config, inventory)
    contract = json.loads(required(attempt, 'measurement-contract.json').read_text())
    source_hashes = {name: sha(required(attempt, name)) for name in SOURCES}
    measurements = {}
    for requirement in contract['requirements']:
        key = requirement['output_key']
        method, function = METHODS[key]
        if method != requirement['method']:
            raise ValueError('Selected trail method changed')
        measurements[key] = {'method': method, 'value': function(observed, context),
                             'sources': {name: source_hashes[name]
                                         for name in requirement['inputs']}}
    provenance = provenance_record(attempt)
    original = provenance['provenance_kind'] == 'native' and not provenance['diagnostic_fixture']
    requested_inside = config['route_case'] == 'within'
    matched = (observed['occupancy_frames'] > 0) == requested_inside
    result = {
        'case_id': config['case_id'], 'measured_values': observed,
        'target_checks': [{'target': 'trail right-of-way occupancy',
                           'requested': {'within': requested_inside},
                           'measured': {'occupancy_frames': observed['occupancy_frames']},
                           'method': 'source-joined original vehicle footprint and surveyed corridor',
                           'tolerance': 'strict geometric overlap; not a legal cutoff',
                           'matched': matched, 'physical_cause_confirmed': False,
                           'cause_evidence': list(SOURCES)}],
        'setup_confirmed': False, 'behavior_attempted': original,
        'maneuver_completed': original and matched,
        'termination_reason': '600 original frames retained; independent source review pending',
        'physical_failure_flags': [] if matched else ['requested_occupancy_not_observed'],
        'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': [{'name': 'trail_occupancy', 'unit': 'structured',
                                'reference': 'vehicle-poses.jsonl'},
                               {'name': 'trail_source_context', 'unit': 'structured',
                                'reference': 'trail-authority-context.json'}],
        'realized_observables': {'trail_occupancy_frames': {
            'value': observed['occupancy_frames'], 'unit': 'frames',
            'method': 'original footprint/corridor intersection',
            'time_window': '600 source frames', 'statistic': 'count',
            'reference': 'vehicle-poses.jsonl'}},
        'provenance_kind': provenance['provenance_kind'],
        'diagnostic_fixture': provenance['diagnostic_fixture'],
        'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
    }
    write_result(attempt, result)
    report = {'format': 'c143691-trail-analysis-v1', 'case_id': config['case_id'],
              'analysis_complete': True, 'measurements': measurements,
              'source_hashes': source_hashes, 'provenance': provenance,
              'legal_verdict_claimed': False, 'physical_acceptance_claimed': False}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))
