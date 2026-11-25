"""Fail-closed original map and weather survey before bicycle spawning."""
import math
import xml.etree.ElementTree as ET

SAMPLES_X = (-50.0, -25.0, -3.0)


def inspect(world, carla):
    mapping = world.get_map()
    opendrive = mapping.to_opendrive()
    root = ET.fromstring(opendrive)
    road = next((item for item in root.findall('road') if item.get('id') == '1'), None)
    if road is None:
        raise ValueError('Original governed approach road missing')
    geometry = road.find('planView/geometry')
    signs = road.findall('signals/signal')
    sign = next((s for s in signs if s.get('id') == '901' and
                 s.get('name') == 'STOP'), None)
    if geometry is None or sign is None:
        raise ValueError('Original stop sign or road geometry missing')
    start_x = float(geometry.get('x'))
    start_y = float(geometry.get('y'))
    heading = float(geometry.get('hdg'))
    sign_x = start_x + float(sign.get('s')) * math.cos(heading)
    if abs(heading) > 1e-3 or abs(sign_x) > .3 or abs(start_x+222) > .3:
        raise ValueError('Original stop sign position differs from authored route')
    lanes = []
    for x in SAMPLES_X:
        waypoint = mapping.get_waypoint(carla.Location(x=x, y=-1.75, z=1.0),
                                       project_to_road=True,
                                       lane_type=carla.LaneType.Driving)
        if (waypoint is None or waypoint.road_id != 1 or waypoint.lane_id != -1 or
                abs(waypoint.transform.location.x-x) > .5 or
                abs(waypoint.transform.location.y+1.75) > .5):
            raise ValueError('Original bicycle approach lane differs')
        lanes.append({'sample_x_m': x, 'road_id': waypoint.road_id,
                      'lane_id': waypoint.lane_id,
                      'projected_x_m': waypoint.transform.location.x,
                      'projected_y_m': waypoint.transform.location.y})
    weather = world.get_weather()
    precipitation = float(weather.precipitation)
    wetness = float(weather.wetness)
    if not (math.isfinite(precipitation) and math.isfinite(wetness)):
        raise ValueError('Original weather readback invalid')
    return {'format': 'c111325-original-bicycle-route-survey-v1',
            'route_lane_verified': True,
            'stop_sign_governs_route': True,
            'approach_clearance_verified': True,
            'stop_sign_road_id': 1, 'stop_sign_signal_id': 901,
            'stop_sign_x_m': sign_x, 'bicycle_stop_x_m': -2.0,
            'lane_samples': lanes, 'precipitation': precipitation,
            'wetness': wetness,
            'weather_readback_only': True,
            'municipal_jurisdiction_review_pending': True,
            'bicycle_legal_classification_review_pending': True,
            'legal_prudence_verdict': None}
