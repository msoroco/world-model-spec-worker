"""Source-gated pedestrian entry probes under steady red plus green arrow.

The green vehicle turn arrow is not treated as pedestrian permission. Permission
from another device under NRS 484B.283 remains an explicit review judgment.
"""
from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    case_id: str
    movement: str
    other_device_display: str
    walk_speed_target_mps: float | None = None


CASES = (
    Case('enter_no_other_device', 'enter', 'none'),
    Case('wait_no_other_device', 'wait', 'none'),
    Case('enter_walk_display', 'enter', 'walk'),
    Case('wait_walk_display', 'wait', 'walk'),
    Case('other_device_permission-0000', 'enter', 'walk', 0.8),
    Case('other_device_permission-0001', 'enter', 'walk', 1.6),
    Case('other_device_permission-0002', 'enter', 'walk', 1.2),
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(value):
    return type(value) in (int, float) and isfinite(value)


def validate_scene(scene: Mapping, case: Case):
    require(case in CASES, 'unknown exact pedestrian entry case')
    require(scene.get('cell_id') == 'C227824' and scene.get('actor') == 'pedestrian',
            'wrong exact cell or actor')
    require(scene.get('official_vehicle_signal') is True and
            scene.get('steady_red') is True and scene.get('green_turn_arrow') is True,
            'official red/green-arrow combination missing')
    require(scene.get('other_device_display') == case.other_device_display,
            'other-device case display differs')
    require(scene.get('movement') == case.movement,
            'pedestrian entry or wait case movement differs')
    if case.walk_speed_target_mps is not None:
        require(0.5 <= case.walk_speed_target_mps <= 2.0,
                'authored walking-speed request outside tested physical bounds')
        require(scene.get('walk_speed_target_mps') == case.walk_speed_target_mps,
                'exact reviewed walking-speed station differs')
    for field in ('jurisdiction', 'highway_dedication', 'public_vehicle_use',
                  'highway_boundary', 'person_afoot', 'facing_orientation',
                  'official_signal', 'red_arrow_timing', 'other_device_inventory',
                  'other_device_display', 'pedestrian_route'):
        require(scene.get(field + '_source_sha256'),
                'original pedestrian scene source missing: ' + field)
    route = scene.get('pedestrian_route_xy')
    require(isinstance(route, list) and len(route) >= 2 and
            all(isinstance(p, list) and len(p) == 2 and all(number(v) for v in p)
                for p in route), 'pedestrian crossing route missing')
    require(number(scene.get('start_signed_boundary_m')) and
            scene['start_signed_boundary_m'] < 0,
            'pedestrian must initially be outside highway')
    boundary = scene.get('highway_boundary_line_xy')
    require(isinstance(boundary, list) and len(boundary) == 2 and
            all(isinstance(p, list) and len(p) == 2 and all(number(v) for v in p)
                for p in boundary) and boundary[0] != boundary[1] and
            scene.get('inside_sign') in (-1, 1),
            'reviewed oriented highway boundary segment missing')
    a, b = boundary
    dx, dy = b[0] - a[0], b[1] - a[1]
    def signed(point):
        return scene['inside_sign'] * (dx * (point[1] - a[1]) -
                                       dy * (point[0] - a[0]))
    require(signed(route[0]) < 0 and signed(route[-1]) > 0,
            'pedestrian crossing route must span highway boundary')
    return {'other_device_display': case.other_device_display,
            'pedestrian_permission_judgment': None, 'legal_judgment': None}


def construct(adapter, scene: Mapping, case: Case):
    context = validate_scene(scene, case)
    owned = []
    try:
        pedestrian = adapter.spawn_pedestrian(scene['pedestrian_route_xy'][0])
        require(pedestrian is not None, 'pedestrian spawn failed')
        owned.append(pedestrian)
        adapter.set_official_signal(steady_red=True, green_turn_arrow=True)
        adapter.set_other_device(case.other_device_display)
        adapter.set_pedestrian_route(pedestrian, scene['pedestrian_route_xy'],
                                     movement=case.movement)
        return {'case_id': case.case_id, 'owned': tuple(owned), **context}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def measure_original(rows: list[Mapping], scene: Mapping, case: Case):
    validate_scene(scene, case)
    require(len(rows) == 900, 'original 900-frame pedestrian capture missing')
    first = rows[0].get('original_frame')
    require(type(first) is int, 'original frame identity missing')
    identity = None
    entries = []
    previous_inside = False
    for i, row in enumerate(rows):
        require(row.get('original_frame') == first + i and number(row.get('time_s')) and
                abs(row['time_s'] - rows[0]['time_s'] - i / 20) <= .005,
                'original frame/time join invalid')
        for field in ('source', 'pedestrian_body', 'pedestrian_motion',
                      'highway_boundary', 'signal_display', 'other_device_display',
                      'facing_orientation'):
            require(row.get(field + '_sha256'), 'original source missing: ' + field)
        require(row.get('highway_boundary_source_sha256') ==
                scene['highway_boundary_source_sha256'] and
                row.get('other_device_display') == case.other_device_display,
                'original boundary/device context changed')
        linked_sources = {'pedestrian_body_sha256': 'person_afoot_source_sha256',
                          'pedestrian_motion_sha256': 'pedestrian_route_source_sha256',
                          'highway_boundary_sha256': 'highway_boundary_source_sha256',
                          'signal_display_sha256': 'red_arrow_timing_source_sha256',
                          'other_device_display_sha256': 'other_device_display_source_sha256',
                          'facing_orientation_sha256': 'facing_orientation_source_sha256'}
        require(all(row[field] == scene[source] for field, source in linked_sources.items()),
                'original signal/body source binding differs')
        require(row.get('pedestrian_id'), 'pedestrian identity missing')
        identity = identity or row['pedestrian_id']
        require(row['pedestrian_id'] == identity, 'pedestrian identity changed')
        require(row.get('person_afoot') is True and row.get('facing_signal') is True and
                row.get('official_steady_red') is True and
                row.get('official_green_turn_arrow') is True,
                'original person/signal condition changed')
        require(number(row.get('body_nearest_signed_boundary_m')),
                'original body-to-highway boundary missing')
        inside = row['body_nearest_signed_boundary_m'] >= 0
        if inside and not previous_inside:
            entries.append(i)
        previous_inside = inside
    require(rows[0]['body_nearest_signed_boundary_m'] < 0,
            'pedestrian was not initially outside')
    if case.movement == 'enter':
        require(len(entries) == 1 and entries[0] > 0,
                'single actual highway entry absent')
        entry_frame = first + entries[0]
    else:
        require(not entries, 'waiting case entered highway')
        entry_frame = None
    speed_observation = None
    if case.walk_speed_target_mps is not None:
        samples = [row.get('pedestrian_speed_mps') for row in rows[120:241]]
        require(len(samples) == 121 and all(number(value) and value >= 0 for value in samples),
                'original pedestrian speed readback missing from steady approach')
        speed_observation = {'value': sum(samples) / len(samples), 'unit': 'm/s',
                             'method': 'original 20 Hz pedestrian body velocity readback after departure, retaining the complete raw stream',
                             'time_window': 'original seconds 6 through 12 after departure, excluding startup transient',
                             'statistic': 'mean', 'sample_window_s': [6.0, 12.0],
                             'source_kind': 'original_native_frames'}
    return {'case_id': case.case_id, 'frame_count': 900,
            'first_original_entry_frame': entry_frame,
            'original_pedestrian_speed_mps': speed_observation,
            'other_device_display_observed': case.other_device_display,
            'vehicle_arrow_is_pedestrian_permission': False,
            'pedestrian_permission_judgment': None, 'legal_judgment': None}
