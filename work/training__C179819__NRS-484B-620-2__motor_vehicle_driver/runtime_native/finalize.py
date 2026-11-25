"""Finalize source-bound signed-zone measurements without a legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_zone import measure

LAW = 'After the establishment of a speed zone and the installation of appropriate signs to control speed, it is unlawful for any person to drive a motor vehicle upon the road and in the speed zone in excess of the speed therein authorized.'
SOURCES = ('road.xodr', 'zone-establishment.json', 'installed-sign-review.json',
           'actor-poses.jsonl', 'reference_corner.mkv')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHANNELS = ('kin.speed', 'dev.speed_limit_sign', 'dev.zone_sign',
            'drv.within_signed_zone', 'dev.governs', 'rel.occupies', 'ru.motor_vehicle')


def required(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_bound_zone_measurement(root):
    root = Path(root)
    road = required(root, 'road.xodr')
    establishment_path = required(root, 'zone-establishment.json')
    sign_path = required(root, 'installed-sign-review.json')
    pose_path = required(root, 'actor-poses.jsonl')
    pixels = required(root, 'reference_corner.mkv')
    establishment = json.loads(establishment_path.read_text())
    sign = json.loads(sign_path.read_text())
    diagnostic = (root / 'fixture-provenance.json').is_file()
    status = 'synthetic_diagnostic' if diagnostic else 'independently_reviewed'
    if establishment.get('review_status') != status or not establishment.get('reviewer'):
        raise ValueError('Independent zone establishment review required')
    if sign.get('review_status') != status or not sign.get('reviewer'):
        raise ValueError('Independent installed sign review required')
    if establishment.get('road_sha256') != sha(road) or sign.get('road_sha256') != sha(road):
        raise ValueError('Reviewed zone road differs from original source')
    if sign.get('pixel_source') != 'reference_corner.mkv' or sign.get('pixel_sha256') != sha(pixels):
        raise ValueError('Reviewed sign differs from original source pixels')
    if establishment.get('administrative_source') == sign.get('installed_sign_source'):
        raise ValueError('Zone establishment and installed sign require separate sources')
    if sign.get('authorized_value_source') != sign.get('installed_sign_source'):
        raise ValueError('Authorized speed is not bound to the installed sign')
    if establishment.get('road_id') != sign.get('road_id') or establishment.get('direction_id') != sign.get('direction_id'):
        raise ValueError('Zone and sign road or direction differ')
    context = {'source_kind': 'reviewed_signed_speed_zone', 'road_sha256': sha(road),
        'establishment_sha256': sha(establishment_path), 'installed_sign_sha256': sha(sign_path),
        'pixel_sha256': sha(pixels), 'zone_bounds_m': establishment.get('zone_bounds_m'),
        'authorized_mph': sign.get('authorized_mph'),
        'zone_established': establishment.get('zone_established'),
        'appropriate_sign_installed': sign.get('appropriate_sign_installed'),
        'sign_governs_route': sign.get('sign_governs_route')}
    for key in ('zone_established', 'appropriate_sign_installed', 'sign_governs_route'):
        if type(context[key]) is not bool:
            raise ValueError('Missing reviewed activation status: ' + key)
    rows = [json.loads(line) for line in pose_path.read_text().splitlines()]
    return measure(context, rows)


def statutory_context(root):
    law = json.loads(required(root, 'law-text.json').read_text())
    if law.get('source') != 'NRS 484B.620(2)' or law.get('text') != LAW:
        raise ValueError('Exact statutory source changed')
    return {'zone_establishment_and_sign_appropriateness': 'source_review_required',
            'legal_outcome': 'reserved', 'synthetic_diagnostic_is_not_authority': True}


def administrative_establishment_observation(root):
    value = source_bound_zone_measurement(root)
    return {'established': value['administrative_zone_establishment'],
            'administrative_source_separate_from_sign': True,
            'legal_authority': 'requires_original_review'}


def installed_sign_observation(root):
    value = source_bound_zone_measurement(root)
    return {'appropriate_sign_installed': value['appropriate_installed_sign'],
            'sign_governs_route': value['sign_governs_route'],
            'original_pixels_review_required': True}


def governed_zone_occupancy_observation(root):
    value = source_bound_zone_measurement(root)
    return {key: value[key] for key in ('first_zone_frame', 'last_zone_frame', 'zone_frame_count')}


def authorized_value_observation(root):
    value = source_bound_zone_measurement(root)
    return {'authorized_mph_from_installed_sign': value['authorized_mph'],
            'legal_authority': 'requires_original_review'}


def speed_boundary_observation(root):
    value = source_bound_zone_measurement(root)
    return {key: value[key] for key in ('observed_speed_mph_range_in_zone',
        'frames_below_authorized_in_zone', 'frames_at_authorized_in_zone',
        'frames_above_authorized_in_zone')}


def motor_vehicle_class_observation(root):
    source_bound_zone_measurement(root)
    establishment = json.loads(required(root, 'zone-establishment.json').read_text())
    return {'class_source': establishment['vehicle_class_source'],
            'original_blueprint_and_personal_driving_review_required': True}


def report(root):
    root = Path(root)
    config = json.loads(required(root, 'config.json').read_text())
    value = source_bound_zone_measurement(root)
    source_hashes = {name: sha(required(root, name)) for name in SOURCES}
    methods = {'source_bound_signed_zone_speed': ('source_bound_zone_measurement', value),
        'administrative_establishment': ('administrative_establishment_observation', administrative_establishment_observation(root)),
        'installed_sign': ('installed_sign_observation', installed_sign_observation(root)),
        'governed_road_direction_and_occupancy': ('governed_zone_occupancy_observation', governed_zone_occupancy_observation(root)),
        'authorized_posted_value': ('authorized_value_observation', authorized_value_observation(root)),
        'measured_speed_boundary': ('speed_boundary_observation', speed_boundary_observation(root)),
        'motor_vehicle_class': ('motor_vehicle_class_observation', motor_vehicle_class_observation(root))}
    measurements = {key: {'method': method, 'value': observed, 'sources': source_hashes}
                    for key, (method, observed) in methods.items()}
    measurements['statutory_context'] = {'method': 'statutory_context',
        'value': statutory_context(root), 'sources': {'law-text.json': sha(required(root, 'law-text.json'))}}
    return {'format': 'worker-analysis-report-v1', 'case_id': config['case_id'],
        'measurements': measurements,
        'scope': 'Original velocity and separately reviewed zone establishment and installed sign; legal outcome unassessed'}


def derive_channels(root, config):
    root = Path(root)
    poses = [json.loads(line) for line in required(root, 'actor-poses.jsonl').read_text().splitlines()]
    frames = [json.loads(line) for line in required(root, 'video_frames.jsonl').read_text().splitlines()]
    if len(poses) != 600 or len(frames) != 600:
        raise ValueError('Complete original frame join required')
    declared = {row['name'] for row in config['recording_description']['channels']}
    if declared != set(CHANNELS):
        raise ValueError('Declared signed-zone channels differ from finalizer')
    establishment = json.loads(required(root, 'zone-establishment.json').read_text())
    sign = json.loads(required(root, 'installed-sign-review.json').read_text())
    start, end = establishment['zone_bounds_m']
    channels = {name: [] for name in CHANNELS}
    for i, (pose, frame) in enumerate(zip(poses, frames)):
        if pose['video_frame'] != i or pose['native_frame'] != frame['native_frame'] or abs(pose['time_s'] - frame['time_s']) > 1e-6:
            raise ValueError('Original pose and frame identity differ')
        position = pose['route_position_m']
        inside = start <= position < end
        values = {
            'kin.speed': pose['observed_speed_mps'],
            'dev.speed_limit_sign': {'authorized_mph': sign['authorized_mph'], 'sign_sha256': sha(root / 'installed-sign-review.json')},
            'dev.zone_sign': {'zone_bounds_m': [start, end], 'establishment_sha256': sha(root / 'zone-establishment.json')},
            'drv.within_signed_zone': inside,
            'dev.governs': {'road_id': sign['road_id'], 'direction_id': sign['direction_id'], 'inside_zone': inside},
            'rel.occupies': {'route_position_m': position, 'inside_zone': inside},
            'ru.motor_vehicle': {'subject_id': pose.get('subject_id'), 'class_source': establishment.get('vehicle_class_source')}}
        for name, value in values.items():
            channels[name].append({'time_s': frame['time_s'], 'value': value})
    directory = root / 'channels'
    directory.mkdir(exist_ok=True)
    for name, rows in channels.items():
        (directory / (name + '.jsonl')).write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))


def finalize(root, output):
    from worker_exchange.native_output import physical_result, provenance_record, write_result
    root, output = Path(root), Path(output)
    if output.exists() or (root / 'result.json').exists():
        raise ValueError('Retain prior finalization; use a fresh stage')
    config = json.loads(required(root, 'config.json').read_text())
    analysis = report(root)
    derive_channels(root, config)
    measured = analysis['measurements']['source_bound_signed_zone_speed']['value']
    target_mph = {'below': 20, 'at': 25, 'above': 30}[config['speed_case']]
    speed_range = measured['observed_speed_mph_range_in_zone']
    target = {'target': 'original measured speed while inside reviewed signed zone',
        'requested': target_mph, 'measured': speed_range,
        'method': 'source-bound 600-frame Native velocity and reviewed zone bounds',
        'tolerance': 2, 'matched': speed_range[0] <= target_mph + 2 and speed_range[1] >= target_mph - 2,
        'physical_cause_confirmed': False, 'cause_evidence': list(SOURCES)}
    evidence = [{'name': name, 'unit': 'source', 'reference': name} for name in SOURCES]
    evidence += [{'name': row['name'], 'unit': row['unit'], 'reference': row['source']}
                 for row in config['recording_description']['channels']]
    result = {'case_id': config['case_id'], 'measured_values': measured,
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
    return analysis


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)


if __name__ == '__main__':
    main()
