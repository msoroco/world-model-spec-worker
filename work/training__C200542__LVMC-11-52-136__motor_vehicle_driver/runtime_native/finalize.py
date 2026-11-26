"""Finalize original aisle observations with separate authority reviews; no legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_aisle import CAMERAS, FRAMES, area, body_bbox, rows

LAW = 'No person shall park a vehicle in an access aisle.'
SOURCES = ('road.xodr', 'aisle-context.json', 'premises-review.json',
           'aisle-designation-review.json', 'parking-review.json',
           'native-vehicle.jsonl', 'video_frames.jsonl', 'reference_corner.mkv')
CHANNELS = ('st.parking_space', 'st.lane_marking', 'drv.standing_or_parked',
            'rel.occupies', 'kin.extent')


def required(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measured(root):
    root = Path(root)
    paths = {name: required(root, name) for name in SOURCES}
    context = json.loads(paths['aisle-context.json'].read_text())
    premises = json.loads(paths['premises-review.json'].read_text())
    designation = json.loads(paths['aisle-designation-review.json'].read_text())
    parking = json.loads(paths['parking-review.json'].read_text())
    diagnostic = (root / 'fixture-provenance.json').is_file()
    expected = 'synthetic_diagnostic' if diagnostic else 'independently_reviewed'
    for review in (premises, designation, parking):
        if review.get('review_status') != expected or not review.get('reviewer'):
            raise ValueError('Independent premises, designation and parking review required')
    if len({premises.get('source'), designation.get('source'), parking.get('source')}) != 3:
        raise ValueError('Premises, designation and parking sources must be separate')
    if premises.get('road_sha256') != sha(paths['road.xodr']):
        raise ValueError('Public-access premises road differs')
    if designation.get('road_sha256') != sha(paths['road.xodr']):
        raise ValueError('Access-aisle designation road differs')
    if designation.get('pixel_sha256') != sha(paths['reference_corner.mkv']):
        raise ValueError('Access-aisle review pixels differ')
    if parking.get('motion_sha256') != sha(paths['native-vehicle.jsonl']):
        raise ValueError('Parking classification motion differs')
    if context.get('source_kind') != 'original_native' or context.get('cell_id') != 'C200542':
        raise ValueError('Original Native aisle context differs')
    aisle = designation.get('access_aisle')
    if not isinstance(aisle, dict) or aisle != context.get('access_aisle'):
        raise ValueError('Reviewed access-aisle bounds differ from original context')
    if designation.get('adjacent_accessible_bay') != context.get('adjacent_accessible_bay'):
        raise ValueError('Reviewed adjacent accessible space differs')
    if not designation.get('contrasting_marking_or_paving'):
        raise ValueError('Contrasting aisle marking or paving source absent')
    if designation.get('vehicle_ingress_egress') is not True or designation.get('accessible_route_connectivity') is not True:
        raise ValueError('Aisle ingress, egress and accessible route source absent')
    route = designation.get('designation_route')
    if route == '11.52.135(A)_sign':
        sign = designation.get('conditional_11_52_135A_sign')
        if not isinstance(sign, dict) or sign.get('access_symbol') is not True or not sign.get('minimum_fine_wording_or_equivalent') or type(sign.get('sign_bottom_height_ft')) not in (int, float) or sign['sign_bottom_height_ft'] < 4:
            raise ValueError('Conditional 11.52.135(A) sign source incomplete')
    elif route != 'direct_marking_and_accessible_bay':
        raise ValueError('Aisle designation source route absent')
    if type(premises.get('public_access')) is not bool or type(designation.get('official_access_aisle')) is not bool:
        raise ValueError('Reviewed public access or aisle designation absent')
    if premises.get('jurisdiction_reviewed') is not True:
        raise ValueError('Public-access jurisdiction source absent')
    if type(parking.get('parked')) is not bool:
        raise ValueError('Independent parked classification absent')
    if parking.get('vehicle_class') != 'motor_vehicle' or not parking.get('responsible_person'):
        raise ValueError('Vehicle and responsible-person source absent')
    for key in ('occupancy', 'loading_purpose', 'actual_loading_activity'):
        if not parking.get(key):
            raise ValueError('Parking activity source absent: ' + key)
    motions = rows(paths['native-vehicle.jsonl'])
    frames = rows(paths['video_frames.jsonl'])
    first_overlap = None
    overlap_samples = stationary_overlap_samples = 0
    channels = {name: [] for name in CHANNELS}
    prior_native = -1
    for i, (motion, frame) in enumerate(zip(motions, frames)):
        native = motion.get('native_frame')
        if type(native) is not int or native <= prior_native or frame.get('native_frame') != native:
            raise ValueError('Original Native frame join differs')
        prior_native = native
        if motion.get('video_frame') != i or frame.get('video_frame') != i or abs(motion.get('time_s', -1) - i / 20) > 1e-6 or abs(frame.get('time_s', -1) - i / 20) > 1e-6:
            raise ValueError('Original frame/time join differs')
        if frame.get('camera_native_frames') != {name: native for name in CAMERAS}:
            raise ValueError('Original four-camera join differs')
        box = body_bbox(motion.get('body_xy_m'))
        speed = motion.get('speed_mps')
        if type(speed) not in (int, float) or speed < 0:
            raise ValueError('Original vehicle speed invalid')
        overlap = area(box, aisle)
        if overlap > 0:
            overlap_samples += 1
            if first_overlap is None:
                first_overlap = i
            if speed == 0:
                stationary_overlap_samples += 1
        values = {
            'st.parking_space': {'official_access_aisle': designation['official_access_aisle'], 'review_sha256': sha(paths['aisle-designation-review.json'])},
            'st.lane_marking': {'pixel_sha256': sha(paths['reference_corner.mkv']), 'reviewed': True},
            'drv.standing_or_parked': {'speed_mps': speed, 'parked_review': parking['parked']},
            'rel.occupies': {'overlap_area_m2': overlap},
            'kin.extent': {'body_xy_m': motion['body_xy_m']}}
        for name, value in values.items():
            channels[name].append({'time_s': i / 20, 'value': value})
    for name in CAMERAS:
        required(root, name + '.mkv')
    return {'frame_count': FRAMES, 'first_overlap_frame': first_overlap,
            'overlap_samples': overlap_samples,
            'stationary_overlap_samples': stationary_overlap_samples,
            'public_access_review': premises['public_access'],
            'official_access_aisle_review': designation['official_access_aisle'],
            'parked_classification_review': parking['parked'],
            'legal_verdict_claimed': False,
            'source_sha256': {name: sha(path) for name, path in paths.items()}}, channels


def premises_observation(root):
    value, _ = measured(root)
    return {'public_access': value['public_access_review']}


def designation_observation(root):
    value, _ = measured(root)
    designation = json.loads(required(root, 'aisle-designation-review.json').read_text())
    return {'official_access_aisle': value['official_access_aisle_review'],
            'marking_or_paving': designation['contrasting_marking_or_paving'],
            'adjacent_accessible_bay': designation['adjacent_accessible_bay'],
            'vehicle_ingress_egress': designation['vehicle_ingress_egress'],
            'accessible_route_connectivity': designation['accessible_route_connectivity'],
            'designation_route': designation['designation_route'],
            'conditional_sign': designation['conditional_11_52_135A_sign']}


def parking_observation(root):
    value, _ = measured(root)
    parking = json.loads(required(root, 'parking-review.json').read_text())
    return {'parked': value['parked_classification_review'],
            'vehicle_class': parking['vehicle_class'],
            'responsible_person': parking['responsible_person'],
            'occupancy': parking['occupancy'],
            'loading_purpose': parking['loading_purpose'],
            'actual_loading_activity': parking['actual_loading_activity']}


def overlap_observation(root):
    value, _ = measured(root)
    return {'stationary_overlap_samples': value['stationary_overlap_samples']}


def report(root):
    root = Path(root)
    config = json.loads(required(root, 'config.json').read_text())
    law = json.loads(required(root, 'law-text.json').read_text())
    if law.get('text') != LAW or law.get('source') != 'LVMC 11.52.136':
        raise ValueError('Exact statutory text differs')
    value, channels = measured(root)
    source_hashes = value['source_sha256']
    methods = {
        'source_bound_aisle_parking': ('measured', value),
        'public_access_premises': ('premises_observation', {'public_access': value['public_access_review']}),
        'official_access_aisle': ('designation_observation', {'official_access_aisle': value['official_access_aisle_review']}),
        'parked_vehicle': ('parking_observation', {'parked': value['parked_classification_review']}),
        'body_aisle_overlap': ('overlap_observation', {'stationary_overlap_samples': value['stationary_overlap_samples']})}
    measurements = {key: {'method': method, 'value': observed, 'sources': source_hashes}
                    for key, (method, observed) in methods.items()}
    measurements['statutory_context'] = {'method': 'statutory_context',
        'value': {'legal_outcome': 'reserved', 'synthetic_diagnostic_is_not_authority': True},
        'sources': {'law-text.json': sha(root / 'law-text.json')}}
    return {'format': 'worker-analysis-report-v1', 'case_id': config['case_id'],
            'measurements': measurements, 'scope': 'Original body/aisle overlap with separate public-access, designation and parking review'}, channels


def finalize(root, output):
    from worker_exchange.native_output import physical_result, provenance_record, write_result
    root, output = Path(root), Path(output)
    if output.exists() or (root / 'result.json').exists():
        raise ValueError('Use a fresh finalization stage')
    config = json.loads(required(root, 'config.json').read_text())
    analysis, channels = report(root)
    if {row['name'] for row in config['recording_description']['channels']} != set(CHANNELS):
        raise ValueError('Declared aisle channels differ')
    directory = root / 'channels'
    directory.mkdir(exist_ok=True)
    for name, values in channels.items():
        (directory / (name + '.jsonl')).write_text(''.join(json.dumps(v, allow_nan=False) + '\n' for v in values))
    value = analysis['measurements']['source_bound_aisle_parking']['value']
    target_inside = config['case_suffix'] == 'controlled_2'
    target = {'target': 'original stationary full-body overlap with independently reviewed access aisle',
              'requested': 'inside' if target_inside else 'outside', 'measured': value['stationary_overlap_samples'],
              'method': 'source-bound 600-frame Native body corners and speed', 'tolerance': 0,
              'matched': (value['stationary_overlap_samples'] > 0) == target_inside,
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
