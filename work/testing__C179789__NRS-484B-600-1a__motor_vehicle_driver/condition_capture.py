"""Capture one original Native speed/conditions observation at a frame identity.

Surface state is a byte-bound source declaration pending physical review; Native
weather readback alone never establishes an icy or wet roadway.
"""
import hashlib
import math
from pathlib import Path
from condition_construction import sample_lane_and_sight


def validate_surface_packet(packet, root):
    if not isinstance(packet, dict) or packet.get('review_status') != 'reviewed_native_surface':
        raise ValueError('Original roadway-surface review packet required')
    if not isinstance(packet.get('native_map_id'), str) or not packet['native_map_id'].strip() or type(packet.get('road_id')) is not int:
        raise ValueError('Original surface map/road identity required')
    state = packet.get('surface')
    if state not in ('dry', 'wet', 'ice_or_snow'):
        raise ValueError('Exact sourced roadway-surface state required')
    for key in ('reviewer', 'review_basis'):
        value = packet.get(key)
        if not isinstance(value, str) or not value.strip() or any(
                word in value.lower() for word in ('synthetic', 'diagnostic')):
            raise ValueError('Original roadway-surface review declaration required')
    source = packet.get('source')
    if not isinstance(source, dict) or not isinstance(source.get('path'), str):
        raise ValueError('Original surface document binding required')
    relative = Path(source['path'])
    root = Path(root).resolve()
    if relative.is_absolute() or '..' in relative.parts or str(relative) in ('', '.'):
        raise ValueError('Unsafe surface document path')
    path = root / relative
    if not path.is_file() or not path.resolve().is_relative_to(root):
        raise ValueError('Original surface document missing or escaping')
    text = path.read_text(encoding='utf-8')
    if not text.strip() or any(word in text.lower() for word in ('synthetic', 'diagnostic')):
        raise ValueError('Original surface document required')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if source.get('sha256') != digest:
        raise ValueError('Original surface document hash changed')
    return {'surface': state, 'source': {'path': str(relative), 'sha256': digest},
            'physical_surface_verified': False}


def sample_frame(world, ego, lead, snapshot, surface_review, eye,
                 forward, *, map_source, ray_source):
    if not isinstance(surface_review, dict) or surface_review.get('physical_surface_verified') is not False:
        raise ValueError('Validated surface source declaration required')
    location = ego.get_location()
    waypoint = world.get_map().get_waypoint(location, project_to_road=False)
    if waypoint is None:
        raise ValueError('Native ego roadway waypoint missing')
    probe = sample_lane_and_sight(world, waypoint, eye, forward, 120,
                                  map_source=map_source, ray_source=ray_source)
    velocity = ego.get_velocity()
    other_velocity = lead.get_velocity()
    ego_vector = [float(getattr(velocity, key)) for key in ('x', 'y', 'z')]
    lead_vector = [float(getattr(other_velocity, key)) for key in ('x', 'y', 'z')]
    if not all(math.isfinite(value) for value in ego_vector + lead_vector):
        raise ValueError('Original Native vehicle velocity nonfinite')
    tangent = [float(forward[0]), float(forward[1])]
    norm = math.hypot(*tangent)
    if norm <= .1 or not math.isfinite(norm):
        raise ValueError('Native road direction invalid')
    tangent = [value / norm for value in tangent]
    other = lead.get_location()
    center_gap = (other.x - location.x) * tangent[0] + (other.y - location.y) * tangent[1]
    body_gap = center_gap - float(ego.bounding_box.extent.x) - float(lead.bounding_box.extent.x)
    if not math.isfinite(body_gap):
        raise ValueError('Original Native body gap nonfinite')
    weather = world.get_weather()
    precipitation = float(weather.precipitation)
    if not math.isfinite(precipitation) or not 0 <= precipitation <= 100:
        raise ValueError('Native precipitation readback invalid')
    fog_density = float(weather.fog_density)
    fog_distance = float(weather.fog_distance)
    if (not math.isfinite(fog_density) or not 0 <= fog_density <= 100 or
            not math.isfinite(fog_distance) or fog_distance < 0):
        raise ValueError('Native fog readback invalid')
    following = waypoint.next(5.0)
    if not following:
        raise ValueError('Native road curvature source missing')
    delta = (float(following[0].transform.rotation.yaw) -
             float(waypoint.transform.rotation.yaw) + 180) % 360 - 180
    curvature = abs(math.radians(delta) / 5.0)
    return {'frame': int(snapshot.frame), 'time_s': float(snapshot.timestamp.elapsed_seconds),
            'ego_actor_id': int(ego.id), 'ego_position_m': [float(location.x), float(location.y), float(location.z)],
            'road_id': waypoint.road_id, 'lane_id': waypoint.lane_id,
            'ego_velocity_source': 'actor.get_velocity', 'ego_velocity_mps': ego_vector,
            'lane_width_m': probe['lane_width_m'], 'surface': surface_review['surface'],
            'surface_source': surface_review['source'], 'physical_surface_verified': False,
            'precipitation_percent': precipitation, 'weather_source': 'world.get_weather',
            'fog_density_percent': fog_density, 'fog_distance_m': fog_distance,
            'sight_distance_m': probe['sight_distance_m'], 'sight_ray_source': ray_source,
            'curvature_per_m': curvature, 'curvature_source': 'native-waypoint.next(5.0)',
            'surrounding_traffic': [{'actor_id': int(lead.id), 'velocity_source': 'actor.get_velocity',
                                     'velocity_mps': lead_vector,
                                     'longitudinal_body_gap_m': body_gap}]}
