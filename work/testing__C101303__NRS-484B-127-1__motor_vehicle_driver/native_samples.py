"""Original Native per-frame following samples; CARLA is supplied by the caller."""
import math


BODY_SOURCE = 'Native CARLA actor transform and bounding box'


def _body(actor):
    points = actor.bounding_box.get_world_vertices(actor.get_transform())
    result = [[p.x, p.y, p.z] for p in points]
    if len(result) < 4 or any(not all(math.isfinite(v) for v in point) for point in result):
        raise ValueError('original actor body vertices missing')
    return result


def _speed(actor):
    velocity = actor.get_velocity()
    result = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
    if not math.isfinite(result):
        raise ValueError('original actor velocity invalid')
    return result


def sample(world, native_map, ego, leader, *, frame, relative_time_s,
           following_lane_id, weather=None):
    """Record both bodies, speeds, traffic, weather, friction and lane change."""
    if ego.id == leader.id:
        raise ValueError('separate moving leader actor required')
    ego_waypoint = native_map.get_waypoint(ego.get_transform().location)
    lead_waypoint = native_map.get_waypoint(leader.get_transform().location)
    if ego_waypoint is None or lead_waypoint is None:
        raise ValueError('original actor lane waypoint missing')
    if not isinstance(frame, int) or frame < 0 or not math.isfinite(relative_time_s):
        raise ValueError('original frame/time missing')
    if weather is None:
        weather = world.get_weather()
    fog = float(weather.fog_density)
    rain = float(weather.precipitation)
    if not all(math.isfinite(v) and 0 <= v <= 100 for v in (fog, rain)):
        raise ValueError('original Native weather outside percent domain')
    wheels = ego.get_physics_control().wheels
    if not wheels:
        raise ValueError('original wheel friction unavailable')
    friction = [float(w.tire_friction) for w in wheels]
    if not all(math.isfinite(v) and v > 0 for v in friction):
        raise ValueError('original wheel friction invalid')
    traffic = [a for a in world.get_actors().filter('vehicle.*')
               if a.id not in (ego.id, leader.id) and a.is_alive]
    ego_speed, leader_speed = _speed(ego), _speed(leader)
    if relative_time_s <= 20 and (ego_waypoint.lane_id != following_lane_id or
                                  lead_waypoint.lane_id != following_lane_id):
        raise ValueError('following participants changed lane before steady window ended')
    return {'frame': frame, 'time_s': relative_time_s,
            'ego': {'actor_id': ego.id, 'source_ref': BODY_SOURCE,
                    'body_vertices_m': _body(ego), 'speed_mps': ego_speed},
            'leader': {'actor_id': leader.id, 'source_ref': BODY_SOURCE,
                       'body_vertices_m': _body(leader), 'speed_mps': leader_speed},
            'surrounding_vehicle_count': 1+len(traffic),
            'traffic_actor_ids': [a.id for a in traffic],
            'traffic_source': 'Native CARLA actor inventory',
            'highway_condition': {
                'source_ref': 'original weather and road context',
                'native_fog_density': fog,
                'native_precipitation_strength': rain,
                'observed_tire_friction': sum(friction)/len(friction),
                'wheel_friction_samples': friction},
            'lane_change': {'source_ref': 'Native lane waypoint and route',
                            'ego_road_id': ego_waypoint.road_id,
                            'ego_lane_id': ego_waypoint.lane_id,
                            'leader_road_id': lead_waypoint.road_id,
                            'leader_lane_id': lead_waypoint.lane_id,
                            'started': ego_waypoint.lane_id != following_lane_id}}
