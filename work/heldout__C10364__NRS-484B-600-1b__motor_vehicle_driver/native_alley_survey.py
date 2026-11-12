"""Bind an operator-reviewed alley annotation to the live Native map.

The diagnostic polygon in the construction bundle is never promoted to a
physical alley. Native execution requires a separate, reviewed map source.
"""

from hashlib import sha256
import json
import math
import os
from pathlib import Path

from shapely.geometry import Point, Polygon


FORMAT = 'worker-native-alley-survey-v1'


def _route_reference(document, direction):
    reference = document.get('routes', {}).get(direction)
    if not isinstance(reference, dict):
        raise ValueError('Operator alley survey lacks the selected route')
    if (type(reference.get('road_id')) is not int or
            type(reference.get('lane_id')) is not int or
            type(reference.get('start_s')) not in (int, float) or
            not math.isfinite(reference['start_s'])):
        raise ValueError('Operator alley route has no exact map waypoint')
    return reference


def verify(world_map, document, direction, raw_sha256):
    if (document.get('format') != FORMAT or
            document.get('map_name') != world_map.name or
            document.get('opendrive_sha256') !=
            sha256(world_map.to_opendrive().encode('utf-8')).hexdigest()):
        raise ValueError('Operator alley survey differs from Native map/OpenDRIVE')
    if (not document.get('reviewer') or not document.get('evidence_reference') or
            document.get('verified_alley') is not True):
        raise ValueError('Operator-reviewed physical alley identity is incomplete')
    polygon_xy = document.get('polygon_xy')
    if (not isinstance(polygon_xy, list) or len(polygon_xy) < 4 or
            any(not isinstance(point, list) or len(point) != 2 or
                any(type(value) not in (int, float) or not math.isfinite(value)
                    for value in point) for point in polygon_xy)):
        raise ValueError('Operator alley polygon is incomplete')
    polygon = Polygon(polygon_xy)
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError('Operator alley polygon is invalid')
    width = document.get('alley_width_m')
    if type(width) not in (int, float) or not math.isfinite(width) or width < 5:
        raise ValueError('Operator alley width cannot hold the participant layout')
    reference = _route_reference(document, direction)
    waypoint = world_map.get_waypoint_xodr(reference['road_id'],
                                           reference['lane_id'], reference['start_s'])
    if waypoint is None:
        raise ValueError('Operator alley route waypoint absent from Native map')
    receipt = {'format': 'worker-native-alley-verification-v1',
               'verified': True, 'map_name': world_map.name,
               'opendrive_sha256': document['opendrive_sha256'],
               'operator_manifest_sha256': raw_sha256,
               'operator_reviewer': document['reviewer'],
               'evidence_reference': document['evidence_reference'],
               'selected_direction': direction, 'selected_route': reference,
               'polygon_xy': polygon_xy, 'alley_width_m': width,
               'physical_alley_identity_claimed_by_package': False}
    return {'polygon_xy': polygon_xy, 'alley_width_m': width,
            'route_reference': reference}, receipt


def load_and_verify(world_map, output, direction):
    filename = os.environ.get('CARLA_ALLEY_SURVEY')
    if not filename:
        raise ValueError('CARLA_ALLEY_SURVEY operator manifest required at Native execution')
    raw = Path(filename).read_bytes()
    digest = sha256(raw).hexdigest()
    document = json.loads(raw)
    scope, receipt = verify(world_map, document, direction, digest)
    root = Path(output)
    original = root / 'alley-survey-original.json'
    verified = root / 'alley-survey-verification.json'
    if original.exists() or verified.exists():
        raise ValueError('Retain prior Native alley survey sources')
    original.write_bytes(raw)
    verified.write_text(json.dumps(receipt, indent=2) + '\n')
    return scope, receipt


def validate_placement(scope, placement):
    """Keep the planned participant bodies within the surveyed alley polygon."""
    polygon = Polygon(scope['polygon_xy'])
    for label, point, radius in (
            ('pedestrian', placement.pedestrian, .3),
            ('property vehicle', placement.property_center, 1.0)):
        if not polygon.buffer(-radius).covers(Point(point.x, point.y)):
            raise ValueError('Native alley ' + label + ' placement leaves surveyed polygon')
