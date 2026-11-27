"""Source-gated inoperative-signal stop/yield probes for NRS 484B.250(4)."""
from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    name: str
    stop_basis: str
    other_state: str
    ego_policy: str


CASES = (
    Case('line_prior_stop_yield', 'stop_line', 'prior_stop', 'yield'),
    Case('line_occupied_yield', 'stop_line', 'inside', 'yield'),
    Case('line_prior_stop_no_yield', 'stop_line', 'prior_stop', 'enter'),
    Case('line_clear_enter', 'stop_line', 'clear', 'enter'),
    Case('crosswalk_prior_stop_yield', 'crosswalk', 'prior_stop', 'yield'),
    Case('viewpoint_prior_stop_yield', 'viewpoint', 'prior_stop', 'yield'),
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(value):
    return type(value) in (int, float) and isfinite(value)


def validate_scene(scene: Mapping, case: Case):
    require(case in CASES, 'unknown exact intersection case')
    require(scene.get('cell_id') == 'C24811' and
            scene.get('actor') == 'motor_vehicle_driver' and
            scene.get('driver_controls_vehicle') is True and
            scene.get('ordinary_motor_vehicle') is True,
            'driver/vehicle context missing')
    require(scene.get('stop_basis') == case.stop_basis and
            scene.get('other_state') == case.other_state and
            scene.get('ego_policy') == case.ego_policy,
            'case variables changed')
    require(scene.get('signal_installed') is True and
            scene.get('vehicular_heads_uncovered') is True and
            scene.get('official_device') is True and
            scene.get('governs_entrance') is True and
            scene.get('all_heads_wholly_inoperative') is True,
            'installed uncovered wholly inoperative governing signal missing')
    for field in ('jurisdiction', 'intersection_bounds', 'entrances',
                  'official_signal', 'signal_governance', 'signal_state',
                  'stop_line', 'crosswalk', 'viewpoint', 'occluder',
                  'ego_route', 'other_route', 'driver_control'):
        require(scene.get(field + '_source_sha256'),
                'original context missing: ' + field)
    require(number(scene.get('stop_station_m')) and
            number(scene.get('entry_station_m')) and
            scene['stop_station_m'] < scene['entry_station_m'],
            'stop/entry station geometry missing')
    require(scene.get('entrance_ids') and
            len(scene['entrance_ids']) >= 2,
            'all entrance inventory missing')
    if case.stop_basis == 'stop_line':
        require(scene.get('marked_stop_line') is True,
                'marked stop line missing')
    elif case.stop_basis == 'crosswalk':
        require(scene.get('marked_stop_line') is False and
                scene.get('near_crosswalk') is True,
                'crosswalk fallback predicates missing')
    else:
        require(scene.get('marked_stop_line') is False and
                scene.get('near_crosswalk') is False and
                scene.get('approach_viewpoint') is True,
                'viewpoint fallback predicates missing')
    if case.other_state != 'clear':
        require(scene.get('other_vehicle_id'), 'distinct other vehicle missing')
    require(scene.get('occluder_geometry') and
            scene.get('occluder_governs_approach') is True,
            'actual sight obstruction geometry missing')
    for field in ('ego_route_xy', 'other_route_xy'):
        route = scene.get(field)
        require(isinstance(route, list) and len(route) >= 2 and
                all(isinstance(p, list) and len(p) == 2 and
                    all(number(v) for v in p) for p in route),
                field + ' missing')
    return {'case_id': case.name, 'caution_judgment': None}


def construct(adapter, scene: Mapping, case: Case):
    context = validate_scene(scene, case)
    owned = []
    try:
        adapter.set_signal_heads_inoperative(scene['entrance_ids'])
        adapter.place_occluder(scene['occluder_geometry'])
        ego = adapter.spawn_vehicle(scene['ego_route_xy'][0])
        require(ego is not None, 'ego spawn failed')
        owned.append(ego)
        other = adapter.spawn_vehicle(scene['other_route_xy'][0])
        require(other is not None, 'other spawn failed')
        owned.append(other)
        adapter.set_ego_stop_and_entry(ego, scene['ego_route_xy'],
                                       scene['stop_station_m'], case.ego_policy)
        adapter.set_other_history(other, scene['other_route_xy'],
                                  case.other_state)
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
    ego_id = other_id = None
    stop_frame = entry_frame = None
    other_prior_stop = False
    other_inside_at_entry = False
    for i, row in enumerate(rows):
        require(row.get('original_frame') == first + i and
                number(row.get('time_s')) and
                abs(row['time_s'] - rows[0]['time_s'] - i / 20) <= .005,
                'original frame/time join invalid')
        for field in ('frame', 'ego_motion', 'other_motion',
                      'intersection_bounds', 'signal_state', 'stop_geometry',
                      'occluder', 'driver_viewpoint'):
            require(row.get(field + '_source_sha256'),
                    'original measurement source missing: ' + field)
        require(row.get('signal_state_source_sha256') ==
                scene['signal_state_source_sha256'] and
                row.get('all_heads_wholly_inoperative') is True,
                'original signal state changed')
        require(row.get('ego_id') and row.get('other_id'),
                'distinct vehicle identity missing')
        ego_id = ego_id or row['ego_id'];other_id = other_id or row['other_id']
        require(row['ego_id'] == ego_id and row['other_id'] == other_id and
                ego_id != other_id, 'vehicle identity changed')
        require(number(row.get('ego_station_m')) and
                number(row.get('ego_speed_mps')) and
                row['ego_speed_mps'] >= 0 and
                type(row.get('other_inside_intersection')) is bool and
                type(row.get('other_stopped')) is bool,
                'original synchronized vehicle history missing')
        if stop_frame is None and row['ego_speed_mps'] <= .01 and \
                row['ego_station_m'] <= scene['stop_station_m']:
            stop_frame = first + i
        if entry_frame is None and row['ego_station_m'] >= scene['entry_station_m']:
            entry_frame = first + i
            other_inside_at_entry = row['other_inside_intersection']
        if row['other_stopped'] and entry_frame is None:
            other_prior_stop = True
    require(stop_frame is not None and entry_frame is not None and
            stop_frame < entry_frame, 'complete pre-entry stop missing')
    if case.other_state == 'prior_stop':
        require(other_prior_stop, 'other prior stop history missing')
    if case.other_state == 'inside':
        require(other_inside_at_entry, 'other intersection occupancy missing')
    return {'case_id': case.name, 'frame_count': 900,
            'stop_frame': stop_frame, 'entry_frame': entry_frame,
            'other_prior_stop': other_prior_stop,
            'other_inside_at_entry': other_inside_at_entry,
            'yield_judgment': None, 'caution_judgment': None}
