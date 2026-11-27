"""Saved-only source-shaped fixture, including missing and stale-source rejection."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from finalize import finalize
from prove_rail_scene import SIGHT_BLOCKERS, make_rows

if (not os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT') or
        Path('.runtime-work').resolve() not in
        Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve().parents):
    raise RuntimeError('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work before runtime imports')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(rows):
    return ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows)


def reject(fn, phrase):
    try:
        fn()
    except ValueError as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError('expected rejection: ' + phrase)


root = Path('.runtime-work').resolve()
with tempfile.TemporaryDirectory(dir=root, prefix='c202465-lvmc-finalize-') as temporary:
    attempt = Path(temporary) / 'attempt'
    attempt.mkdir()
    (attempt/'road.xodr').write_text('<OpenDRIVE>synthetic diagnostic grade crossing</OpenDRIVE>\n')
    review_dir = attempt/'original-source-review'
    review_dir.mkdir()
    source_records = {
        'railway': {'crossing_kind': 'at_grade', 'railway_type': 'electric',
                    'railway_identity': 'synthetic fixture only',
                    'crossing_xyz_m': [0, 0, 0], 'rail_unit_direction_xy': [0, 1],
                    'surveyed_left_extent_m': 122, 'surveyed_right_extent_m': 122,
                    'rail_vehicle_lateral_tolerance_m': 1.5,
                    'rail_vehicle_actor_ids': {'left': 2, 'right': 3}},
        'approach': {'driver_role': 'motor_vehicle_driver',
                     'municipal_jurisdiction_verified': True,
                     'approach_maneuver': 'cross_railway',
                     'approach_direction_xy': [1, 0],
                     'surveyed_approach_length_m': 50,
                     'ego_spawn_xyz_m': [-50, 0, 2], 'ego_spawn_yaw_deg': 0},
        'flagman': {'source_method': 'original_actor_and_duty_readback',
                    'on_duty_at_capture_start': False},
        'signal': {'source_method': 'original_device_visibility_and_state_readback',
                   'installed': False, 'clearly_visible': False,
                   'indicates_immediate_approach': False},
    }
    for role, values in source_records.items():
        source = review_dir/(role+'.source.txt')
        source.write_text('synthetic schema-only '+role+'\n')
        record = dict(values, role=role, road_sha256=sha(attempt/'road.xodr'),
                      source_sha256=sha(source), review_status='schema_only',
                      provenance_kind='synthetic_fixture', reviewer_id='cpu-schema-only')
        (review_dir/(role+'.json')).write_text(json.dumps(record)+'\n')
    (attempt/'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'synthetic_fixture'})+'\n')
    for camera in ('overview','approach','reference_corner','driver_reference'):
        (attempt/(camera+'.mkv')).write_bytes(('synthetic '+camera).encode())
    plan = json.loads((Path(__file__).resolve().parents[1]/'case-plan.json').read_text())
    case_id = plan['cases'][0]['case_id']
    config = {'case_id': case_id, 'speed_mode': 'slower_traversal',
              'recording_description': {'channels': []}}
    (attempt/'config.json').write_text(json.dumps(config)+'\n')
    scene = make_rows('slower_traversal', SIGHT_BLOCKERS['left_sight_obscured'])
    bodies, rays, exceptions, maps, trace = [], [], [], [], []
    for i, source in enumerate(scene):
        frame = 1000+i
        x = -50 + .3*i
        body = {'frame': frame, 'actor_id': 1, 'actor_type_id': 'vehicle.fixture',
                'body_vertices_m': [[x+dx, dy, z] for dx in (-2, 2)
                                    for dy in (-1, 1) for z in (0, 1)],
                'velocity_mps': [6, 0, 0]}
        direction = lambda side, aid: {
            'actor_id': aid, 'actor_position_m': [0, source['rail_vehicle_positions_m'][side][1], 0],
            'rail_rays': [{'clear': True}], 'body_rays': [{'clear': True}],
            'clear_distance_m': source['rail_'+side+'_clear_distance_m'],
            'rail_vehicle_visible_proxy': source[side+'_traffic_visible']}
        ray = {'frame': frame, 'ego_actor_id': 1,
               'review_source_sha256': sha(review_dir/'railway.source.txt'),
               'observer_m': [x, 0, 1.4],
               'crossing': {'clear': source['crossing_visible'], 'method': 'world.cast_ray'},
               'directions': {'left': direction('left',2), 'right': direction('right',3)}}
        exception = {'frame': frame, 'video_frame': i,
                     'flagman': {'frame': frame, 'source_ref': 'fixture:flagman', 'on_duty': False},
                     'signal': {'frame': frame, 'source_ref': 'fixture:signal',
                                'installed': False, 'visible': False, 'indicates_approach': False}}
        mapping = {'video_frame': i, 'native_frame': frame, 'carla_frame': frame,
                   'time_s': i/20, 'camera_native_frames': {
                       name: frame for name in ('overview','approach','reference_corner','driver_reference')}}
        bodies.append(body);rays.append(ray);exceptions.append(exception);maps.append(mapping)
        trace.append({'frame': frame, 'time_s': i/20,
                      'position': {'x': x, 'y': 0, 'z': 0},
                      'speed_mps': 6, 'heading_deg': 0})
    for name, rows in (('rail-body.jsonl',bodies),('rail-rays.jsonl',rays),
                       ('reviewed-exceptions.jsonl',exceptions),
                       ('video_frames.jsonl',maps),('trace.jsonl',trace)):
        (attempt/name).write_text(lines(rows))
    review = {'review_status': 'schema_only', 'provenance_kind': 'synthetic_fixture',
              'reviewer_id': 'cpu-schema-only',
              'frame_map_sha256': sha(attempt/'video_frames.jsonl'),
              'overview_video_sha256': sha(attempt/'overview.mkv'),
              'exception_rows_sha256': sha(attempt/'reviewed-exceptions.jsonl')}
    (attempt/'reviewed-exceptions-review.json').write_text(json.dumps(review)+'\n')
    report = finalize(attempt, attempt/'analysis-report.json')
    assert report['measurements']['rail_sight_and_speed']['value']['last_100_feet_missing_view_frames'] > 0
    assert report['measurements']['selected_witness']['value']['crossing_traversal_frames'] > 0
    assert report['physical_acceptance_claimed'] is False
    (attempt/'result.json').unlink()
    (attempt/'analysis-report.json').unlink()
    shutil.rmtree(attempt/'channels')
    (attempt/'rail-rays.jsonl').unlink()
    reject(lambda: finalize(attempt, attempt/'analysis-report.json'),
           'Missing required source: rail-rays.jsonl')
print('PASS: saved 600-frame source joins, Native result and missing rail-ray rejection')
