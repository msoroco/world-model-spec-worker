"""Saved-only U-turn analysis from retained Native frame and actor sources."""

import argparse
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path

from u_turn_measurement import measure
from u_turn_403_3_frontage import FRONTAGE_M, WINDOW_M, measure_frontage
from u_turn_227_divider import measure_divider_candidate
from u_turn_363_school import measure_school_candidate
from u_turn_407_geometry import validate_geometry_packet
from u_turn_407_measurement import measure_407_visibility
from types import SimpleNamespace


def _required(root, name):
    path = Path(root) / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required source: ' + name)
    return path, sha256(path.read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure_original_u_turn(motion_path, context_path):
    return measure(motion_path, context_path)


def measure_mapped_device(device_path, context_path):
    source = json.loads(Path(device_path).read_text())
    context = json.loads(Path(context_path).read_text())
    value = source.get('mapped_no_u_turn_device')
    if (not isinstance(value, dict) or not value.get('landmark_id') or
            value.get('road_id') != context.get('approach_road_id') or
            not isinstance(value.get('source_fields'), dict)):
        raise ValueError('Mapped no-U-turn landmark source differs')
    distance = value.get('distance_to_approach_m')
    if type(distance) not in (int, float) or not isfinite(distance) or distance > 30 or distance < 0:
        raise ValueError('Mapped no-U-turn landmark distance invalid')
    if any(value.get(key) is not None for key in
           ('official_device_status', 'governing_lane_status',
            'pixel_visibility_status')):
        raise ValueError('Unreviewed mapped landmark cannot claim official or visible status')
    label = ' '.join(str(x) for x in value['source_fields'].values()).lower().replace('_', ' ').replace('-', ' ')
    if not any(marker in label for marker in
               ('no u turn', 'u turn prohibited', 'u turn forbidden')):
        raise ValueError('Mapped source does not describe no-U-turn device')
    return value


def measure_built_frontage(frontage_path, context_path):
    source = json.loads(Path(frontage_path).read_text()).get('built_frontage_candidate')
    if not isinstance(source,dict):
        raise ValueError('Missing authored 403(3) built-frontage context')
    context = json.loads(Path(context_path).read_text())
    if (source.get('road_id') != context.get('approach_road_id') or
            source.get('approach_lane_id') != context.get('approach_lane_id') or
            source.get('opposite_lane_id') != context.get('opposite_lane_id') or
            source.get('window_m') != WINDOW_M or
            source.get('qualifying_frontage_m') != FRONTAGE_M or
            source.get('business_district_legal_judgment') is not None or
            source.get('intersection_exception_status') is not None or
            source.get('divided_highway_opening_exception_status') is not None or
            source.get('site_is_junction') is not False):
        raise ValueError('Original 403(3) frontage identity or legal status differs')
    recalculated = measure_frontage(source.get('buildings'),
                                   source.get('turn_xy_m'),
                                   source.get('forward_unit_xy'))
    for key in ('frontage_by_side', 'combined_built',
                'combined_sourced_qualifying_use'):
        if recalculated[key] != source.get(key):
            raise ValueError('Original 403(3) building frontage differs')
    if recalculated['combined_built']['frontage_m'] < FRONTAGE_M:
        raise ValueError('Original 403(3) built-frontage candidate absent')
    return source


def measure_mapped_divider(divider_path, context_path):
    source = json.loads(Path(divider_path).read_text()).get('divider_candidate')
    context = json.loads(Path(context_path).read_text())
    if (not isinstance(source,dict) or
            source.get('road_id') != context.get('approach_road_id') or
            source.get('approach_lane_id') != context.get('approach_lane_id') or
            source.get('opposite_lane_id') != context.get('opposite_lane_id') or
            any(source.get(key) is not None for key in
                ('divided_highway_legal_judgment','public_authority_opening_status',
                 'crossover_or_intersection_status')) or
            source.get('actual_barrier_crossing_verified') is not False):
        raise ValueError('Original 227 divider identity or legal status differs')
    def lane(xy,width,lane_id):
        forward = source['approach_forward_unit_xy']
        transform = SimpleNamespace(
            location=SimpleNamespace(x=xy[0],y=xy[1]),
            get_forward_vector=lambda:SimpleNamespace(x=forward[0],y=forward[1]))
        return SimpleNamespace(transform=transform,road_id=source['road_id'],
                               lane_id=lane_id,lane_width=width)
    scene = {'approach':lane(source['approach_xy_m'],source['lane_widths_m'][0],
                             source['approach_lane_id']),
             'opposite':lane(source['opposite_xy_m'],source['lane_widths_m'][1],
                             source['opposite_lane_id'])}
    recalculated = measure_divider_candidate(scene,source.get('nearby_divider_boxes',[]))
    for key in ('lane_center_separation_m','lane_widths_m',
                'unoccupied_lane_edge_gap_m','nearby_divider_boxes'):
        if recalculated[key] != source.get(key):
            raise ValueError('Original 227 divider geometry differs')
    if source['unoccupied_lane_edge_gap_m'] < 1.0 or not source['nearby_divider_boxes']:
        raise ValueError('Original 227 mapped divider candidate absent')
    return source


def measure_school_zone_candidate(school_path, context_path):
    source = json.loads(Path(school_path).read_text()).get('school_zone_candidate')
    context = json.loads(Path(context_path).read_text())
    if (not isinstance(source, dict) or
            source.get('road_id') != context.get('approach_road_id') or
            source.get('approach_lane_id') != context.get('approach_lane_id') or
            any(source.get(key) is not None for key in (
                'official_zone_designation', 'children_present',
                'school_in_session', 'governing_body_exempt_period',
                'operational_beacon', 'pupils_in_class',
                'yellow_beacon_lights_flashing',
                'sign_speed_limit_in_effect',
                'legal_prohibition_applicable'))):
        raise ValueError('Original 363 school-zone identity or legal status differs')
    xy = source.get('approach_xy_m')
    if not isinstance(xy, list) or len(xy) != 2:
        raise ValueError('Original 363 approach point missing')
    waypoint = SimpleNamespace(
        road_id=source['road_id'], lane_id=source['approach_lane_id'],
        transform=SimpleNamespace(location=SimpleNamespace(x=xy[0], y=xy[1])))
    recalculated = measure_school_candidate(
        {'approach': waypoint}, source.get('source_landmarks', []),
        max_distance_m=source.get('search_radius_m', 60.0))
    for key in recalculated:
        if source.get(key) != recalculated[key]:
            raise ValueError('Original 363 school-zone source differs: ' + key)
    if not source.get('matching_landmarks'):
        raise ValueError('Original 363 mapped school-zone candidate absent')
    return source


def measure_curve_crest_geometry(geometry_path, context_path):
    return validate_geometry_packet(json.loads(Path(geometry_path).read_text()),
                                    json.loads(Path(context_path).read_text()))


def measure_two_direction_500ft_visibility(capture_path, motion_path, context_path):
    return measure_407_visibility(capture_path, motion_path, context_path)


def analyze(attempt, *, write_channels=True):
    root = Path(attempt)
    config = json.loads(_required(root, 'config.json')[0].read_text())
    case_id = config.get('selected_case_id')
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-403-1', 'C230671', 'motor_vehicle_driver') or not (
            isinstance(case_id, str) and case_id.startswith(
                'heldout__C230671__NRS-484B-403-1__motor_vehicle_driver__')):
        raise ValueError('Wrong C230671 exact U-turn identity')
    paths = {name: _required(root, name) for name in (
        'u_turn_motion.jsonl', 'u_turn_context.json', 'video_frames.jsonl',
        'trace.jsonl')}
    motion = _rows(paths['u_turn_motion.jsonl'][0])
    mapping = _rows(paths['video_frames.jsonl'][0])
    trace = _rows(paths['trace.jsonl'][0])
    if not motion or len(motion) != len(mapping) or len(motion) != len(trace):
        raise ValueError('Original U-turn frame inventory differs')
    ego_id = motion[0].get('ego_id')
    if type(ego_id) is not int:
        raise ValueError('Original U-turn ego identity missing')
    for index, (row, frame, capture) in enumerate(zip(motion, mapping, trace)):
        identity = row.get('frame'), row.get('time_s')
        if (row.get('ego_id') != ego_id or frame.get('video_frame') != index or
                (frame.get('carla_frame'), frame.get('time_s')) != identity or
                (capture.get('frame'), capture.get('time_s')) != identity):
            raise ValueError('Original U-turn frame or ego join differs')
    value = measure_original_u_turn(paths['u_turn_motion.jsonl'][0],
                                    paths['u_turn_context.json'][0])
    source_hashes = {name: item[1] for name, item in paths.items()}
    measurements = {'u_turn_observation': {
        'method': 'measure_original_u_turn', 'value': value,
        'sources': source_hashes}}
    if case_id.endswith('__prohibition_403_2'):
        device_path, device_hash = _required(root, 'u_turn_device.json')
        measurements['mapped_no_u_turn_device'] = {
            'method': 'measure_mapped_device',
            'value': measure_mapped_device(device_path, paths['u_turn_context.json'][0]),
            'sources': {'u_turn_device.json': device_hash,
                        'u_turn_context.json': paths['u_turn_context.json'][1]}}
    if case_id.endswith('__prohibition_403_3'):
        frontage_path, frontage_hash = _required(root, 'u_turn_403_3_frontage.json')
        measurements['built_frontage_candidate'] = {
            'method': 'measure_built_frontage',
            'value': measure_built_frontage(frontage_path, paths['u_turn_context.json'][0]),
            'sources': {'u_turn_403_3_frontage.json': frontage_hash,
                        'u_turn_context.json': paths['u_turn_context.json'][1]}}
    if case_id.endswith('__prohibition_227'):
        divider_path, divider_hash = _required(root, 'u_turn_227_divider.json')
        measurements['divider_candidate'] = {
            'method': 'measure_mapped_divider',
            'value': measure_mapped_divider(divider_path, paths['u_turn_context.json'][0]),
            'sources': {'u_turn_227_divider.json': divider_hash,
                        'u_turn_context.json': paths['u_turn_context.json'][1]}}
    if case_id.endswith('__prohibition_363'):
        school_path, school_hash = _required(root, 'u_turn_363_school.json')
        measurements['school_zone_candidate'] = {
            'method': 'measure_school_zone_candidate',
            'value': measure_school_zone_candidate(school_path, paths['u_turn_context.json'][0]),
            'sources': {'u_turn_363_school.json': school_hash,
                        'u_turn_context.json': paths['u_turn_context.json'][1]}}
    if case_id.endswith('__prohibition_407'):
        geometry_path, geometry_hash = _required(root, 'u_turn_407_geometry.json')
        capture_path, capture_hash = _required(root, 'capture/evidence.jsonl')
        geometry = json.loads(geometry_path.read_text())
        context = json.loads(paths['u_turn_context.json'][0].read_text())
        measurements['curve_crest_geometry'] = {
            'method': 'measure_curve_crest_geometry',
            'value': measure_curve_crest_geometry(geometry_path, paths['u_turn_context.json'][0]),
            'sources': {'u_turn_407_geometry.json': geometry_hash,
                        'u_turn_context.json': paths['u_turn_context.json'][1]}}
        measurements['two_direction_500ft_visibility'] = {
            'method': 'measure_two_direction_500ft_visibility',
            'value': measure_two_direction_500ft_visibility(capture_path,
                        paths['u_turn_motion.jsonl'][0], paths['u_turn_context.json'][0]),
            'sources': {'capture/evidence.jsonl': capture_hash,
                        'u_turn_motion.jsonl': paths['u_turn_motion.jsonl'][1],
                        'u_turn_context.json': paths['u_turn_context.json'][1]}}
    if write_channels:
        channel = root / 'u_turn_observation.jsonl'
        if channel.exists():
            raise ValueError('Retain prior derived U-turn channel')
        channel.write_text(''.join(json.dumps({
            'frame': observation['frame'], 'time_s': observation['time_s'],
            'value': {'heading_change_deg': observation['heading_change_deg'],
                      'surface_gaps_m': observation['surface_gaps_m']}},
            allow_nan=False) + '\n' for observation in value['observations']))
        if case_id.endswith('__prohibition_407'):
            context_file = root/'u_turn_407_context.json'
            if context_file.exists():
                raise ValueError('Retain prior derived 407 context')
            context_file.write_text(json.dumps({
                'curve_crest_geometry': measurements['curve_crest_geometry']['value'],
                'two_direction_500ft_visibility': measurements['two_direction_500ft_visibility']['value']},
                allow_nan=False)+'\n')
    return {'format': 'worker-analysis-report', 'case_id': case_id,
            'measurements': measurements,
            'limitations': ['Source-shaped CPU media does not establish physical U-turn completion, sight lines, cited prohibition applicability or legal safety.'],
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


def build_result(attempt, report):
    root = Path(attempt)
    config = json.loads((root / 'config.json').read_text())
    description = config['case']['recording_description']
    value = report['measurements']['u_turn_observation']['value']
    channel = 'u_turn_observation.jsonl'
    evidence = [{'name': 'u_turn_observation', 'unit': 'structured',
                 'reference': channel, 'sha256': _required(root, channel)[1]},
                {'name': 'participant_roles', 'unit': 'structured context',
                 'reference': 'u_turn_context.json',
                 'sha256': _required(root, 'u_turn_context.json')[1]}]
    if report['case_id'].endswith('__prohibition_403_2'):
        evidence.append({'name': 'mapped_no_u_turn_device',
                         'unit': 'structured context',
                         'reference': 'u_turn_device.json',
                         'sha256': _required(root, 'u_turn_device.json')[1]})
    if report['case_id'].endswith('__prohibition_403_3'):
        evidence.append({'name': 'built_frontage_candidate',
                         'unit': 'structured context',
                         'reference': 'u_turn_403_3_frontage.json',
                         'sha256': _required(root, 'u_turn_403_3_frontage.json')[1]})
    if report['case_id'].endswith('__prohibition_227'):
        evidence.append({'name': 'divider_candidate',
                         'unit': 'structured context',
                         'reference': 'u_turn_227_divider.json',
                         'sha256': _required(root, 'u_turn_227_divider.json')[1]})
    if report['case_id'].endswith('__prohibition_363'):
        evidence.append({'name': 'school_zone_candidate',
                         'unit': 'structured context',
                         'reference': 'u_turn_363_school.json',
                         'sha256': _required(root, 'u_turn_363_school.json')[1]})
    if report['case_id'].endswith('__prohibition_407'):
        evidence.extend([
            {'name':'curve_crest_geometry','unit':'structured context',
             'reference':'u_turn_407_context.json',
             'sha256':_required(root,'u_turn_407_context.json')[1]},
            {'name':'two_direction_500ft_visibility','unit':'structured context',
             'reference':'u_turn_407_context.json',
             'sha256':_required(root,'u_turn_407_context.json')[1]}])
    return {'case_id': report['case_id'],
            'measured_values': {key: item['value'] for key, item in
                                report['measurements'].items()},
            'target_checks': [{'target': 'whole U-turn and surrounding-user safety',
                               'requested': 'retained original motion and context',
                               'measured': value['net_heading_change_deg'],
                               'method': 'joined Native 20 Hz actor bodies, yaw and speed',
                               'tolerance': None, 'matched': False,
                               'physical_cause_confirmed': False,
                               'cause_evidence': 'Saved source joined; physical and legal outcomes unverified'}],
            'setup_confirmed': False, 'behavior_attempted': True,
            'maneuver_completed': False,
            'termination_reason': 'Saved U-turn measurements complete; physical outcome unverified',
            'physical_failure_flags': {'detection_validated': False},
            'trace_reference': 'trace.jsonl',
            'video_references': ['overview.mkv', 'approach.mkv',
                                 'reference_corner.mkv', 'driver_reference.mkv'],
            'video_frame_map_reference': 'video_frames.jsonl',
            'recording_description': description, 'recording_evidence': evidence,
            'realized_observables': {'net_heading_change_deg': {
                'unit': 'degrees', 'method': 'original ego yaw difference',
                'time_window': 'all original frames', 'statistic': 'last',
                'reference': channel,
                'value': value['net_heading_change_deg'],
                'sample_window_s': [value['observations'][0]['time_s'],
                                    value['observations'][-1]['time_s']]}},
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = analyze(args.attempt)
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior U-turn analysis report')
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt, build_result(args.attempt, report))


if __name__ == '__main__':
    main()
