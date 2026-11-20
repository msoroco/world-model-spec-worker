"""Retain original traffic-light state for a direction-exception probe.

An actor state is an observation, not proof that its direction applied to ego
or that a stop in the fire lane was necessary or lawful.
"""
from math import hypot, isfinite

from fire_lane_survey import require


def inspect_device(world, carla, survey, fire_lane_plan):
    requested = survey.get('traffic_control_device')
    require(isinstance(requested, dict), 'Traffic-control device survey missing')
    actor_id = requested.get('actor_id')
    xy = requested.get('position_xy_m')
    if requested.get('selection_mode') == 'unique_same_road_near_stop':
        require(actor_id is None and xy is None,
                'Device discovery cannot override a surveyed actor')
        radius = requested.get('search_radius_m')
        require(type(radius) in (int, float) and isfinite(radius) and
                0 < radius <= 50, 'Device search radius invalid')
        center = fire_lane_plan['cases']['reference']['stop_center_xy_m']
        require(isinstance(center, list) and len(center) == 2 and
                all(type(v) in (int, float) and isfinite(v) for v in center),
                'Surveyed reference stop center invalid')
        actors = world.get_actors()
        matches = []
        for candidate in actors.filter('traffic.traffic_light'):
            if candidate.type_id != 'traffic.traffic_light':
                continue
            position = candidate.get_transform().location
            if hypot(position.x-center[0], position.y-center[1]) > radius:
                continue
            lane = world.get_map().get_waypoint(
                position, project_to_road=True, lane_type=carla.LaneType.Driving)
            if lane is not None and lane.road_id == fire_lane_plan['fixed_context']['road_id']:
                matches.append(candidate)
        require(len(matches) == 1,
                'Device discovery needs exactly one nearby same-road original light; found '+str(len(matches)))
        actor = matches[0]
        location = actor.get_transform().location
        actor_id, xy = actor.id, [location.x, location.y]
    else:
        require(type(actor_id) is int and actor_id > 0 and
                isinstance(xy, list) and len(xy) == 2 and
                all(type(v) in (int, float) and isfinite(v) for v in xy),
                'Traffic-control device identity or position invalid')
        actor = world.get_actors().find(actor_id)
    require(actor is not None and getattr(actor, 'type_id', None) ==
            'traffic.traffic_light', 'Original traffic light actor missing')
    location = actor.get_transform().location
    require(hypot(location.x-xy[0], location.y-xy[1]) <= 0.5,
            'Original traffic light moved from surveyed location')
    waypoint = world.get_map().get_waypoint(
        location, project_to_road=True, lane_type=carla.LaneType.Driving)
    require(waypoint is not None and waypoint.road_id ==
            fire_lane_plan['fixed_context']['road_id'],
            'Traffic light not on surveyed road')
    return {'actor_id':actor_id, 'type_id':actor.type_id,
            'position_xy_m':[location.x, location.y],
            'road_id':waypoint.road_id, 'lane_id':waypoint.lane_id,
            'source_kind':'original_carla_actor_and_map_readback',
            'selection_mode':requested.get('selection_mode', 'surveyed_actor_id'),
            'direction_applicability_verified':False,
            'statutory_necessity_verified':False}


def sample_device(actor, readback, frame):
    require(type(frame) is int and frame >= 0, 'Original frame invalid')
    require(actor.id == readback['actor_id'] and
            actor.type_id == 'traffic.traffic_light',
            'Traffic-control actor identity changed')
    transform = actor.get_transform()
    location = transform.location
    xy = readback['position_xy_m']
    require(hypot(location.x-xy[0],location.y-xy[1]) <= 0.5,
            'Traffic-control actor moved during capture')
    raw_state = actor.get_state()
    state = getattr(raw_state, 'name', None) or str(raw_state).rsplit('.',1)[-1]
    require(state in ('Red','Yellow','Green','Off','Unknown'),
            'Unrecognized original traffic-light state')
    return {'frame':frame, 'device_actor_id':actor.id,
            'device_type_id':actor.type_id, 'device_state':state,
            'device_pose_xyz_m':[location.x,location.y,location.z],
            'direction_applicability_verified':False,
            'statutory_necessity_verified':False,
            'source_kind':'original_carla_actor_readback'}


def check_saved_device_rows(rows, frame_rows, readback, *, source_kind='original_carla_actor_readback'):
    """Check source identity and frame joins without issuing a legal verdict."""
    require(len(rows) == len(frame_rows) and len(rows) >= 600,
            'Device source must cover the full thirty-second capture')
    expected = [row['frame'] for row in frame_rows]
    require(all(type(frame) is int for frame in expected) and
            len(set(expected)) == len(expected) and
            expected == sorted(expected), 'Video frame map invalid')
    for index, (row, frame) in enumerate(zip(rows, expected)):
        require(row.get('frame') == frame and
                row.get('video_frame') == index and
                row.get('device_actor_id') == readback['actor_id'] and
                row.get('device_type_id') == readback['type_id'] and
                row.get('source_kind') == source_kind and
                row.get('device_state') in
                ('Red','Yellow','Green','Off','Unknown') and
                row.get('direction_applicability_verified') is False and
                row.get('statutory_necessity_verified') is False,
                'Saved traffic-control source differs or overclaims')
    return {'source_frames':len(rows), 'device_actor_id':readback['actor_id'],
            'state_counts':{state:sum(row['device_state'] == state for row in rows)
                            for state in ('Red','Yellow','Green','Off','Unknown')},
            'direction_applicability_verified':False,
            'statutory_necessity_verified':False}
