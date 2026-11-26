"""Finalize parking source joins; physical and legal outcomes remain for independent review."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_parking import CAMERAS, FRAMES, measure

SOURCES = ('road.xodr', 'frontage-inventory.json', 'park-review.json',
           'vehicle-spec-review.json', 'exception-review.json',
           'vehicle-poses.jsonl', 'video_frames.jsonl', 'overview.mkv')
CHANNELS = ('vehicle_pose_and_speed', 'park_frontage_geometry', 'source_camera_frame_join',
            'ru.commercial_motor_vehicle', 'ru.trailer_or_combination', 'kin.extent',
            'drv.standing_or_parked', 'st.roadway', 'dev.regulatory_sign',
            'st.driveway_or_alley_entrance', 'sig.door_open', 'ru.occupant_count',
            'kin.time', 'dev.temporary_traffic_control')


def required(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def measured(root):
    root = Path(root)
    paths = {name: required(root, name) for name in SOURCES}
    for name in CAMERAS:
        required(root, name + '.mkv')
    inventory = json.loads(paths['frontage-inventory.json'].read_text())
    park = json.loads(paths['park-review.json'].read_text())
    vehicle = json.loads(paths['vehicle-spec-review.json'].read_text())
    exception = json.loads(paths['exception-review.json'].read_text())
    diagnostic = (root / 'fixture-provenance.json').is_file()
    expected = 'synthetic_diagnostic' if diagnostic else 'independently_reviewed'
    for review in (park, vehicle, exception):
        if review.get('review_status') != expected or not review.get('reviewer'):
            raise ValueError('Independent park, vehicle and exception review required')
    if len({park.get('source'), vehicle.get('source'), exception.get('source')}) != 3:
        raise ValueError('Park, vehicle and exception source identities must be separate')
    road_hash = sha(paths['road.xodr'])
    if inventory.get('cell_id') != 'C135709' or inventory.get('source_kind') != 'native_saved_sample':
        raise ValueError('Original frontage inventory differs')
    if park.get('road_sha256') != road_hash or (park.get('pixel_sha256') != sha(paths['overview.mkv']) and not (diagnostic and park.get('pixel_sha256') == 'synthetic_rgb_source')):
        raise ValueError('Park status source does not bind original road and pixels')
    if any(type(park.get(key)) is not bool for key in ('residence_district_300ft', 'public_school')):
        raise ValueError('Alternative frontage classification source absent')
    if park.get('public_access') is not True or park.get('jurisdiction_reviewed') is not True or not park.get('designation_source'):
        raise ValueError('Public park access, designation or jurisdiction source absent')
    if park.get('park_status') != 'public_park' or park.get('park_bounds_m') != inventory.get('park_bounds_m'):
        raise ValueError('Public park designation or bounds absent')
    if exception.get('road_sha256') != road_hash or (exception.get('pixel_sha256') != sha(paths['overview.mkv']) and not (diagnostic and exception.get('pixel_sha256') == 'synthetic_rgb_source')):
        raise ValueError('Posted permission and exception review does not bind original sources')
    if vehicle.get('pose_sha256') != sha(paths['vehicle-poses.jsonl']):
        raise ValueError('Vehicle specification source does not bind observed vehicle')
    if type(vehicle.get('trailer_present')) is not bool or type(vehicle.get('occupant_count')) is not int:
        raise ValueError('Vehicle trailer and occupancy source absent')
    if not vehicle.get('commercial_enterprise_basis') or not vehicle.get('design_maintenance_or_use'):
        raise ValueError('Commercial enterprise design, maintenance or use source absent')
    if vehicle.get('vehicle_class') != 'commercial_motor_vehicle':
        raise ValueError('Commercial vehicle classification source absent')
    for key in ('posted_permission', 'expeditious_loading', 'essential_local_service',
                'door_open_observed', 'service_ttc_observed'):
        if type(exception.get(key)) is not bool:
            raise ValueError('Exception source absent: ' + key)
    for key in ('device_wording', 'device_authority', 'governed_area',
                'parking_purpose', 'actual_transfer_activity',
                'section_wide_exceptions_review', 'storage_meaning_review',
                'modifier_scope_review'):
        if not isinstance(exception.get(key), str) or not exception[key]:
            raise ValueError('Device, parking activity or legal review source absent: ' + key)
    if not isinstance(exception.get('property_frontage'), str) or not exception['property_frontage']:
        raise ValueError('Loading property frontage source absent')
    if not isinstance(exception.get('loading_activity_source'), str) or not exception['loading_activity_source']:
        raise ValueError('Loading activity source absent')
    if not isinstance(exception.get('service_activity_source'), str) or not exception['service_activity_source']:
        raise ValueError('Service activity source absent')
    poses = rows(paths['vehicle-poses.jsonl'])
    frames = rows(paths['video_frames.jsonl'])
    if len(poses) != FRAMES or len(frames) != FRAMES:
        raise ValueError('Incomplete original 600-frame source join')
    observations = []
    channels = {name: [] for name in CHANNELS}
    prior_native = -1
    for i, (pose, frame) in enumerate(zip(poses, frames)):
        native = pose.get('native_frame')
        if type(native) is not int or native <= prior_native or frame.get('native_frame') != native:
            raise ValueError('Original Native frame join differs')
        prior_native = native
        if pose.get('video_frame') != i or frame.get('video_frame') != i:
            raise ValueError('Original video frame join differs')
        if abs(pose.get('time_s', -1) - i / 20) > 1e-6 or abs(frame.get('time_s', -1) - i / 20) > 1e-6:
            raise ValueError('Original frame/time join differs')
        cameras = {name: native for name in CAMERAS}
        if pose.get('camera_native_frames') != cameras or frame.get('camera_native_frames') != cameras:
            raise ValueError('Original four-camera frame join differs')
        xyz = pose.get('vehicle_xyz_m')
        if not isinstance(xyz, list) or len(xyz) != 3:
            raise ValueError('Original vehicle pose absent')
        half_length = pose.get('bbox_half_length_m')
        half_width = pose.get('bbox_half_width_m')
        if type(half_length) not in (float, int) or type(half_width) not in (float, int) or half_length <= 0 or half_width <= 0:
            raise ValueError('Original body extent absent')
        footprint = {'min_x': xyz[0] - half_length, 'max_x': xyz[0] + half_length,
                     'min_y': xyz[1] - half_width, 'max_y': xyz[1] + half_width}
        observations.append({'video_frame': i, 'native_frame': native, 'time_s': i / 20,
                             'source_cameras': {name: i for name in CAMERAS},
                             'observed_speed_mps': pose['observed_speed_mps'],
                             'vehicle_footprint_m': footprint})
        values = {'vehicle_pose_and_speed': {'xyz_m': xyz, 'speed_mps': pose['observed_speed_mps']},
                  'park_frontage_geometry': {'footprint_m': footprint, 'park_bounds_m': park['park_bounds_m']},
                  'source_camera_frame_join': cameras,
                  'ru.commercial_motor_vehicle': {'vehicle_class': vehicle['vehicle_class']},
                  'ru.trailer_or_combination': {'trailer_present': vehicle['trailer_present']},
                  'kin.extent': {'overall_length_m': vehicle['vehicle_overall_length_m'], 'body_extent_m': [half_length * 2, half_width * 2]},
                  'drv.standing_or_parked': {'speed_mps': pose['observed_speed_mps'], 'stationary': pose['observed_speed_mps'] <= 0.10},
                  'st.roadway': {'road_sha256': road_hash},
                  'dev.regulatory_sign': {'posted_permission': exception['posted_permission']},
                  'st.driveway_or_alley_entrance': {'property_frontage': exception['property_frontage']},
                  'sig.door_open': {'door_open_observed': exception['door_open_observed']},
                  'ru.occupant_count': {'count': vehicle['occupant_count']},
                  'kin.time': {'original_time_s': i / 20},
                  'dev.temporary_traffic_control': {'service_ttc_observed': exception['service_ttc_observed']}}
        for name, value in values.items():
            channels[name].append({'time_s': i / 20, 'value': value})
    context = {'source_kind': 'native_map_and_external_status_readback',
               'native_map_sha256': road_hash,
               'park_status_document_sha256': sha(paths['park-review.json']),
               'vehicle_specification_sha256': sha(paths['vehicle-spec-review.json']),
               'vehicle_class': vehicle['vehicle_class'],
               'vehicle_overall_length_m': vehicle['vehicle_overall_length_m'],
               'vehicle_unladen_mass_kg': vehicle['vehicle_unladen_mass_kg'],
               'street_bounds_m': inventory['street_bounds_m'],
               'park_bounds_m': park['park_bounds_m'], 'park_status': park['park_status']}
    outcome = measure(context, observations)
    outcome['posted_permission_review'] = exception['posted_permission']
    outcome['expeditious_loading_review'] = exception['expeditious_loading']
    outcome['essential_local_service_review'] = exception['essential_local_service']
    outcome['public_park_review'] = park['park_status']
    outcome['public_access_review'] = park['public_access']
    outcome['jurisdiction_review'] = park['jurisdiction_reviewed']
    outcome['commercial_enterprise_basis'] = vehicle['commercial_enterprise_basis']
    outcome['design_maintenance_or_use'] = vehicle['design_maintenance_or_use']
    outcome['device_wording'] = exception['device_wording']
    outcome['device_authority'] = exception['device_authority']
    outcome['governed_area'] = exception['governed_area']
    outcome['parking_purpose'] = exception['parking_purpose']
    outcome['actual_transfer_activity'] = exception['actual_transfer_activity']
    outcome['section_wide_exceptions_review'] = exception['section_wide_exceptions_review']
    outcome['storage_meaning_review'] = exception['storage_meaning_review']
    outcome['modifier_scope_review'] = exception['modifier_scope_review']
    outcome['residence_district_300ft_review'] = park['residence_district_300ft']
    outcome['public_school_review'] = park['public_school']
    outcome['legal_verdict_claimed'] = False
    outcome['source_sha256'] = {name: sha(path) for name, path in paths.items()}
    return outcome, channels


def park_observation(root):
    value, _ = measured(root)
    return {'park_status': value['public_park_review'], 'overlap_at_rest': value['park_frontage_overlap_at_rest']}


def vehicle_observation(root):
    value, _ = measured(root)
    return {'overall_length_m': value['vehicle_overall_length_m'],
            'unladen_mass_kg': value['vehicle_unladen_mass_kg'],
            'length_at_least_24_feet': value['length_at_least_24_feet'],
            'unladen_mass_over_8000_pounds': value['unladen_mass_over_8000_pounds']}


def alternative_place_observation(root):
    value, _ = measured(root)
    return {'residence_district_300ft': value['residence_district_300ft_review'],
            'public_school': value['public_school_review']}


def sign_observation(root):
    value, _ = measured(root)
    return {'posted_permission': value['posted_permission_review']}


def loading_observation(root):
    value, _ = measured(root)
    return {'expeditious_loading': value['expeditious_loading_review']}


def service_observation(root):
    value, _ = measured(root)
    return {'essential_local_service': value['essential_local_service_review']}


def exception_observation(root):
    value, _ = measured(root)
    return {key: value[key] for key in ('posted_permission_review',
            'expeditious_loading_review', 'essential_local_service_review')}


def park_context_observation(root):
    value, _ = measured(root)
    return {'public_park': value['public_park_review'],
            'public_access': value['public_access_review'],
            'jurisdiction_reviewed': value['jurisdiction_review']}


def commercial_basis_observation(root):
    value, _ = measured(root)
    return {'basis': value['commercial_enterprise_basis'],
            'design_maintenance_or_use': value['design_maintenance_or_use']}


def parking_purpose_observation(root):
    value, _ = measured(root)
    return {'purpose': value['parking_purpose'],
            'actual_transfer_activity': value['actual_transfer_activity'],
            'storage_meaning_review': value['storage_meaning_review']}


def device_observation(root):
    value, _ = measured(root)
    return {'wording': value['device_wording'], 'authority': value['device_authority'],
            'governed_area': value['governed_area'],
            'posted_permission': value['posted_permission_review']}


def interpretive_reservations_observation(root):
    value, _ = measured(root)
    return {'modifier_scope': value['modifier_scope_review'],
            'section_wide_exceptions': value['section_wide_exceptions_review']}

def report(root):
    root = Path(root)
    config = json.loads(required(root, 'config.json').read_text())
    value, channels = measured(root)
    sources = value['source_sha256']
    items = {'parking_adjacency': ('measured', value),
             'posted_sign_permission': ('sign_observation', sign_observation(root)),
             'residence_district_definition': ('alternative_place_observation', alternative_place_observation(root)),
             'public_school': ('alternative_place_observation', alternative_place_observation(root)),
             'loading_delivery_exception': ('loading_observation', loading_observation(root)),
             'essential_local_service_exception': ('service_observation', service_observation(root)),
             'size_weight_scope': ('vehicle_observation', vehicle_observation(root)),
             'public_park_access_jurisdiction': ('park_context_observation', park_context_observation(root)),
             'commercial_enterprise_basis': ('commercial_basis_observation', commercial_basis_observation(root)),
             'parking_purpose_storage': ('parking_purpose_observation', parking_purpose_observation(root)),
             'device_authority_area': ('device_observation', device_observation(root)),
             'modifier_scope_exceptions': ('interpretive_reservations_observation', interpretive_reservations_observation(root))}
    measurements = {key: {'method': method, 'value': observed, 'sources': sources}
                    for key, (method, observed) in items.items()}
    return {'format': 'worker-analysis-report-v1', 'case_id': config['case_id'],
            'measurements': measurements,
            'scope': 'Original parking motion and independent park, vehicle and exception reviews'}, channels


def finalize(root, output):
    from worker_exchange.native_output import physical_result, provenance_record, write_result
    root, output = Path(root), Path(output)
    if output.exists() or (root / 'result.json').exists():
        raise ValueError('Use a fresh finalization stage')
    config = json.loads(required(root, 'config.json').read_text())
    analysis, channels = report(root)
    if {row['name'] for row in config['recording_description']['channels']} != set(CHANNELS):
        raise ValueError('Declared parking channels differ')
    channel_dir = root / 'channels'
    channel_dir.mkdir(exist_ok=True)
    for name, values in channels.items():
        (channel_dir / (name + '.jsonl')).write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in values))
    value = analysis['measurements']['parking_adjacency']['value']
    requested = config['parking_case'] == 'beside'
    target = {'target': 'original stationary footprint within surveyed public park frontage',
              'requested': 'beside' if requested else 'away',
              'measured': value['park_frontage_overlap_at_rest'],
              'method': 'source-bound 600-frame Native body and speed', 'tolerance': 0,
              'matched': value['park_frontage_overlap_at_rest'] == requested,
              'physical_cause_confirmed': False, 'cause_evidence': list(SOURCES)}
    evidence = [{'name': name, 'unit': 'source', 'reference': name} for name in SOURCES]
    evidence += [{'name': row['name'], 'unit': row['unit'], 'reference': row['source']}
                 for row in config['recording_description']['channels']]
    result = {'case_id': config['case_id'], 'measured_values': value,
              'target_checks': [target], 'setup_confirmed': False,
              'behavior_attempted': False, 'maneuver_completed': False,
              'termination_reason': 'Awaiting original source and physical review',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['recording_description'],
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
