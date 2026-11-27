"""Source-gated non-through intersection stop probes for 484B.257(2).

This records physical response and participant histories, not legal hazard or
right-of-way judgments. Existing accepted metadata is not original capture.
"""
from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    case_id: str
    through_phase: str
    approach_policy: str
    traffic_station_m: float


CASES = (
    Case('occupied_response', 'within', 'stop', 0),
    Case('approaching_near_response', 'approaching', 'stop', 8),
    Case('approaching_far_response', 'approaching', 'stop', 35),
    Case('approaching_near_uninterrupted', 'approaching', 'uninterrupted', 8),
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(x):
    return type(x) in (int, float) and isfinite(x)


def validate_scene(scene: Mapping, case: Case):
    require(case in CASES, 'unknown exact non-through stop case')
    require(scene.get('cell_id') == 'C158190' and scene.get('actor') == 'motor_vehicle_driver',
            'wrong exact cell or actor')
    require(scene.get('ego_stop_sign') is True and scene.get('non_through_highway') is True and
            scene.get('officer_controls') is False and scene.get('signal_controls') is False,
            'governing sign/non-through/exception context missing')
    for key in ('jurisdiction', 'intersection_geometry', 'all_entrance_controls',
                'ego_stop_sign', 'non_through_classification', 'stop_reference',
                'sightlines', 'through_vehicle_exemption', 'officer_control',
                'signal_control', 'ego_vehicle'):
        require(scene.get(key + '_source_sha256'), 'original scene source missing: ' + key)
    require(scene.get('other_vehicle_obligated_to_stop_or_yield') is False,
            'other participant obligation not established')
    route = scene.get('ego_route_xy')
    require(isinstance(route, list) and len(route) >= 2 and
            all(isinstance(p, list) and len(p) == 2 and all(number(v) for v in p)
                for p in route), 'connected ego route missing')
    require(number(scene.get('stop_reference_station_m')) and
            number(scene.get('intersection_entry_station_m')) and
            scene['stop_reference_station_m'] < scene['intersection_entry_station_m'],
            'upstream stopping reference missing')
    require(isinstance(scene.get('through_spawn_xy'), list) and
            len(scene['through_spawn_xy']) == 2 and
            all(number(v) for v in scene['through_spawn_xy']),
            'through vehicle spawn missing')
    return {'reference_station_m': scene['stop_reference_station_m'],
            'other_not_obligated': True, 'legal_judgment': None}


def construct(adapter, scene: Mapping, case: Case):
    context = validate_scene(scene, case)
    owned = []
    try:
        ego = adapter.spawn_vehicle(scene['ego_route_xy'][0], 'ego')
        require(ego is not None, 'ego spawn failed')
        owned.append(ego)
        other = adapter.spawn_vehicle(scene['through_spawn_xy'], 'other')
        require(other is not None, 'other spawn failed')
        owned.append(other)
        adapter.set_stop_approach(ego, scene['ego_route_xy'],
                                   scene['stop_reference_station_m'], case.approach_policy)
        adapter.set_other_phase(other, case.through_phase, case.traffic_station_m)
        return {'case_id': case.case_id, 'owned': tuple(owned), **context}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def measure_original(rows: list[Mapping], scene: Mapping, case: Case):
    validate_scene(scene, case)
    require(len(rows) == 900, 'original 900-frame capture missing')
    first = rows[0].get('original_frame')
    require(type(first) is int, 'original frame identity missing')
    ego_id = other_id = None
    speeds = []
    entries = []
    other_stations = []
    for i, row in enumerate(rows):
        require(row.get('original_frame') == first + i and number(row.get('time_s')) and
                abs(row['time_s'] - rows[0]['time_s'] - i / 20) <= .005,
                'original frame/time join invalid')
        for key in ('source', 'ego_motion', 'other_motion', 'body_geometry',
                    'controls', 'sightlines', 'entrance_controls'):
            require(row.get(key + '_sha256'), 'original source missing: ' + key)
        require(row.get('intersection_geometry_source_sha256') ==
                scene['intersection_geometry_source_sha256'] and
                row.get('all_entrance_controls_source_sha256') ==
                scene['all_entrance_controls_source_sha256'],
                'original intersection source changed')
        require(row.get('ego_id') and row.get('other_id'), 'participant identity missing')
        ego_id = ego_id or row['ego_id']
        other_id = other_id or row['other_id']
        require(row['ego_id'] == ego_id and row['other_id'] == other_id and
                ego_id != other_id, 'participant identity changed')
        require(row.get('other_obligated_to_stop_or_yield') is False and
                row.get('officer_controls') is False and row.get('signal_controls') is False,
                'original governing context changed')
        for key in ('ego_speed_mps', 'ego_leading_station_m',
                    'other_center_station_m', 'other_min_vertex_station_m'):
            require(number(row.get(key)), 'original numeric stream missing: ' + key)
        require(row.get('other_phase') in ('approaching', 'within', 'cleared') and
                type(row.get('ego_across_or_within')) is bool,
                'original participant phase/crossing missing')
        speeds.append(row['ego_speed_mps'])
        other_stations.append(row['other_center_station_m'])
        if row['ego_leading_station_m'] >= scene['intersection_entry_station_m']:
            entries.append(i)
    require(entries and entries[0] > 0, 'intersection entry absent')
    entry = entries[0]
    require(rows[entry]['other_phase'] == case.through_phase,
            'requested other phase not realized at physical entry')
    require(rows[entry - 1]['ego_leading_station_m'] <
            scene['intersection_entry_station_m'], 'first leading-body entry invalid')
    require(any(r['ego_across_or_within'] for r in rows[entry:]),
            'across-or-within history absent')
    minimum = min(speeds[:entry + 1])
    if case.approach_policy == 'stop':
        require(minimum <= 0.1 and minimum < max(speeds[:entry + 1]), 'original pre-entry full stop absent')
    return {'case_id': case.case_id, 'frame_count': 900,
            'first_original_entry_frame': first + entry,
            'minimum_original_approach_speed_mps': minimum,
            'other_center_station_at_entry_m': other_stations[entry],
            'other_min_vertex_station_at_entry_m': rows[entry]['other_min_vertex_station_m'],
            'other_phase': case.through_phase, 'immediate_hazard_judgment': None,
            'cautious_proceeding_judgment': None, 'right_of_way_judgment': None,
            'legal_judgment': None}


def measure_frozen_windows(rows: list[Mapping], scene: Mapping, case: Case):
    """Compute exact frozen training observables from original physical windows.

    Values are descriptive coverage measurements, never hazard or caution cutoffs.
    The source rows must already have passed measure_original's frame/source join.
    """
    primary = measure_original(rows, scene, case)
    passage = [i for i, row in enumerate(rows)
               if row['ego_leading_station_m'] >= scene['stop_reference_station_m']]
    require(passage and passage[0] > 0 and
            rows[passage[0] - 1]['ego_leading_station_m'] < scene['stop_reference_station_m'],
            'first original stop-reference passage missing')
    peaks = [i for i in range(passage[0] + 1)
             if rows[i]['ego_speed_mps'] == max(row['ego_speed_mps'] for row in rows[:passage[0] + 1])]
    peak = peaks[-1]
    require(peak < passage[0], 'approach peak to reference interval missing')
    overlap = [i for i, row in enumerate(rows)
               if row.get('ego_full_body_overlap') is True]
    require(overlap and overlap[0] > 0 and overlap[-1] < len(rows) - 1 and
            all(rows[i].get('ego_full_body_overlap') is True
                for i in range(overlap[0], overlap[-1] + 1)),
            'original full-body intersection overlap/clearance absent')
    clear = overlap[-1] + 1
    require(rows[clear].get('ego_full_body_cleared') is True and
            all(type(row.get('ego_full_body_overlap')) is bool and
                type(row.get('ego_full_body_cleared')) is bool for row in rows),
            'original body containment history incomplete')
    reference = [i for i, row in enumerate(rows) if row.get('traffic_reference_event') is True]
    require(len(reference) == 1 and type(rows[reference[0]].get('other_center_station_m'))
            in (int, float), 'unique original traffic reference event missing')
    i = reference[0]
    primary['frozen_observables'] = {
        'counterpart_center_station_first_m': rows[i]['other_center_station_m'],
        'ego_speed_min_peak_to_stop_reference_mps': min(
            row['ego_speed_mps'] for row in rows[peak:passage[0] + 1]),
        'ego_speed_mean_full_body_overlap_to_clear_mps': sum(
            row['ego_speed_mps'] for row in rows[overlap[0]:clear + 1]) / (clear - overlap[0] + 1),
    }
    primary['frozen_windows'] = {
        'traffic_reference_frame': rows[i]['original_frame'],
        'approach_peak_frame': rows[peak]['original_frame'],
        'stop_reference_passage_frame': rows[passage[0]]['original_frame'],
        'first_overlap_frame': rows[overlap[0]]['original_frame'],
        'first_clear_frame': rows[clear]['original_frame'],
    }
    return primary
