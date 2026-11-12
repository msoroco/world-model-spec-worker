"""Native school-zone landmark candidate for NRS 484B.363(3).

Mapped landmarks locate a possible zone. A landmark does not establish public
designation, operative hours, a child-free scene, or an applicable exception.
"""
from math import hypot, isfinite


def measure_school_candidate(scene, landmarks, *, max_distance_m=60.0):
    if not isfinite(max_distance_m) or max_distance_m <= 0:
        raise ValueError('Invalid school landmark search radius')
    waypoint = scene['approach']
    road_id = int(waypoint.road_id)
    origin = waypoint.transform.location
    matches = []
    for source in landmarks:
        if int(source['road_id']) != road_id:
            continue
        fields = {key: str(source.get(key, '')) for key in ('name', 'type', 'value')}
        label = ' '.join(fields.values()).lower().replace('-', ' ').replace('_', ' ')
        if not any(marker in label for marker in ('school zone', 'school crossing')):
            continue
        x, y = map(float, source['xy_m'])
        if not all(isfinite(v) for v in (x, y)):
            raise ValueError('Invalid school landmark position')
        distance = hypot(x - float(origin.x), y - float(origin.y))
        if distance <= max_distance_m:
            matches.append({'landmark_id': str(source['landmark_id']),
                            'road_id': road_id, 'xy_m': [x, y],
                            'source_fields': fields,
                            'distance_to_approach_m': distance})
    if not matches:
        raise ValueError('No source-mapped school-zone landmark near turn lane')
    matches.sort(key=lambda item: (item['distance_to_approach_m'], item['landmark_id']))
    return {'method': 'Native mapped school-zone landmark near turn lane',
            'road_id': road_id,
            'approach_lane_id': int(waypoint.lane_id),
            'approach_xy_m': [float(origin.x), float(origin.y)],
            'search_radius_m': float(max_distance_m),
            'matching_landmarks': matches,
            'official_zone_designation': None,
            'children_present': None,
            'school_in_session': None,
            'governing_body_exempt_period': None,
            'operational_beacon': None,
            'pupils_in_class': None,
            'yellow_beacon_lights_flashing': None,
            'sign_speed_limit_in_effect': None,
            'legal_prohibition_applicable': None}


def collect_native_school_landmarks(carla_map):
    records = []
    for landmark in carla_map.get_all_landmarks():
        transform = getattr(landmark, 'transform', None)
        if transform is None or getattr(landmark, 'road_id', None) is None:
            continue
        records.append({'landmark_id': str(landmark.id),
                        'road_id': int(landmark.road_id),
                        'xy_m': [float(transform.location.x), float(transform.location.y)],
                        'name': str(getattr(landmark, 'name', '')),
                        'type': str(getattr(landmark, 'type', '')),
                        'value': str(getattr(landmark, 'value', ''))})
    return records


def select_363_candidate(carla_map, *, waypoint_spacing_m=2.0, max_candidates=500):
    from u_turn_construction import select_u_turn_scene
    if type(max_candidates) is not int or max_candidates <= 0:
        raise ValueError('Invalid school-zone candidate count')
    landmarks = collect_native_school_landmarks(carla_map)
    for index in range(max_candidates):
        try:
            scene = select_u_turn_scene(carla_map,
                                        waypoint_spacing_m=waypoint_spacing_m,
                                        candidate_index=index)
        except ValueError as error:
            if 'No requested Native opposing-lane U-turn pair' in str(error):
                break
            raise
        try:
            packet = measure_school_candidate(scene, landmarks)
        except ValueError as error:
            if 'No source-mapped school-zone landmark' in str(error):
                continue
            raise
        packet['candidate_index'] = index
        packet['source_landmarks'] = landmarks
        return scene, packet
    raise ValueError('No Native school-zone landmark candidate with opposing lanes')
