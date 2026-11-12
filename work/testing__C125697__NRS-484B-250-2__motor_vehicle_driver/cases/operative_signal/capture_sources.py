"""Original-frame Native crossing and Off-state capture for C125697.

The caller must join all four camera callbacks to this tick before recording.
The supplied FrameMap owns the adjacent video_frames.jsonl identity.
"""
import json
import math


CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def _number(value, label):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('Nonfinite Native ' + label)
    return value


def _actor(actor, world_map, plan, role):
    pose = actor.get_transform()
    vertices = actor.bounding_box.get_world_vertices(pose)
    if len(vertices) < 4:
        raise ValueError('Complete Native body vertices required')
    waypoint = world_map.get_waypoint(actor.get_location(), project_to_road=False)
    if waypoint is None:
        raise ValueError('No Native driving waypoint at original frame')
    velocity = actor.get_velocity()
    return {'actor_id': actor.id,
            'position_xy_m': [_number(pose.location.x, 'x'),
                              _number(pose.location.y, 'y')],
            'body_vertices_xy_m': [[_number(v.x, 'body x'), _number(v.y, 'body y')]
                                   for v in vertices],
            'heading_deg': _number(pose.rotation.yaw, 'yaw'),
            'velocity_xyz_mps': [_number(velocity.x, 'velocity x'),
                                 _number(velocity.y, 'velocity y'),
                                 _number(velocity.z, 'velocity z')],
            'intersection_id': plan['native_junction_id'],
            'road_id': plan['approaches'][role]['road_id'],
            'native_road_id': waypoint.road_id,
            'native_lane_id': waypoint.lane_id,
            'native_junction_id': waypoint.get_junction().id if waypoint.is_junction else None,
            'body_source': 'actor.bounding_box.get_world_vertices'}


def record_crossing_sample(frame_map, stream, snapshot, world_map, ego, other,
                           lights, traffic_light_state, camera_frames, plan):
    if plan.get('physical_acceptance_claimed') is not False or not plan.get('native_junction_id'):
        raise ValueError('Checked Native pair plan required')
    if set(camera_frames) != set(CAMERAS) or any(camera_frames[name] != snapshot.frame for name in CAMERAS):
        raise ValueError('Four source-camera frames must join original Native tick')
    if len(lights) < 2 or len({light.id for light in lights}) != len(lights):
        raise ValueError('Distinct inventoried entrance lights required')
    states = [light.get_state() for light in lights]
    expected = [traffic_light_state.Red, traffic_light_state.Green] + [traffic_light_state.Red] * (len(lights) - 2)
    if states != expected:
        raise ValueError('Operative entrance lights must read back Red/Green')
    time_s = _number(snapshot.timestamp.elapsed_seconds, 'time')
    ego_row, other_row = (_actor(ego, world_map, plan, 'ego'),
                          _actor(other, world_map, plan, 'other'))
    if ego_row['actor_id'] == other_row['actor_id']:
        raise ValueError('Distinct Native actor identities required')
    mapped = frame_map.append(snapshot.frame, time_s)
    row = {'frame': snapshot.frame, 'time_s': time_s,
           'governing_signal_state': 'Red',
           'entrance_signal_states': [{'actor_id': light.id, 'state': 'Green' if i == 1 else 'Red'}
                                      for i, light in enumerate(lights)],
           'ego': ego_row, 'other': other_row,
           'ego_vertices_m': ego_row['body_vertices_xy_m']}
    stream.write(json.dumps(row, allow_nan=False) + '\n')
    return mapped, row


def junction_context(site, plan):
    required = ('native_map_name', 'same_statutory_crossing', 'crossing_polygon_source',
                'all_entrances_source', 'signal_governance_source',
                'signal_head_video_source', 'median_spacing_source')
    if any(site.get(key) in (None, '') for key in required):
        raise ValueError('Reviewed median opening and signal provenance required')
    if site['same_statutory_crossing'] is not True:
        raise ValueError('One median-opening statutory crossing required')
    approaches = plan['approaches']
    yaw = math.radians(approaches['ego']['heading_deg'])
    other_yaw = math.radians(approaches['other']['heading_deg'])
    return {'native_map_id': plan['native_map_name'],
            'intersection_id': plan['native_junction_id'],
            'ego_highway_id': plan['ego_highway_id'],
            'other_highway_id': plan['other_highway_id'],
            'ego_road_id': approaches['ego']['road_id'],
            'other_road_id': approaches['other']['road_id'],
            'crossing_geometry_source': plan['crossing_polygon_source'],
            'all_entrances_source': plan['all_entrances_source'],
            'signal_governance_source': site['signal_governance_source'],
            'signal_head_video_source': site['signal_head_video_source'],
            'median_spacing_source': plan['median_spacing_source'],
            'same_statutory_crossing': True,
            'intersection_polygon_xy_m': plan['crossing_polygon_xy_m'],
            'ego_approach_forward_xy': [math.cos(yaw), math.sin(yaw)],
            'other_approach_forward_xy': [math.cos(other_yaw), math.sin(other_yaw)],
            'opposite_approach_with_left_turn': False,
            'official_device_operating': True,
            'physical_acceptance_claimed': False,
            'legal_priority_judgment': 'unresolved'}
