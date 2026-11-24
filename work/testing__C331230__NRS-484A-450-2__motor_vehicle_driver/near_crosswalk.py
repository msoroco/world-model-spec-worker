"""Source-bound near-side crosswalk stop probes for NRS 484A.450(2)."""
from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    name: str
    marked: bool
    halt: bool


CASES = (
    Case('marked_crosswalk_halt', True, True),
    Case('marked_crosswalk_rolling', True, False),
    Case('unmarked_crosswalk_halt', False, True),
    Case('unmarked_crosswalk_rolling', False, False),
)


SOURCES = ('driver_identity', 'vehicle_class', 'driver_control',
           'stop_sign_governance', 'stop_sign_orientation',
           'intersection_geometry', 'near_side_crosswalk_geometry',
           'opposing_sidewalk_connections', 'crosswalk_marking',
           'vehicle_trajectory', 'vehicle_speed', 'vehicle_front_extent',
           'pedestrian_route', 'delivery_device_route')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(v):
    return type(v) in (int, float) and isfinite(v)


def point(v):
    return isinstance(v, (list, tuple)) and len(v) == 2 and all(number(x) for x in v)


def rect(v):
    return (isinstance(v, (list, tuple)) and len(v) == 4 and
            all(number(x) for x in v) and v[0] < v[2] and v[1] < v[3])


def inside(p, box):
    return box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]


def validate_scene(scene: Mapping, case: Case):
    require(case in CASES, 'unknown near-side crosswalk case')
    require(scene.get('cell_id') == 'C331230' and
            scene.get('actor') == 'motor_vehicle_driver' and
            scene.get('qualifying_vehicle') is True and
            scene.get('driver_control') is True and
            scene.get('driver_id') and scene.get('vehicle_id'),
            'driver/vehicle/control context missing')
    require(scene.get('marked') is case.marked and
            scene.get('halt') is case.halt and
            scene.get('stop_sign_governs') is True,
            'case/sign governance changed')
    for name in SOURCES:
        require(scene.get(name + '_source_sha256'),
                'independent source missing: ' + name)
    require(rect(scene.get('intersection_rect_m')) and
            rect(scene.get('near_crosswalk_rect_m')) and
            point(scene.get('opposing_sidewalk_left_xy')) and
            point(scene.get('opposing_sidewalk_right_xy')),
            'intersection/sidewalk-crosswalk geometry missing')
    route = scene.get('vehicle_route_xy')
    require(isinstance(route, list) and len(route) >= 2 and
            all(point(p) for p in route), 'approach route missing')
    require(type(scene.get('crosswalk_entry_frame')) is int and
            0 < scene['crosswalk_entry_frame'] < 900,
            'crosswalk entry timing missing')
    return {'case_id': case.name, 'stop_before_crosswalk_judgment': None}


def construct(adapter, scene: Mapping, case: Case):
    context = validate_scene(scene, case)
    vehicle = adapter.spawn_vehicle(scene['vehicle_route_xy'][0])
    require(vehicle is not None, 'vehicle spawn failed')
    try:
        adapter.set_stop_sign(scene['stop_sign_governs'])
        adapter.set_crosswalk(scene['near_crosswalk_rect_m'], case.marked)
        adapter.set_vehicle_route(vehicle, scene['vehicle_route_xy'],
                                  case.halt, scene['crosswalk_entry_frame'])
        return {'owned': (vehicle,), **context}
    except Exception:
        adapter.destroy(vehicle)
        raise


def measure_original(rows: list[Mapping], scene: Mapping, case: Case):
    validate_scene(scene, case)
    require(len(rows) == 900, 'original 900-frame capture missing')
    first = rows[0].get('original_frame')
    t0 = rows[0].get('time_s')
    require(type(first) is int and number(t0),
            'original frame/time missing')
    entry = None
    stopped_before = False
    crossed = False
    for i, row in enumerate(rows):
        frame = first + i
        require(row.get('original_frame') == frame and
                number(row.get('time_s')) and
                abs(row['time_s'] - t0 - i / 20) <= .005,
                'original frame/time join invalid')
        for name in SOURCES:
            require(row.get(name + '_source_sha256') ==
                    scene[name + '_source_sha256'],
                    'original source changed: ' + name)
        require(row.get('driver_id') == scene['driver_id'] and
                row.get('vehicle_id') == scene['vehicle_id'] and
                row.get('marked') is case.marked and
                row.get('stop_sign_governs') is True,
                'original driver/sign/crosswalk context changed')
        require(point(row.get('vehicle_front_xy')) and
                number(row.get('speed_mps')) and
                row['speed_mps'] >= 0,
                'original vehicle front/speed missing')
        in_crosswalk = inside(row['vehicle_front_xy'],
                              scene['near_crosswalk_rect_m'])
        if i == 0:
            require(not in_crosswalk, 'vehicle starts inside near crosswalk')
        if in_crosswalk and entry is None:
            entry = frame
        if entry is None and row['speed_mps'] <= .1:
            stopped_before = True
        if entry is not None and not in_crosswalk:
            crossed = True
    require(entry == scene['crosswalk_entry_frame'] and crossed,
            'original approach/crossing not realized')
    require(stopped_before is case.halt,
            'stop-versus-rolling physical response changed')
    return {'case_id': case.name, 'crosswalk_entry_frame': entry,
            'stopped_before_entry': stopped_before,
            'stop_before_crosswalk_judgment': None}
