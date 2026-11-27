"""Saved-only, source-joined encounter measurement; no mental-state verdict."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from native.person_interaction import FRAME_COUNT, measure_trace
from native.person_scene import require_source_packet


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def require_file(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def measure_intro(measured, packet):
    return {'vehicle_driver_present': measured['frames'] == FRAME_COUNT,
            'original_driver_source': packet['driver_identity_source'],
            'original_vehicle_class_source': packet['vehicle_class_source']}


def measure_clause(measured, packet):
    return {'minimum_person_surface_gap_m': measured['minimum_person_surface_gap_m'],
            'minimum_projected_ttc_s': measured['minimum_projected_ttc_s'],
            'maximum_ego_speed_mps': measured['maximum_ego_speed_mps'],
            'maximum_abs_longitudinal_accel_mps2': measured['maximum_abs_ego_longitudinal_accel_mps2'],
            'maximum_abs_yaw_rate_radps': measured['maximum_abs_ego_yaw_rate_radps'],
            'minimum_person_accel_mps2': measured['minimum_person_accel_mps2'],
            'contact_frames': measured['contact_frames'],
            'access_kind_claimed_by_source': packet['access_kind'],
            'public_access_source': packet['highway_or_public_access_source'],
            'mental_state_verdict': None}


def measure_scope(measured, packet):
    return {'worker_identity_source': packet['worker_identity_source'],
            'worker_role_source': packet['worker_role_source'],
            'worker_route_relation_source': packet['worker_route_relation_source'],
            'sight_line_source': packet['sight_line_source'],
            'surface_condition_source': packet['surface_condition_source'],
            'nearby_property_source': packet['nearby_property_source'],
            'complete_encounter_frames': measured['frames']}


def analyze(attempt):
    root = Path(attempt).resolve()
    config_path = require_file(root, 'config.json')
    config = json.loads(config_path.read_text())
    case_id = config.get('case_id') or config.get('selected_case_id')
    packet_path = require_file(root, 'original-context-packet.json')
    packet = require_source_packet(json.loads(packet_path.read_text()), case_id)
    raw_path = require_file(root, 'native-person-interaction.jsonl')
    map_path = require_file(root, 'video_frames.jsonl')
    road_path = require_file(root, 'native-road-readback.json')
    road = json.loads(road_path.read_text())
    raw = rows(raw_path)
    mapping = rows(map_path)
    if len(raw) != FRAME_COUNT or len(mapping) != FRAME_COUNT:
        raise ValueError('Missing complete original encounter timeline')
    if road.get('driving_road_id') != 1 or road.get('driving_lane_id') != -1:
        raise ValueError('Original paved driving route readback missing')
    for index, (source, frame) in enumerate(zip(raw, mapping)):
        if (source.get('frame') != index or frame.get('video_frame') != index or
                source.get('native_frame') != frame.get('native_frame') or
                source.get('ego_actor_id') == source.get('person_actor_id') or
                not str(source.get('ego_blueprint_id', '')).startswith('vehicle.') or
                not str(source.get('person_blueprint_id', '')).startswith('walker.pedestrian.')):
            raise ValueError('Original distinct vehicle/person or frame join failed')
        camera_frames = frame.get('camera_native_frames', {})
        if set(camera_frames) != {'overview', 'approach', 'reference_corner', 'driver_reference'} or any(
                value != frame['native_frame'] for value in camera_frames.values()):
            raise ValueError('Original four-camera frame join failed')
    measured = measure_trace(raw, {
        'access_kind': packet['access_kind'],
        'public_access_source': packet['highway_or_public_access_source'],
        'driver_source': packet['driver_identity_source'],
        'person_actor_source': packet['worker_identity_source']})
    source_hashes = {name: sha(root / name) for name in (
        'config.json', 'original-context-packet.json', 'native-person-interaction.jsonl',
        'video_frames.jsonl', 'native-road-readback.json')}
    requirements = {
        'intro': ('measure_intro', measure_intro(measured, packet),
                  ('native-person-interaction.jsonl', 'original-context-packet.json')),
        'clause': ('measure_clause', measure_clause(measured, packet),
                   ('native-person-interaction.jsonl', 'original-context-packet.json',
                    'video_frames.jsonl', 'native-road-readback.json')),
        'scope': ('measure_scope', measure_scope(measured, packet),
                  ('native-person-interaction.jsonl', 'original-context-packet.json'))}
    measurements = {name: {'method': method, 'value': value,
                           'sources': {key: source_hashes[key] for key in keys}}
                    for name, (method, value, keys) in requirements.items()}
    return {'format': 'c179799-saved-interaction-analysis-v1',
            'case_id': case_id, 'candidate_id': config.get('candidate_id'),
            'source_complete': True, 'selected_branch_measurement': measured,
            'measurements': measurements, 'source_sha256': source_hashes,
            'physical_completion_confirmed': False,
            'highway_or_public_access_legally_confirmed': False,
            'worker_role_independently_confirmed': False,
            'mental_state_conclusion': None, 'legal_recklessness_conclusion': None}


def finalize(attempt, output):
    root, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (root / 'result.json').exists():
        raise ValueError('Retain prior saved analysis; choose fresh output')
    report = analyze(root)
    config = json.loads((root / 'config.json').read_text())
    construction = json.loads(require_file(root, 'construction.json').read_text())
    if construction.get('case_id') != report['case_id']:
        raise ValueError('Selected case and construction identity differ')
    videos = [name + '.mkv' for name in (
        'overview', 'approach', 'reference_corner', 'driver_reference')]
    for name in ('trace.jsonl', 'capture/evidence.jsonl', *videos):
        require_file(root, name)
    samples = rows(root / 'native-person-interaction.jsonl')
    mapped = rows(root / 'video_frames.jsonl')
    channel_dir = root / 'channels'
    channel_dir.mkdir(exist_ok=False)
    evidence = []
    context = json.loads((root / 'original-context-packet.json').read_text())
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        if name == 'drv.time_to_conflict':
            values = [report['selected_branch_measurement']['minimum_projected_ttc_s']] * len(samples)
        elif name == 'drv.hard_deceleration':
            values = [sample['ego_accel_longitudinal_mps2'] for sample in samples]
        elif name == 'kin.speed':
            values = [(sample['ego_vx_mps']**2 + sample['ego_vy_mps']**2)**.5 for sample in samples]
        elif name == 'kin.accel_longitudinal':
            values = [sample['ego_accel_longitudinal_mps2'] for sample in samples]
        elif name == 'kin.yaw_rate':
            values = [sample['ego_yaw_rate_radps'] for sample in samples]
        elif name == 'rel.surface_gap':
            values = [((sample['person_x_m']-sample['ego_x_m'])**2 +
                       (sample['person_y_m']-sample['ego_y_m'])**2)**.5 -
                      sample['ego_radius_m'] - sample['person_radius_m'] for sample in samples]
        elif name == 'rel.contact':
            values = [sample['collision_sensor_contact'] for sample in samples]
        elif name == 'st.highway':
            values = [{'access_kind_claimed_by_source': context['access_kind'],
                       'source': 'original-context-packet.json',
                       'legal_status_independently_reviewed': False}] * len(samples)
        elif name == 'ru.pedestrian':
            values = [{'actor_id': sample['person_actor_id'],
                       'blueprint_id': sample['person_blueprint_id'],
                       'x_m': sample['person_x_m'], 'y_m': sample['person_y_m'],
                       'worker_role_independently_reviewed': False} for sample in samples]
        else:
            raise ValueError('Unrecognized mandatory person-interaction channel: ' + name)
        with (channel_dir / (name + '.jsonl')).open('x') as stream:
            for frame, value in zip(mapped, values):
                stream.write(json.dumps({'time_s': frame['time_s'], 'value': value},
                                        allow_nan=False) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': 'channels/' + name + '.jsonl'})
    result = {'case_id': report['case_id'],
              'measured_values': report['selected_branch_measurement'],
              'target_checks': [{
                  'target': 'complete original person encounter on sourced paved route',
                  'requested': True,
                  'measured': len(samples) == 600,
                  'method': 'source-joined actor telemetry, map, context and four-camera frame map',
                  'tolerance': 0, 'matched': len(samples) == 600,
                  'physical_cause_confirmed': False,
                  'cause_evidence': ['native-person-interaction.jsonl',
                                     'original-context-packet.json',
                                     'native-road-readback.json', 'video_frames.jsonl']}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': '600-frame saved diagnostic; independent physical and legal review pending',
              'physical_failure_flags': [
                  'Actual worker role and location, highway or public access, sight lines and surface require review',
                  'Willful or wanton mental state cannot be inferred from telemetry'],
              'trace_reference': 'trace.jsonl',
              'video_references': videos,
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': evidence,
              'realized_observables': {},
              'provenance_kind': ('synthetic_local_diagnostic' if context.get('synthetic_diagnostic')
                                  else 'original_native'),
              'accepted': False}
    from worker_exchange.native_output import write_result
    write_result(root, result)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = finalize(args.attempt, args.output)
    print(json.dumps({'case_id': result['case_id'], 'source_complete': True,
                      'physical_completion_confirmed': False}))


if __name__ == '__main__':
    main()
