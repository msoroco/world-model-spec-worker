"""Publish source-joined factual Native channels for parked headlamps."""
from __future__ import annotations

import json
from pathlib import Path

from analysis import source
from parking_completion import assess

CHANNELS = ('original_actor_state', 'original_four_view_frame_map',
            'headlamp_emission_and_aim_review')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
          'driver_reference.mkv')


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def publish(attempt: str | Path, report: dict) -> dict:
    root = Path(attempt)
    config = json.loads(source(root, 'config.json').read_text(encoding='utf-8'))
    description = json.loads(source(root, 'construction.json').read_text(encoding='utf-8'))[
        'recording_description']
    declared = {item['name']: item for item in description['channels']}
    if set(declared) != set(CHANNELS):
        raise ValueError('selected recording channels changed')
    states = _rows(source(root, 'actor-state.jsonl'))
    camera = _rows(source(root, 'camera-frame-map.jsonl'))
    trace = _rows(source(root, 'trace.jsonl'))
    video = _rows(source(root, 'video_frames.jsonl'))
    if not states or len(states) != len(camera) or len(states) != len(trace) or len(states) != len(video):
        raise ValueError('original Native/Core source frame count differs')
    for index, (state, mapped, point, frame) in enumerate(zip(states, camera, trace, video)):
        native = state['frame']
        if (mapped['frame'] != native or point['frame'] != native or
                frame['carla_frame'] != native or frame['video_frame'] != index or
                abs(float(state['time_s']) - float(point['time_s'])) > 1e-4 or
                abs(float(frame['time_s']) - float(point['time_s'])) > 1e-4):
            raise ValueError('original Native/Core source frame/time join differs')
    receipt = json.loads(source(root, 'native-source-receipt.json').read_text(encoding='utf-8'))
    if set(receipt.get('original_camera_videos', {})) != {
            'overview', 'approach', 'reference_corner', 'driver_reference'}:
        raise ValueError('four original Native videos required')
    for name in VIDEOS:
        source(root, name)
    evidence = []
    for name, originals in [('original_actor_state', states),
                            ('original_four_view_frame_map', camera)]:
        path = root / (name + '.jsonl')
        if path.exists():
            raise ValueError('selected channel already published: ' + name)
        path.write_text(''.join(json.dumps({'time_s': states[i]['time_s'], 'value': value}) + '\n'
                                for i, value in enumerate(originals)), encoding='utf-8')
        evidence.append({'name': name, 'unit': declared[name]['unit'], 'reference': path.name})
    review = root / 'headlamp_emission_and_aim_review.jsonl'
    if review.exists():
        raise ValueError('selected channel already published: ' + review.name)
    review.write_text(''.join(json.dumps({
        'time_s': state['time_s'],
        'value': {'light_state_bits': state['light_state_bits'],
                  'four_original_camera_frame': state['frame'],
                  'emitted_intensity_confirmed': False, 'beam_aim_confirmed': False}}) + '\n'
        for state in states), encoding='utf-8')
    evidence.append({'name': 'headlamp_emission_and_aim_review',
                     'unit': declared['headlamp_emission_and_aim_review']['unit'],
                     'reference': review.name})
    site_context = root / 'reviewed-site-geometry.json'
    if site_context.exists():
        raise ValueError('selected site context already published')
    site_context.write_text(json.dumps({'reviewed_site_geometry': json.loads(
        source(root, 'site-packet.json').read_text(encoding='utf-8'))}) + '\n',
        encoding='utf-8')
    evidence.append({'name': 'reviewed_site_geometry', 'unit': 'structured record',
                     'reference': site_context.name})
    mode = config['requested_headlamp_mode']
    observed = report['measurements']['parked_vehicle_observation']['value']
    target = {'target': 'parked_vehicle_and_requested_headlamp_mode',
              'requested': mode,
              'measured': {'parked_samples': observed['parking_brake_and_footprint_sample_count'],
                           'low_beam_readback_count': sum(bool(s['light_state_bits'] & receipt['light_masks']['low_beam']) for s in states),
                           'high_beam_readback_count': sum(bool(s['light_state_bits'] & receipt['light_masks']['high_beam']) for s in states)},
              'method': 'source-joined original body and light-state readback',
              'tolerance': 'all planned samples; emission and aim independently reviewed',
              'matched': False, 'physical_cause_confirmed': False,
              'cause_evidence': 'Original emitted light and beam aim require local physical review'}
    physical = assess(root, planned_frames=len(states),
                      diagnostic_fixture=bool(json.loads(source(root, 'site-packet.json').read_text()).get('diagnostic_fixture')))
    return {'case_id': config['selected_case_id'],
            'measured_values': {'parked_sample_count': observed['parking_brake_and_footprint_sample_count'],
                                'frame_count': len(states)},
            'target_checks': [target], 'setup_confirmed': False,
            'behavior_attempted': True, 'maneuver_completed': physical['maneuver_completed'],
            'termination_reason': 'original planned frames exhausted',
            'physical_failure_flags': {'emitted_light_and_aim_unverified': True},
            'trace_reference': 'trace.jsonl', 'video_references': list(VIDEOS),
            'video_frame_map_reference': 'video_frames.jsonl',
            'recording_description': description, 'recording_evidence': evidence,
            'realized_observables': {},
            'physical_checks': physical['physical_checks'],
            'provenance_kind': physical['provenance_kind'],
            'diagnostic_fixture': physical['diagnostic_fixture']}
