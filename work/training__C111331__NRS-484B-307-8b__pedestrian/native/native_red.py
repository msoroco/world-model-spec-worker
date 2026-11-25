"""Authored C111331 red-head route and fail-closed Native source survey.

The surveyed actor state is an original source. Its legal authority and visible
display remain independent post-capture review questions.
"""

import hashlib
import math
from pathlib import Path
import xml.etree.ElementTree as ET

ASSIGNMENT = 'training__C111331__NRS-484B-307-8b__pedestrian'
ROAD = Path(__file__).with_name('road.xodr')
RATE_HZ = 20
FRAMES = 600
BOUNDARY_Y = 3.5
WALKER_X = 8.0
START_Y = 5.0
SIGNAL_ID = '3078b-facing-steady-red'
OTHER_ID = '3078b-other-pedestrian-device'
SIGNAL_OD_ID = '301'
OTHER_OD_ID = '302'
CAMERAS = (
    ('overview', 1920, 1080, (-2, 10, 12, -30, -35)),
    ('approach', 1280, 720, (8, 9, 4, -90, -18)),
    ('reference_corner', 1280, 720, (4, 5, 3, -55, -20)),
    ('driver_reference', 1280, 720, (9, 5, 2, -90, -8)),
)
CONDITIONS = {
    'condition_a': {'enter': False, 'other': 'dont_walk'},
    'condition_b': {'enter': True, 'other': 'dont_walk'},
    'exception_absent': {'enter': True, 'other': 'dont_walk'},
    'exception_permits': {'enter': True, 'other': 'walk'},
    'exception_countdown': {'enter': True, 'other': 'flashing_dont_walk_countdown'},
}
REQUIRED_ATOMS = ['ru.pedestrian', 'ru.subject', 'kin.position', 'kin.heading',
                  'st.intersection', 'st.crosswalk', 'rel.occupies',
                  'dev.traffic_signal', 'dev.governs']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_map(path=ROAD):
    root = ET.parse(path).getroot()
    roads = root.findall('road')
    if len(roads) != 2 or {r.get('id') for r in roads} != {'1', '2'}:
        raise ValueError('Authored two-road intersection is missing')
    by_id = {r.get('id'): r for r in roads}
    east_west = by_id['2']
    geometry = east_west.find('planView/geometry')
    if (geometry is None or float(geometry.get('x')) != -20 or
            float(geometry.get('y')) != 0 or float(geometry.get('hdg')) != 0):
        raise ValueError('East-west road axis differs')
    lane_widths = [float(w.get('a')) for w in east_west.findall('lanes/laneSection/left/lane/width') +
                   east_west.findall('lanes/laneSection/right/lane/width')]
    if lane_widths != [BOUNDARY_Y, BOUNDARY_Y]:
        raise ValueError('Highway lateral boundary source differs')
    if WALKER_X <= BOUNDARY_Y or START_Y <= BOUNDARY_Y:
        raise ValueError('Walker must start outside both roadway corridors')
    signals = {s.get('id'): s for r in roads for s in r.findall('signals/signal')}
    if set(signals) != {SIGNAL_OD_ID, OTHER_OD_ID}:
        raise ValueError('Both distinct OpenDRIVE devices required')
    if (signals[SIGNAL_OD_ID].get('name') != SIGNAL_ID or
            signals[OTHER_OD_ID].get('name') != OTHER_ID or
            any(s.get('dynamic') != 'yes' for s in signals.values())):
        raise ValueError('Authored device identity differs')
    return {'map_sha256': sha(path), 'roadway_y_abs_max_m': BOUNDARY_Y,
            'walker_start_xy_m': [WALKER_X, START_Y],
            'native_map_loaded': False, 'device_governance_verified': False}


def plan(condition, candidate='primary'):
    if condition not in CONDITIONS or candidate not in ('primary', 'fallback1'):
        raise ValueError('Unknown red-entry condition or candidate')
    request = CONDITIONS[condition]
    return {'case_id': ASSIGNMENT + '__selected_0b864230__' + condition,
            'condition': condition, 'candidate_id': candidate,
            'cell_id': 'C111331', 'law_id': 'NRS-484B-307-8b',
            'actor': 'pedestrian', 'rate_hz': RATE_HZ, 'duration_s': 30,
            'frames': FRAMES, 'map': 'road.xodr',
            'map_sha256': sha(ROAD), 'traffic_head_id': SIGNAL_ID,
            'other_device_id': OTHER_ID,
            'requested_traffic': 'steady_red_alone',
            'requested_other_device': request['other'],
            'requested_entry': request['enter'],
            'walker_start_xy_m': [WALKER_X, START_Y + (.8 if candidate == 'fallback1' else 0)],
            'walker_direction_xy': [0, -1],
            'roadway_y_abs_max_m': BOUNDARY_Y,
            'required_atoms': REQUIRED_ATOMS,
            'cameras': [{'name': name, 'width': width, 'height': height,
                         'pose_strategy': 'fixed_crossing_source_view', 'fov_deg': 90}
                        for name, width, height, _ in CAMERAS],
            'native_governance_verified': False,
            'physical_pixels_verified': False,
            'legal_verdict': None}


def check_plan(config):
    expected = plan(config['condition'], config['candidate_id'])
    for field, value in expected.items():
        if config.get(field) != value:
            raise ValueError('Exact red-entry plan differs: ' + field)
    check_map()
    return {'case_id': expected['case_id'], 'frames': FRAMES,
            'camera_count': len(CAMERAS), 'native_executed': False}


def resolve_heads(actors):
    result = {}
    for actor in actors:
        if not str(getattr(actor, 'type_id', '')).startswith('traffic.traffic_light'):
            continue
        get_id = getattr(actor, 'get_opendrive_id', None)
        if get_id is None:
            continue
        od_id = str(get_id())
        if od_id in (SIGNAL_OD_ID, OTHER_OD_ID):
            if od_id in result:
                raise ValueError('Ambiguous Native OpenDRIVE head ' + od_id)
            result[od_id] = actor
    if set(result) != {SIGNAL_OD_ID, OTHER_OD_ID} or result[SIGNAL_OD_ID].id == result[OTHER_OD_ID].id:
        raise ValueError('Both distinct Native signal actors required')
    return result


def configure_heads(heads, config, carla):
    check_plan(config)
    requested = {SIGNAL_OD_ID: carla.TrafficLightState.Red,
                 OTHER_OD_ID: (carla.TrafficLightState.Green if
                               config['requested_other_device'] == 'walk' else
                               carla.TrafficLightState.Red)}
    for od_id, state in requested.items():
        heads[od_id].set_state(state)
        heads[od_id].freeze(True)
    observed = sample_heads(heads)
    expected_other = ('dont_walk' if config['condition'] == 'exception_countdown'
                      else config['requested_other_device'])
    if observed['traffic']['state'] != 'red' or observed['other']['state'] != expected_other:
        raise ValueError('Native head readback differs from request')
    return observed


def sample_heads(heads):
    roles = ((SIGNAL_OD_ID, 'traffic', SIGNAL_ID),
             (OTHER_OD_ID, 'other', OTHER_ID))
    observed = {}
    for od_id, role, named_id in roles:
        actor = heads[od_id]
        if str(actor.get_opendrive_id()) != od_id:
            raise ValueError('Original head identity changed')
        raw = str(actor.get_state()).split('.')[-1].lower()
        if raw not in ('red', 'green', 'off'):
            raise ValueError('Unsupported original head state')
        observed[role] = {'named_id': named_id, 'opendrive_id': od_id,
                          'native_actor_id': actor.id,
                          'state': ({'green': 'walk', 'red': 'dont_walk', 'off': 'off'}[raw]
                                    if role == 'other' else raw),
                          'source_kind': 'native_device_readback'}
    return observed


def requested_speed(condition, frame):
    if condition not in CONDITIONS or not isinstance(frame, int) or frame < 0 or frame >= FRAMES:
        raise ValueError('Invalid pedestrian control request')
    if not CONDITIONS[condition]['enter'] or frame < 180 or frame >= 300:
        return 0.0
    return 1.2


def countdown_program(frame):
    if type(frame) is not int or not 0 <= frame < FRAMES:
        raise ValueError('Invalid countdown source frame')
    flashing = 180 <= frame < 380
    remaining = math.ceil((380 - frame) / 20) if flashing else None
    illuminated = (frame // 5) % 2 == 0 if flashing else True
    return {'flashing': flashing, 'countdown_seconds': remaining,
            'illuminated': illuminated,
            'source_scope': 'authored_debug_countdown_not_original_pixels'}


def command_countdown_head(head, carla, frame):
    program = countdown_program(frame)
    head.set_state(carla.TrafficLightState.Red if program['illuminated'] else
                   carla.TrafficLightState.Off)
    head.freeze(True)
    raw = str(head.get_state()).split('.')[-1].lower()
    if raw != ('red' if program['illuminated'] else 'off'):
        raise ValueError('Native countdown head readback differs')
    return program


def measure_entry(rows, config):
    check_plan(config)
    if len(rows) != FRAMES:
        raise ValueError('Original walker source incomplete')
    first = None
    for index, row in enumerate(rows):
        if row.get('video_frame') != index or row.get('traffic', {}).get('state') != 'red':
            raise ValueError('Missing or changed red-entry source')
        if config['condition'] == 'exception_countdown':
            program = countdown_program(index)
            if row.get('display_program') != program or row.get('other', {}).get('state') != (
                    'dont_walk' if program['illuminated'] else 'off'):
                raise ValueError('Countdown original-source program differs')
        elif row.get('other', {}).get('state') != config['requested_other_device']:
            raise ValueError('Missing or changed red-entry source')
        feet = row.get('footprint_xy_m')
        if not isinstance(feet, list) or len(feet) != 4 or any(len(point) != 2 for point in feet):
            raise ValueError('Original walker footprint incomplete')
        if any(not math.isfinite(v) for point in feet for v in point):
            raise ValueError('Nonfinite original walker footprint')
        if any(point[1] < BOUNDARY_Y for point in feet) and first is None:
            first = index
    if bool(first is not None) != config['requested_entry']:
        raise ValueError('Pedestrian entry contrast absent')
    if config['condition'] == 'exception_countdown' and (
            first is None or not countdown_program(first)['flashing'] or
            countdown_program(first)['countdown_seconds'] <= 0):
        raise ValueError('Countdown entry-before-zero contrast absent')
    return {'first_roadway_footprint_frame': first,
            'governing_head_original_review_required': True,
            'other_device_original_review_required': True,
            'legal_verdict': None}
