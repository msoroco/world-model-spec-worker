"""Build a source-checkable fire-lane stop comparison from a live map survey.

The geometry check is an engineering construction guard. It does not prove City
Fire Code designation, actual sign text, Native stopping, or a legal violation.
"""
from math import isfinite

from shapely.geometry import LineString, Point, Polygon


CAMERAS = ('overview', 'approach', 'curb_sign', 'driver_reference')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def point(value, name):
    require(isinstance(value, list) and len(value) == 2 and
            all(type(v) in (int, float) and isfinite(v) for v in value),
            name + ' needs finite XY coordinates')
    return Point(value)


def polygon(value, name):
    require(isinstance(value, list) and len(value) >= 3,
            name + ' needs at least three vertices')
    vertices = [point(v, name) for v in value]
    shape = Polygon([(v.x, v.y) for v in vertices])
    require(shape.is_valid and not shape.is_empty and shape.area > 0,
            name + ' has invalid area')
    return shape


def build(survey, map_probe):
    """Return two same-context construction plans from surveyed geometry.

    map_probe(XY) must perform a live CARLA driving-road lookup in the eventual
    runner. A CPU fake may exercise this contract without claiming original data.
    """
    required = {'map_name', 'cell_id', 'curb_polyline_xy_m',
                'authored_fire_lane_polygon_xy_m', 'posted_sign_xy_m',
                'posted_sign_actor_id', 'posted_sign_authored_text',
                'stop_footprints_xy_m', 'capture_frames', 'capture_hz',
                'camera_names', 'property_context', 'fire_code_designation_review'}
    require(isinstance(survey, dict) and required <= set(survey),
            'Fire-lane survey is missing construction inputs')
    require(survey['cell_id'] == 'C201084' and
            isinstance(survey['map_name'], str) and survey['map_name'],
            'Survey map/cell identity differs')
    require(survey['capture_hz'] == 20 and survey['capture_frames'] >= 600 and
            survey['camera_names'] == list(CAMERAS),
            'Thirty-second four-camera capture contract differs')
    require(survey['property_context'] in ('public', 'private') and
            survey['fire_code_designation_review'] == 'pending_original_source',
            'Property or Fire Code source review is missing')
    require(type(survey['posted_sign_actor_id']) is int and
            survey['posted_sign_actor_id'] > 0 and
            survey['posted_sign_authored_text'] == 'FIRE LANE',
            'Posted fire-lane sign construction identity differs')
    curb_values = survey['curb_polyline_xy_m']
    require(isinstance(curb_values, list) and len(curb_values) >= 2,
            'Curb needs two surveyed points')
    curb = LineString([(p.x, p.y) for p in
                       (point(value, 'curb') for value in curb_values)])
    require(curb.is_simple and curb.length > 5,
            'Curb survey has no usable extent')
    zone = polygon(survey['authored_fire_lane_polygon_xy_m'], 'fire-lane zone')
    sign = point(survey['posted_sign_xy_m'], 'posted sign')
    require(zone.distance(curb) <= 0.25 and
            sign.distance(curb) <= 3 and sign.distance(zone) <= 3,
            'Posted zone/sign is not adjacent to the surveyed curb')
    footprints = survey['stop_footprints_xy_m']
    require(isinstance(footprints, dict) and
            set(footprints) == {'reference', 'contrast'},
            'Inside/outside stop footprints are required')
    inside = polygon(footprints['reference'], 'reference footprint')
    outside = polygon(footprints['contrast'], 'contrast footprint')
    require(zone.covers(inside) and zone.disjoint(outside),
            'Requested stops do not isolate fire-lane footprint occupancy')
    require(inside.distance(curb) <= 3 and outside.distance(curb) <= 3,
            'Both destination stops must remain near the same curb')
    require(callable(map_probe), 'Live map probe is required')
    road_rows = {}
    for name, shape in (('reference', inside), ('contrast', outside)):
        sample = map_probe([shape.centroid.x, shape.centroid.y])
        require(isinstance(sample, dict) and
                type(sample.get('road_id')) is int and
                type(sample.get('lane_id')) is int and
                sample.get('map_name') == survey['map_name'] and
                sample.get('drivable_access') is True,
                name + ' lacks live same-map vehicle access')
        road_rows[name] = sample
    require(road_rows['reference']['road_id'] == road_rows['contrast']['road_id'],
            'Stop comparison changes road identity')
    return {'format': 'c201084-fire-lane-construction-plan-v1',
            'map_name': survey['map_name'], 'cell_id': survey['cell_id'],
            'capture_frames': survey['capture_frames'],
            'capture_hz': survey['capture_hz'], 'camera_names': list(CAMERAS),
            'survey_geometry': {
                'curb_polyline_xy_m': curb_values,
                'authored_fire_lane_polygon_xy_m':
                    survey['authored_fire_lane_polygon_xy_m'],
                'posted_sign_xy_m': survey['posted_sign_xy_m'],
                'planned_stop_footprints_xy_m': footprints},
            'fixed_context': {'property_context': survey['property_context'],
                              'posted_sign_actor_id': survey['posted_sign_actor_id'],
                              'road_id': road_rows['reference']['road_id']},
            'cases': {name: {'stop_center_xy_m': [shape.centroid.x, shape.centroid.y],
                             'road_readback': road_rows[name],
                             'authored_zone_footprint_relation':
                                 'inside' if name == 'reference' else 'outside'}
                      for name, shape in (('reference', inside), ('contrast', outside))},
            'posting_designation_verified': False,
            'original_sign_text_verified': False,
            'original_stop_footprint_verified': False,
            'physical_or_legal_completion_claimed': False}
