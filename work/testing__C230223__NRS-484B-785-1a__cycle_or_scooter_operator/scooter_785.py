"""Source-gated physical geometry, scooter classification and original speed measures."""
from dataclasses import dataclass
from math import hypot, isfinite
from package_spec import ACTOR, AID, CELL


@dataclass(frozen=True)
class Case:
    name: str
    speed_mph: float
    ordinance: str
    qualifies: bool
    in_lane: bool


CASES = (
    Case('lane_14_5_mph', 14.5, 'none', True, True),
    Case('lane_15_mph', 15.0, 'none', True, True),
    Case('lane_15_5_mph', 15.5, 'none', True, True),
    Case('lane_14_5_ordinance', 14.5, 'reviewed_ordinance', True, True),
    Case('lane_14_5_nonqualifying', 14.5, 'none', False, True),
    Case('outside_lane_14_5', 14.5, 'none', True, False),
)
SOURCE_ROLES = ('map', 'lane_designation', 'device_specification', 'jurisdiction',
                'ordinance_inventory', 'manufacturer_intent')


def need(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    return type(value) in (int, float) and isfinite(value)


def point(value):
    return isinstance(value, (list, tuple)) and len(value) == 2 and all(number(x) for x in value)


def rect(value):
    return isinstance(value, (list, tuple)) and len(value) == 4 and all(number(x) for x in value) and value[0] < value[2] and value[1] < value[3]


def inside(point_xy, rectangle):
    return rectangle[0] <= point_xy[0] <= rectangle[2] and rectangle[1] <= point_xy[1] <= rectangle[3]


def qualifying_device(device):
    """Only recorded physical definition facts; never infer legal verdict from a label."""
    return (device.get('handlebars') is True and device.get('electric_motor') is True
            and device.get('upright_or_seated') in ('upright', 'seated')
            and device.get('propulsion') in ('motor', 'rider', 'motor_and_rider')
            and number(device.get('rider_excluded_weight_lb'))
            and device['rider_excluded_weight_lb'] <= 100
            and number(device.get('motor_only_max_speed_mph'))
            and device['motor_only_max_speed_mph'] <= 20
            and device.get('manufacturer_assistive_device_intent') is False)


def validate_scene(scene, case):
    need(case in CASES and scene.get('assignment_id') == AID and
         scene.get('cell_id') == CELL and scene.get('actor') == ACTOR,
         'exact scooter cell or case differs')
    need(scene.get('facility_kind') == 'official_bicycle_lane' and
         rect(scene.get('bicycle_lane_rect_m')) and
         rect(scene.get('roadway_rect_m')) and
         scene.get('lane_designation_id') and scene.get('jurisdiction'),
         'official bicycle lane extent and jurisdiction required')
    need(scene.get('ordinance_context') == case.ordinance and
         scene.get('ordinance_effect_judgment') is None,
         'ordinance context or unresolved effect changed')
    if case.ordinance == 'reviewed_ordinance':
        need(scene.get('ordinance_enacted_under_nrs_484a_469') is True and
             scene.get('ordinance_effective_date') and scene.get('ordinance_text_sha256'),
             'official enacted ordinance source required')
    else:
        need(scene.get('ordinance_enacted_under_nrs_484a_469') is False,
             'ordinance absence must be source reviewed')
    need(qualifying_device(scene.get('device', {})) is case.qualifies,
         'reviewed device qualification facts differ')
    route = scene.get('ego_route_xy')
    need(isinstance(route, list) and len(route) >= 2 and all(point(p) for p in route),
         'original scooter route missing')
    lane = scene['bicycle_lane_rect_m']
    need(all(inside(p, lane) is case.in_lane for p in route),
         'planned route does not match bicycle-lane occupancy branch')
    need(all(inside(p, scene['roadway_rect_m']) for p in route),
         'scooter route leaves reviewed roadway context')
    need(hypot(route[-1][0]-route[0][0], route[-1][1]-route[0][1]) >= 250,
         'original scooter route too short for 45-second speed probe')
    for role in SOURCE_ROLES:
        need(scene.get(role+'_source_sha256'), 'independent scooter source missing: '+role)
    return {'case_id': AID+'__'+case.name, 'requested_speed_mph': case.speed_mph,
            'ordinance_effect_judgment': None, 'legal_verdict': None}


def measure_original(rows, scene, case):
    validate_scene(scene, case)
    need(len(rows) == 900, 'original 900-frame scooter history missing')
    first = rows[0].get('original_frame')
    start = rows[0].get('time_s')
    need(type(first) is int and number(start), 'original frame/time missing')
    speeds = []
    occupancy = []
    for index, row in enumerate(rows):
        need(row.get('original_frame') == first+index and number(row.get('time_s')) and
             abs(row['time_s']-start-index/20) <= .005,
             'original scooter frame/time join invalid')
        need(row.get('native_actor_id') and row.get('device_id') == scene['device']['device_id'],
             'original scooter actor/device identity differs')
        need(number(row.get('speed_mps')) and row['speed_mps'] >= 0 and
             len(row.get('body_corners_xy', ())) >= 4 and
             all(point(p) for p in row['body_corners_xy']),
             'original velocity/body corners missing')
        for role in SOURCE_ROLES:
            need(row.get(role+'_source_sha256') == scene[role+'_source_sha256'],
                 'original scooter source changed: '+role)
        speeds.append(row['speed_mps'] / .44704)
        occupancy.append(any(inside(p, scene['bicycle_lane_rect_m']) for p in row['body_corners_xy']))
    steady = speeds[200:800]
    need(len(steady) == 600, 'steady operating speed window missing')
    return {'case_id': AID+'__'+case.name,
            'requested_speed_mph': case.speed_mph,
            'steady_mean_speed_mph': sum(steady)/len(steady),
            'steady_max_speed_mph': max(steady),
            'all_frame_max_speed_mph': max(speeds),
            'bicycle_lane_occupied_frames': sum(occupancy),
            'bicycle_lane_occupancy_requested': case.in_lane,
            'qualifying_device_from_source': qualifying_device(scene['device']),
            'ordinance_context_from_source': scene['ordinance_context'],
            'ordinance_effect_judgment': None,
            'legal_verdict': None}
