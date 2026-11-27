"""Exact excavation parking probes; physical measurements leave legal judgments open."""
from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    case_id: str
    relation: str
    activity: str
    passage: str
    exception: str


CASES = (
    Case('alongside_park_narrow', 'alongside', 'park', 'narrow', 'none'),
    Case('opposite_park_narrow', 'opposite', 'park', 'narrow', 'none'),
    Case('alongside_park_open', 'alongside', 'park', 'open', 'none'),
    Case('alongside_stop_conflict', 'alongside', 'stop', 'narrow', 'conflict_avoidance'),
    Case('alongside_stand_officer', 'alongside', 'stand', 'narrow', 'officer_direction'),
    Case('alongside_park_device', 'alongside', 'park', 'narrow', 'official_device'),
    Case('alongside_park_law', 'alongside', 'park', 'narrow', 'law'),
    Case('alongside_stop_ordinary', 'alongside', 'stop', 'narrow', 'none'),
    Case('alongside_stand_ordinary', 'alongside', 'stand', 'narrow', 'none'),
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(value):
    return type(value) in (int, float) and isfinite(value)


def rect(value):
    return (isinstance(value, (list, tuple)) and len(value) == 4 and
            all(number(v) for v in value) and value[0] < value[2] and
            value[1] < value[3])


def separation(a, b):
    """Minimum axis-aligned body/excavation separation, zero at contact."""
    require(rect(a) and rect(b), 'measured body/excavation rectangles missing')
    dx = max(a[0] - b[2], b[0] - a[2], 0)
    dy = max(a[1] - b[3], b[1] - a[3], 0)
    return (dx * dx + dy * dy) ** .5


def available_passage_width(lane_span_y, body_rect, excavation_rect):
    """Largest lateral open span after conservative obstacle projection."""
    require(isinstance(lane_span_y, (list, tuple)) and len(lane_span_y) == 2 and
            all(number(v) for v in lane_span_y) and lane_span_y[0] < lane_span_y[1],
            'traffic lane cross-section missing')
    require(rect(body_rect) and rect(excavation_rect),
            'original obstruction geometry missing')
    low, high = lane_span_y
    blocked = sorted((max(low, item[1]), min(high, item[3]))
                     for item in (body_rect, excavation_rect)
                     if item[3] > low and item[1] < high)
    cursor, widths = low, []
    for left, right in blocked:
        widths.append(max(0.0, left - cursor))
        cursor = max(cursor, right)
    widths.append(max(0.0, high - cursor))
    return max(widths)


def validate_scene(scene: Mapping, case: Case):
    require(case in CASES, 'unknown exact excavation case')
    require(scene.get('cell_id') == 'C229405' and
            scene.get('actor') == 'motor_vehicle_driver' and
            scene.get('driver_present') is True and
            scene.get('motor_vehicle') is True, 'qualifying driver/vehicle missing')
    require(scene.get('highway_public_access') is True and
            scene.get('highway_dedicated') is True, 'highway basis missing')
    require(scene.get('excavation_kind') == 'highway_excavation',
            'excavation classification missing')
    require(scene.get('relation') == case.relation and
            scene.get('halt_activity') == case.activity and
            scene.get('passage') == case.passage and
            scene.get('exception') == case.exception,
            'case variables differ from exact construction')
    for field in ('highway', 'vehicle', 'driver', 'excavation', 'parking_route',
                  'traffic_route', 'traffic_actor', 'halt_activity', 'exception'):
        require(scene.get(field + '_source_sha256'),
                'original context missing: ' + field)
    for field in ('vehicle_target_xy', 'traffic_start_xy'):
        point = scene.get(field)
        require(isinstance(point, list) and len(point) == 2 and
                all(number(v) for v in point), field + ' missing')
    require(rect(scene.get('excavation_rect_m')) and
            rect(scene.get('target_body_rect_m')), 'target geometry missing')
    centerline = scene.get('road_centerline_y_m')
    require(number(centerline), 'road centerline missing')
    excavation_side = (scene['excavation_rect_m'][1] +
                       scene['excavation_rect_m'][3]) / 2 - centerline
    vehicle_side = (scene['target_body_rect_m'][1] +
                    scene['target_body_rect_m'][3]) / 2 - centerline
    require((excavation_side * vehicle_side > 0) == (case.relation == 'alongside') and
            excavation_side * vehicle_side != 0,
            'vehicle relation not constructed from road geometry')
    require(number(scene.get('planned_passage_width_m')) and
            scene['planned_passage_width_m'] > 0,
            'planned traffic passage missing')
    available_passage_width(scene.get('traffic_lane_span_y_m'),
                            scene['target_body_rect_m'], scene['excavation_rect_m'])
    for field in ('parking_route_xy', 'traffic_route_xy'):
        route = scene.get(field)
        require(isinstance(route, list) and len(route) >= 2 and
                all(isinstance(point, list) and len(point) == 2 and
                    all(number(v) for v in point) for point in route),
                field + ' missing')
    if case.exception == 'conflict_avoidance':
        require(scene.get('conflicting_traffic_id'), 'conflicting actor missing')
    if case.exception in ('officer_direction', 'official_device', 'law'):
        require(scene.get('authority_record_id'), 'authority record missing')
    return {'case_id': case.case_id, 'legal_obstruction_judgment': None,
            'legal_exception_judgment': None}


def construct(adapter, scene: Mapping, case: Case):
    context = validate_scene(scene, case)
    owned = []
    try:
        adapter.place_excavation(scene['excavation_rect_m'])
        ego = adapter.spawn_motor_vehicle(scene['vehicle_target_xy'])
        require(ego is not None, 'motor vehicle spawn failed')
        owned.append(ego)
        traffic = adapter.spawn_traffic(scene['traffic_start_xy'])
        require(traffic is not None, 'traffic spawn failed')
        owned.append(traffic)
        adapter.set_halt_route(ego, scene['parking_route_xy'], case.activity)
        adapter.set_traffic_route(traffic, scene['traffic_route_xy'])
        adapter.set_exception_context(case.exception, scene.get('authority_record_id'),
                                      scene.get('conflicting_traffic_id'))
        return {'owned': tuple(owned), **context}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def measure_original(rows: list[Mapping], scene: Mapping, case: Case):
    validate_scene(scene, case)
    require(len(rows) == 900, 'original 900-frame capture missing')
    start = rows[0].get('original_frame')
    require(type(start) is int and number(rows[0].get('time_s')),
            'original frame/time identity missing')
    vehicle_id = traffic_id = None
    gaps, widths, traffic_speeds, halt_speeds = [], [], [], []
    for i, row in enumerate(rows):
        require(row.get('original_frame') == start + i and
                number(row.get('time_s')) and
                abs(row['time_s'] - rows[0]['time_s'] - i / 20) <= .005,
                'original frame/time join invalid')
        for field in ('frame', 'vehicle_motion', 'vehicle_body', 'excavation',
                      'passage', 'traffic_motion', 'activity', 'exception'):
            require(row.get(field + '_source_sha256'),
                    'original measurement source missing: ' + field)
        require(row.get('excavation_source_sha256') ==
                scene['excavation_source_sha256'] and
                row.get('halt_activity') == case.activity and
                row.get('exception') == case.exception and
                row.get('relation') == case.relation,
                'original excavation/case context changed')
        require(row.get('vehicle_id') and row.get('traffic_id'),
                'participant identity missing')
        vehicle_id = vehicle_id or row['vehicle_id']
        traffic_id = traffic_id or row['traffic_id']
        require(row['vehicle_id'] == vehicle_id and
                row['traffic_id'] == traffic_id and vehicle_id != traffic_id,
                'participant identity changed')
        require(rect(row.get('vehicle_body_rect_m')) and
                rect(row.get('excavation_rect_m')),
                'original physical geometry missing')
        for field in ('passage_width_m', 'traffic_speed_mps', 'vehicle_speed_mps'):
            require(number(row.get(field)) and row[field] >= 0,
                    'original physical stream missing: ' + field)
        actual_width = available_passage_width(scene['traffic_lane_span_y_m'],
                                               row['vehicle_body_rect_m'],
                                               row['excavation_rect_m'])
        require(abs(row['passage_width_m'] - actual_width) <= 0.001,
                'passage width differs from original body and road geometry')
        gaps.append(separation(row['vehicle_body_rect_m'],
                               row['excavation_rect_m']))
        widths.append(row['passage_width_m'])
        traffic_speeds.append(row['traffic_speed_mps'])
        halt_speeds.append(row['vehicle_speed_mps'])
    require(min(halt_speeds) <= .1, 'requested halt never observed')
    require(max(traffic_speeds) > 0, 'traffic movement never observed')
    return {'case_id': case.case_id, 'frame_count': len(rows),
            'minimum_body_excavation_gap_m': min(gaps),
            'minimum_available_passage_width_m': min(widths),
            'minimum_traffic_speed_mps': min(traffic_speeds),
            'maximum_traffic_speed_mps': max(traffic_speeds),
            'legal_obstruction_judgment': None,
            'legal_exception_judgment': None}
