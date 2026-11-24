"""Source-gated non-tour-bus loading and front-wheel/curb probes."""
from dataclasses import dataclass
from math import hypot, isfinite
from typing import Mapping


EIGHTEEN_INCH_M = 0.4572


@dataclass(frozen=True)
class Case:
    name: str
    location: str
    activity: str
    target_distance_m: float


CASES = (
    Case('bus_stop_below', 'bus_stop', 'passenger_loading', .4472),
    Case('bus_stop_at', 'bus_stop', 'passenger_loading', .4572),
    Case('bus_stop_above', 'bus_stop', 'passenger_loading', .4672),
    Case('bus_stand_baggage', 'bus_stand', 'baggage_loading', .4472),
    Case('passenger_zone_unload', 'passenger_zone', 'passenger_unloading', .4472),
    Case('origin_point_load', 'origin_point', 'passenger_loading', .4472),
    Case('destination_point_unload', 'destination_point', 'passenger_unloading', .4472),
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(value):
    return type(value) in (int, float) and isfinite(value)


def point(value):
    return isinstance(value, (list, tuple)) and len(value) == 2 and all(number(x) for x in value)


def point_segment_distance(p, a, b):
    require(point(p) and point(a) and point(b), 'wheel/curb geometry missing')
    vx, vy = b[0]-a[0], b[1]-a[1]
    denominator = vx*vx + vy*vy
    require(denominator > 0, 'curb segment degenerate')
    t = max(0, min(1, ((p[0]-a[0])*vx+(p[1]-a[1])*vy)/denominator))
    return hypot(p[0]-a[0]-t*vx, p[1]-a[1]-t*vy)


def validate_scene(scene: Mapping, case: Case):
    require(case in CASES, 'unknown exact bus case')
    require(scene.get('cell_id') == 'C149470' and
            scene.get('actor') == 'bus_driver' and
            scene.get('operator_controls_bus') is True and
            scene.get('bus_qualifies') is True and
            scene.get('tour_bus') is False and
            scene.get('public_street') is True,
            'covered non-tour bus/operator/public street missing')
    require(scene.get('location_kind') == case.location and
            scene.get('activity') == case.activity and
            scene.get('target_distance_m') == case.target_distance_m,
            'case variables changed')
    require(scene.get('location_designated') is True and
            scene.get('location_governs_bus') is True,
            'qualifying loading location missing')
    for field in ('jurisdiction', 'bus_class', 'tour_exclusion',
                  'operator', 'location_boundary', 'location_designation',
                  'signs', 'curb_geometry', 'right_front_wheel',
                  'bus_route', 'loading_activity', 'traffic_route'):
        require(scene.get(field + '_source_sha256'),
                'original context missing: ' + field)
    curb = scene.get('curb_segment_xy')
    require(isinstance(curb, list) and len(curb) == 2 and
            all(point(x) for x in curb), 'curb segment missing')
    point_segment_distance([0, 0], *curb)
    for field in ('bus_route_xy', 'traffic_route_xy'):
        route = scene.get(field)
        require(isinstance(route, list) and len(route) >= 2 and
                all(point(x) for x in route), field + ' missing')
    require(scene.get('loading_actor_ids'), 'actual passenger/baggage actor missing')
    return {'case_id': case.name, 'parallel_judgment': None,
            'unduly_impede_judgment': None}


def construct(adapter, scene: Mapping, case: Case):
    context = validate_scene(scene, case)
    owned = []
    try:
        adapter.mark_loading_location(case.location,
                                      scene['location_boundary_xy'])
        bus = adapter.spawn_bus(scene['bus_route_xy'][0])
        require(bus is not None, 'bus spawn failed')
        owned.append(bus)
        traffic = adapter.spawn_traffic(scene['traffic_route_xy'][0])
        require(traffic is not None, 'traffic spawn failed')
        owned.append(traffic)
        adapter.set_bus_entry_and_halt(bus, scene['bus_route_xy'],
                                       case.target_distance_m)
        adapter.set_loading_activity(bus, case.activity,
                                     scene['loading_actor_ids'])
        adapter.set_traffic_route(traffic, scene['traffic_route_xy'])
        return {'owned': tuple(owned), **context}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def measure_original(rows: list[Mapping], scene: Mapping, case: Case):
    validate_scene(scene, case)
    require(len(rows) == 900, 'original 900-frame capture missing')
    first = rows[0].get('original_frame')
    require(type(first) is int and number(rows[0].get('time_s')),
            'original frame/time identity missing')
    bus_id = traffic_id = None
    stopped_distances, uncertainties, angles, traffic_speeds = [], [], [], []
    activity_seen = False
    for i, row in enumerate(rows):
        require(row.get('original_frame') == first + i and
                number(row.get('time_s')) and
                abs(row['time_s'] - rows[0]['time_s'] - i/20) <= .005,
                'original frame/time join invalid')
        for field in ('frame', 'bus_motion', 'traffic_motion',
                      'right_front_wheel', 'curb_geometry',
                      'location_designation', 'loading_activity'):
            require(row.get(field + '_source_sha256'),
                    'original measurement source missing: ' + field)
        require(row.get('curb_geometry_source_sha256') ==
                scene['curb_geometry_source_sha256'] and
                row.get('activity') == case.activity,
                'original curb/activity context changed')
        require(row.get('bus_id') and row.get('traffic_id'),
                'participant identity missing')
        bus_id = bus_id or row['bus_id'];traffic_id = traffic_id or row['traffic_id']
        require(row['bus_id'] == bus_id and row['traffic_id'] == traffic_id and
                bus_id != traffic_id, 'participant identity changed')
        for field in ('bus_speed_mps', 'traffic_speed_mps',
                      'wheel_position_uncertainty_m', 'bus_curb_angle_deg'):
            require(number(row.get(field)) and row[field] >= 0,
                    'original physical stream missing: ' + field)
        require(point(row.get('right_front_wheel_xy')) and
                type(row.get('loading_active')) is bool,
                'original wheel/activity state missing')
        if row['bus_speed_mps'] <= .01:
            stopped_distances.append(point_segment_distance(
                row['right_front_wheel_xy'], *scene['curb_segment_xy']))
            uncertainties.append(row['wheel_position_uncertainty_m'])
            angles.append(row['bus_curb_angle_deg'])
            traffic_speeds.append(row['traffic_speed_mps'])
            activity_seen |= row['loading_active']
    require(len(stopped_distances) >= 20 and activity_seen,
            'stopped loading interval missing')
    return {'case_id': case.name, 'stopped_frame_count': len(stopped_distances),
            'minimum_right_front_wheel_curb_m': min(stopped_distances),
            'maximum_right_front_wheel_curb_m': max(stopped_distances),
            'maximum_wheel_position_uncertainty_m': max(uncertainties),
            'maximum_bus_curb_angle_deg': max(angles),
            'minimum_other_traffic_speed_mps': min(traffic_speeds),
            'statutory_limit_m': EIGHTEEN_INCH_M,
            'parallel_judgment': None, 'unduly_impede_judgment': None}
