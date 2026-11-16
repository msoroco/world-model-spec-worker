"""Source review for the two-directional left-turn destination references."""
import hashlib
import json
import math
from pathlib import Path

from shapely.geometry import LineString, Polygon

from native_road_selection import verify_two_directional_roads


def _points(value, label, minimum):
    if not isinstance(value, list) or len(value) < minimum:
        raise ValueError('Missing '+label)
    points = []
    for item in value:
        if (not isinstance(item, list) or len(item) != 2 or
                any(type(v) not in (int, float) or not math.isfinite(v) for v in item)):
            raise ValueError('Invalid '+label)
        points.append(tuple(float(v) for v in item))
    return points


def _source(root, reference, label):
    if not isinstance(reference, dict) or not reference.get('path') or not reference.get('sha256'):
        raise ValueError('Missing '+label+' source')
    path = Path(reference['path'])
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Unsafe '+label+' source path')
    path = Path(root)/path
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != reference['sha256']:
        raise ValueError('Stale or missing '+label+' source')
    return {'path': reference['path'], 'sha256': reference['sha256']}


def validate(packet, root, world):
    """Bind reviewed documents to the exact Native junction and exit geometry."""
    if not isinstance(packet, dict):
        raise ValueError('Site packet required')
    mapping = world.get_map()
    if packet.get('native_map_id') != mapping.name or not packet.get('intersection_id'):
        raise ValueError('Native map or junction identity differs')
    approach, outgoing = packet.get('approach_road_id'), packet.get('outgoing_road_id')
    if type(approach) is not int or type(outgoing) is not int:
        raise ValueError('Two Native road identities required')
    lanes = verify_two_directional_roads(world, approach, outgoing)
    if packet.get('centerline_kind') not in ('marked', 'imaginary'):
        raise ValueError('Marked or imaginary destination centerline required')
    centerline = LineString(_points(packet.get('destination_centerline_xy_m'), 'destination centerline', 2))
    right = Polygon(_points(packet.get('destination_right_half_polygon_xy_m'), 'destination right half', 3))
    junction = Polygon(_points(packet.get('junction_polygon_xy_m'), 'junction polygon', 3))
    if (centerline.length <= 0 or not right.is_valid or right.area <= 0 or
            not junction.is_valid or junction.area <= 0 or
            not centerline.intersects(right.boundary) or not right.intersects(junction)):
        raise ValueError('Destination centerline, right half or junction geometry differs')
    source_names = ('approach_road_source', 'outgoing_road_source',
                    'destination_centerline_source', 'destination_right_half_source',
                    'junction_source')
    sources = {name: _source(root, packet.get(name), name) for name in source_names}
    if len({value['path'] for value in sources.values()}) != len(sources):
        raise ValueError('Distinct geometry source documents required')
    if not packet.get('reviewer') or not packet.get('review_basis'):
        raise ValueError('Explicit site review basis required')
    return {'format': 'worker-c109705-destination-site-review',
            'native_map_id': packet['native_map_id'],
            'intersection_id': packet['intersection_id'],
            'approach_road_id': approach, 'outgoing_road_id': outgoing,
            'centerline_kind': packet['centerline_kind'],
            'native_lane_inventory': lanes, 'sources': sources,
            'destination_geometry_sha256': hashlib.sha256(json.dumps({
                'centerline': list(centerline.coords), 'right_half': list(right.exterior.coords),
                'junction': list(junction.exterior.coords)}, sort_keys=True).encode()).hexdigest(),
            'physical_exit_position': 'unverified',
            'legal_two_directional_status': 'unresolved'}
