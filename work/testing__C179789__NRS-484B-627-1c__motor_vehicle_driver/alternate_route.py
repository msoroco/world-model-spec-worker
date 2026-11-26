"""Journey-level alternate-route probes for NRS 484B.627(1)(c).

Route observations and following motion are physical measurements. They cannot
decide 'so slow', 'immediately behind', or whether an alternate is possible.
"""
from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    case_id: str
    route_choice: str
    alternate_declared: bool
    controlled_access: bool = True


CASES = (
    Case('alternate_selected', 'alternate', True),
    Case('alternate_not_selected', 'main', True),
    Case('alternate_restricted', 'main', False),
    Case('ordinary_road_contrast', 'main', True, False),
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(x):
    return type(x) in (int, float) and isfinite(x)


def path(points, name):
    require(isinstance(points, list) and len(points) >= 2 and
            all(isinstance(p, list) and len(p) == 2 and
                all(number(v) for v in p) for p in points),
            name + ' route geometry missing')


def validate_scene(scene: Mapping, case: Case):
    require(case in CASES, 'unknown exact alternate-route case')
    require(scene.get('cell_id') == 'C179789' and scene.get('actor') == 'motor_vehicle_driver',
            'wrong exact cell or actor')
    require(scene.get('controlled_access') is case.controlled_access and
            scene.get('alternate_declared') is case.alternate_declared,
            'case access or alternate declaration differs')
    for field in ('jurisdiction', 'highway_classification', 'controlled_access_classification',
                  'ego_vehicle', 'ego_driver_control', 'main_route', 'alternate_route',
                  'alternate_restrictions', 'journey_destination', 'follower_route',
                  'follower_driver', 'shared_segment', 'following_motion'):
        require(scene.get(field + '_source_sha256'),
                'original journey source missing: ' + field)
    path(scene.get('main_route_xy'), 'main')
    path(scene.get('alternate_route_xy'), 'alternate')
    path(scene.get('follower_route_xy'), 'follower')
    require(scene['main_route_xy'][0] == scene['alternate_route_xy'][0] and
            scene['main_route_xy'][0] == scene['follower_route_xy'][0],
            'routes do not share relevant approach segment')
    require(scene['main_route_xy'] != scene['alternate_route_xy'],
            'alternate does not differ from main route')
    follower_spawn = scene.get('follower_spawn_xy')
    require(isinstance(follower_spawn, list) and len(follower_spawn) == 2 and
            all(number(value) for value in follower_spawn) and
            follower_spawn != scene['main_route_xy'][0] and
            scene.get('follower_spawn_source_sha256'),
            'source-reviewed separated follower spawn missing')
    require(scene.get('alternate_restriction_state') in ('open', 'restricted'),
            'alternate restriction state missing')
    require((scene['alternate_restriction_state'] == 'open') is case.alternate_declared,
            'alternate declaration/restriction conflict')
    return {'controlled_access_declared': case.controlled_access,
            'alternate_declared': case.alternate_declared,
            'possible_route_judgment': None, 'legal_judgment': None}


def construct(adapter, scene: Mapping, case: Case):
    context = validate_scene(scene, case)
    owned = []
    try:
        ego = adapter.spawn_vehicle(scene['main_route_xy'][0], 'ego')
        require(ego is not None, 'ego spawn failed')
        owned.append(ego)
        follower = adapter.spawn_vehicle(scene['follower_spawn_xy'], 'follower')
        require(follower is not None, 'follower spawn failed')
        owned.append(follower)
        adapter.set_route(ego, scene[case.route_choice + '_route_xy'])
        adapter.set_route(follower, scene['follower_route_xy'])
        adapter.set_following_context(follower, ego, scene['shared_segment_source_sha256'])
        return {'case_id': case.case_id, 'owned': tuple(owned),
                'requested_route': case.route_choice, **context}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def measure_original(rows: list[Mapping], scene: Mapping, case: Case):
    validate_scene(scene, case)
    require(len(rows) == 900, 'original 900-frame journey missing')
    first = rows[0].get('original_frame')
    require(type(first) is int, 'original frame identity missing')
    ego_id = follower_id = None
    gaps = []
    ego_speeds = []
    follower_speeds = []
    route_choices = []
    for i, row in enumerate(rows):
        require(row.get('original_frame') == first + i and number(row.get('time_s')) and
                abs(row['time_s'] - rows[0]['time_s'] - i / 20) <= .005,
                'original frame/time join invalid')
        for field in ('source', 'ego_motion', 'follower_motion', 'route_observation',
                      'map_classification', 'journey_context', 'shared_segment'):
            require(row.get(field + '_sha256'), 'original source missing: ' + field)
        require(row.get('shared_segment_source_sha256') ==
                scene['shared_segment_source_sha256'] and
                row.get('controlled_access') is case.controlled_access and
                row.get('alternate_restriction_state') == scene['alternate_restriction_state'],
                'original journey context changed')
        require(row.get('ego_id') and row.get('follower_id'),
                'participant identity missing')
        ego_id = ego_id or row['ego_id']
        follower_id = follower_id or row['follower_id']
        require(row['ego_id'] == ego_id and row['follower_id'] == follower_id and
                ego_id != follower_id, 'participant identity changed')
        for field in ('following_gap_m', 'ego_speed_mps', 'follower_speed_mps',
                      'ego_route_station_m', 'follower_route_station_m'):
            require(number(row.get(field)), 'original motion missing: ' + field)
        require(row['following_gap_m'] > 0, 'follower not behind on shared segment')
        require(row.get('actual_route_choice') in ('main', 'alternate'),
                'actual route observation missing')
        gaps.append(row['following_gap_m'])
        ego_speeds.append(row['ego_speed_mps'])
        follower_speeds.append(row['follower_speed_mps'])
        route_choices.append(row['actual_route_choice'])
    require(route_choices[-1] == case.route_choice,
            'actual terminal route differs from requested case')
    return {'case_id': case.case_id, 'frame_count': 900,
            'minimum_following_gap_m': min(gaps),
            'mean_ego_speed_mps': sum(ego_speeds) / len(ego_speeds),
            'mean_follower_speed_mps': sum(follower_speeds) / len(follower_speeds),
            'terminal_actual_route': route_choices[-1],
            'controlled_access_declared': case.controlled_access,
            'alternate_restriction_state': scene['alternate_restriction_state'],
            'slow_impeding_judgment': None, 'immediately_behind_judgment': None,
            'possible_route_judgment': None, 'legal_judgment': None}
