"""Publish source-joined factual Native channels without a legal verdict."""

import json
from pathlib import Path

from lamp_direction import require
from saved_audit import audit_saved


VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
          'driver_reference.mkv')


def rows(path):
    path = Path(path)
    require(path.is_file(), 'Missing required source: ' + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def publish(attempt, report):
    root = Path(attempt).resolve()
    config = json.loads((root / 'config.json').read_text())
    case_id = config['selected_case_id']
    key = case_id.rsplit('__', 1)[-1]
    audit_saved(root, key)
    construction = json.loads((root / 'construction.json').read_text())
    description = construction['recording_description']
    require(config['recording_description'] == description, 'Native recording plan changed')
    trace = rows(root / 'trace.jsonl')
    frame_map = rows(root / 'video_frames.jsonl')
    lamp_ticks = rows(root / 'original-lamp-ticks.jsonl')
    require(len(trace) == len(frame_map) == len(lamp_ticks) == 900,
            'full original Native/trace/camera frame join missing')
    for i, (point, mapped, tick) in enumerate(zip(trace, frame_map, lamp_ticks)):
        require(point['frame'] == mapped['carla_frame'] == tick['original_frame'] and
                mapped['video_frame'] == i and
                abs(float(point['time_s']) - float(mapped['time_s'])) < 1e-6 and
                abs(float(point['time_s']) - float(tick['time_s'])) < 1e-6,
                'original Native/trace/camera frame or time join changed')
    for video in VIDEOS:
        require((root / video).is_file(), 'Missing required source: ' + video)
    packet = json.loads((root / 'lamp-context-packet.json').read_text())
    scene = packet['scene']
    camera = json.loads((root / 'camera-source-manifest.json').read_text())['cameras']
    evidence = []
    channels_dir = root / 'channels'
    require(not channels_dir.exists(), 'Native channels already published')
    channels_dir.mkdir()
    for channel in description['channels']:
        name = channel['name']
        path = channels_dir / (name + '.jsonl')
        with path.open('x') as stream:
            for i, (point, tick) in enumerate(zip(trace, lamp_ticks)):
                values = {
                    'original_frame': tick['original_frame'],
                    'native_time_s': tick['time_s'],
                    'map_sha256': scene['map_sha256'],
                    'vehicle_id': tick['vehicle_id'],
                    'ego_position': point['position'],
                    'ego_heading': point['heading_deg'],
                    'ego_speed': point['speed_mps'],
                    'ego_lamp_bits': tick['lamp_states'],
                    'required_lamp_states': tick['lamp_states'],
                    'device_actor_id': scene.get('device_actor_id', 'source-gated-device'),
                    'device_message': scene['device_message'],
                    'device_authority': scene['device_authority'],
                    'device_route': scene['route_xy'],
                    'device_timing': scene['device_timing'],
                    'jurisdiction': scene['nevada_jurisdiction'],
                    'highway': scene['highway'],
                    'parking_status': scene['parked'],
                    'clock': scene['clock_time_s'],
                    'sunset_sunrise': [scene['sunset_time_s'], scene['sunrise_time_s']],
                    'visibility': scene['visibility_ahead_m'],
                    'camera_frames': {view: camera[view][i] for view in camera},
                }
                require(name in values, 'Native recording channel missing: ' + name)
                stream.write(json.dumps({'time_s': tick['time_s'],
                                         'value': values[name]}, separators=(',', ':')) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': str(path.relative_to(root))})
    contexts = {
        'reviewed_site_packet': {'reviewed_site_packet': packet},
        'original_map_identity': {'original_map_identity': scene['map_sha256']},
    }
    for context in description['context_inputs']:
        name = context['name']
        require(name in contexts, 'Native context input missing: ' + name)
        path = channels_dir / (name + '.json')
        path.write_text(json.dumps(contexts[name], separators=(',', ':')) + '\n')
        evidence.append({'name': name, 'unit': context['unit'],
                         'reference': str(path.relative_to(root))})
    counts = report['measurements']['required_lamp_states']['value']['on_frame_counts']
    target = {'target': 'requested_class_lamp_state',
              'requested': bool(config['case']['lamps_on']),
              'measured': counts,
              'method': 'source-joined original per-lamp Native readback',
              'tolerance': 'all 900 original frames for each required lamp',
              'matched': all(count == (900 if config['case']['lamps_on'] else 0)
                             for count in counts.values()),
              'physical_cause_confirmed': False,
              'cause_evidence': 'Original emitted light, device face and authority require independent local review'}
    return {'case_id': case_id,
            'measured_values': {'frame_count': 900, 'lamp_on_frame_counts': counts},
            'target_checks': [target], 'setup_confirmed': False,
            'behavior_attempted': True, 'maneuver_completed': False,
            'termination_reason': '45-second source-gated acquisition completed; physical review pending',
            'physical_failure_flags': {'device_face_or_emission_unverified': True},
            'trace_reference': 'trace.jsonl', 'video_references': list(VIDEOS),
            'video_frame_map_reference': 'video_frames.jsonl',
            'recording_description': description, 'recording_evidence': evidence,
            'realized_observables': {},
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}
