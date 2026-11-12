"""Retain original Native truck bodies, widths and frame identities at capture."""
import json
import math


def _finite_vector(values, label):
    result = [float(value) for value in values]
    if any(not math.isfinite(value) for value in result):
        raise ValueError('Nonfinite Native ' + label)
    return result


def _actor(actor, waypoint):
    bounds = actor.bounding_box
    vertices = bounds.get_world_vertices(actor.get_transform())
    if len(vertices) < 4:
        raise ValueError('Missing original complete truck body')
    body = [_finite_vector((v.x, v.y), 'truck body') for v in vertices]
    width = 2.0 * float(bounds.extent.y)
    if not math.isfinite(width) or width <= 0:
        raise ValueError('Missing realized truck width')
    return {'actor_id': actor.id, 'blueprint_id': actor.type_id,
            'road_id': waypoint.road_id, 'lane_id': waypoint.lane_id,
            'overall_width_m': width, 'overall_width_source': 'Native bounding_box; single vehicle only',
            'is_truck_or_combination': actor.type_id in ('vehicle.carlamotors.european_hgv',
                                                         'vehicle.carlamotors.carlacola'),
            'body_vertices_xy_m': body,
            'velocity_mps': _finite_vector((actor.get_velocity().x, actor.get_velocity().y,
                                           actor.get_velocity().z), 'truck velocity')}


def record_sample(frame_map, history_stream, snapshot, ego, lead, ego_waypoint, lead_waypoint):
    if ego_waypoint is None or lead_waypoint is None:
        raise ValueError('Missing original truck lane readback')
    frame, time_s = snapshot.frame, snapshot.timestamp.elapsed_seconds
    row = {'frame': frame, 'time_s': time_s, 'ego': _actor(ego, ego_waypoint),
           'lead': _actor(lead, lead_waypoint)}
    mapping = frame_map.append(frame, time_s)
    history_stream.write(json.dumps(row, allow_nan=False) + '\n')
    return {'video_frame': mapping['video_frame'], 'frame': frame}
