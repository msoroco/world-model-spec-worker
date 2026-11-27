"""Original-source-gated roadside signal approach construction and measurements.

The 30-foot value is an exact statutory quantity (9.144 m). This module retains
raw body and signal geometry; it does not choose a legal distance datum.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path


ASSIGNMENT = 'testing__C229472__NRS-484B-450-1g__motor_vehicle_driver'
THIRTY_FEET_M = 9.144


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def point(value):
    require(isinstance(value, list) and len(value) == 2 and
            all(type(x) in (int, float) and math.isfinite(x) for x in value),
            'finite xy point required')
    return tuple(map(float, value))


@dataclass(frozen=True)
class Case:
    name: str
    metres: float
    relation: str
    activity: str
    exception: str
    signal_status: str


CASES = tuple(Case(*row) for row in (
    ('approach_below_30ft_park', 9.000, 'upstream', 'park', 'none', 'official'),
    ('approach_at_30ft_park', THIRTY_FEET_M, 'upstream', 'park', 'none', 'official'),
    ('approach_above_30ft_park', 9.300, 'upstream', 'park', 'none', 'official'),
    ('past_signal_park', 2.000, 'downstream', 'park', 'none', 'official'),
    ('approach_unofficial_light_park', 9.000, 'upstream', 'park', 'none', 'unofficial'),
    ('approach_below_30ft_stop', 9.000, 'upstream', 'stop', 'none', 'official'),
    ('approach_below_30ft_stand', 9.000, 'upstream', 'stand', 'none', 'official'),
    ('approach_below_30ft_conflict_stop', 9.000, 'upstream', 'stop', 'traffic_conflict', 'official'),
    ('approach_below_30ft_law_park', 9.000, 'upstream', 'park', 'law_direction', 'official'),
    ('approach_below_30ft_officer_park', 9.000, 'upstream', 'park', 'officer_direction', 'official'),
    ('approach_below_30ft_device_park', 9.000, 'upstream', 'park', 'device_direction', 'official'),
))
CASE_BY_ID = {ASSIGNMENT + '__' + c.name: c for c in CASES}


def unit_route(scene):
    start, end = point(scene['incoming_route_xy'][0]), point(scene['incoming_route_xy'][-1])
    vector = (end[0] - start[0], end[1] - start[1])
    length = math.hypot(*vector)
    require(length >= 25.0, 'incoming route too short for signal approach')
    return start, (vector[0] / length, vector[1] / length)


def station(point_xy, origin, heading):
    xy = point(point_xy)
    return (xy[0] - origin[0]) * heading[0] + (xy[1] - origin[1]) * heading[1]


def signed_body_station(vertices, origin, heading, signal_station):
    values = [station([v[0], v[1]], origin, heading) for v in vertices]
    require(len(values) >= 4, 'original body vertices missing')
    return {'body_front_approach_gap_m': signal_station - max(values),
            'body_rear_approach_gap_m': signal_station - min(values),
            'body_station_range_m': [min(values), max(values)]}


def validate_scene(scene, case):
    require(isinstance(scene, dict), 'reviewed signal scene missing')
    origin, heading = unit_route(scene)
    signal = point(scene['signal_xy'])
    signal_station = station(list(signal), origin, heading)
    lateral = (signal[0] - origin[0]) * (-heading[1]) + (signal[1] - origin[1]) * heading[0]
    require(1.5 <= abs(lateral) <= 12.0, 'signal is not at reviewed highway side')
    require(scene.get('highway_public_use_reviewed') is True,
            'public highway status requires original review')
    require(scene.get('signal_governed_route_reviewed') is True,
            'signal governed movement requires original review')
    require(scene.get('signal_placement_authority_reviewed') is True,
            'signal placement authority requires original review')
    require(scene.get('signal_stop_proceed_function_reviewed') is True,
            'signal stop/proceed function requires original review')
    require(scene.get('signal_official_status') == case.signal_status,
            'reviewed signal status differs from exact case')
    require(scene.get('signal_id') and scene.get('signal_actor_id'),
            'original signal identity missing')
    target = point(scene['halt_target_xy'])
    target_station = station(list(target), origin, heading)
    signed = signal_station - target_station
    front_offset = scene.get('body_front_offset_m')
    require(type(front_offset) in (int, float) and 1.0 <= front_offset <= 5.0,
            'reviewed vehicle front offset missing')
    require((signed > 0 if case.relation == 'upstream' else signed < 0),
            'target is not on exact approach side of signal')
    expected = case.metres + front_offset
    require(abs(abs(signed) - expected) <= 0.2,
            'reviewed body-front target differs from exact case')
    require(scene.get('halt_activity') == case.activity and
            scene.get('exception_context') == case.exception,
            'activity or exception changed')
    require(scene.get('traffic_actor_blueprint', '').startswith('vehicle.') and
            scene.get('ego_blueprint', '').startswith('vehicle.'),
            'motor vehicle blueprint absent')
    require(isinstance(scene.get('traffic_route_xy'), list) and
            len(scene['traffic_route_xy']) >= 2,
            'original passing traffic route missing')
    if case.exception == 'traffic_conflict':
        require(scene.get('conflict_actor_route_xy') and
                scene.get('conflict_necessity_source'),
                'traffic conflict actor and necessity source required')
    elif case.exception != 'none':
        require(scene.get('direction_document_source') and
                scene.get('direction_document_type') == case.exception,
                'exception direction document missing or mismatched')
    return {'route_origin_xy': list(origin), 'heading_xy': list(heading),
            'signal_station_m': signal_station,
            'signal_lateral_offset_m': lateral,
            'target_signed_approach_station_m': signed,
            'reviewed_body_front_offset_m': float(front_offset),
            'statutory_quantity_m': THIRTY_FEET_M,
            'legal_measurement_datum': 'unresolved'}


def reviewed_packet(packet_path, case_id):
    path = Path(packet_path).resolve()
    require(path.is_file() and not path.is_symlink(), 'original reviewed signal packet missing')
    packet = json.loads(path.read_text(encoding='utf-8'))
    case = CASE_BY_ID.get(case_id)
    require(case is not None and packet.get('case_id') == case_id,
            'reviewed signal packet exact case differs')
    require(packet.get('review_status') == 'reviewed_original_source' and
            packet.get('diagnostic_fixture') is False and
            packet.get('reviewer') and packet.get('review_method'),
            'original independent signal review missing')
    refs = packet.get('sources')
    require(isinstance(refs, dict) and
            {'map', 'highway', 'signal', 'authority', 'traffic'} <= set(refs),
            'reviewed source inventory incomplete')
    for name, ref in refs.items():
        require(isinstance(ref, dict) and ref.get('path') and ref.get('sha256'),
                'reviewed source identity missing: ' + name)
        target = (path.parent / ref['path']).resolve()
        require(target.is_relative_to(path.parent) and target.is_file() and
                not target.is_symlink() and sha(target) == ref['sha256'],
                'reviewed source changed: ' + name)
    map_record = json.loads((path.parent / refs['map']['path']).read_text())
    require(packet.get('map_id') == map_record.get('map_id') and
            len(map_record.get('opendrive_sha256', '')) == 64,
            'reviewed CARLA map identity missing')
    scene = packet.get('scene')
    geometry = validate_scene(scene, case)
    for source_name, field in (('highway', 'highway_source_sha256'),
                               ('signal', 'signal_source_sha256'),
                               ('authority', 'authority_source_sha256'),
                               ('traffic', 'traffic_source_sha256')):
        require(scene.get(field) == refs[source_name]['sha256'],
                'reviewed scene does not bind original ' + source_name)
    return packet, case, geometry


def measure_original(rows, scene, case):
    require(len(rows) == 900, '45 seconds at 20 Hz of original samples required')
    frames = [row['original_frame'] for row in rows]
    require(len(set(frames)) == 900 and frames == list(range(frames[0], frames[0] + 900)),
            'original frame sequence incomplete')
    origin, heading = unit_route(scene)
    signal_station = station(scene['signal_xy'], origin, heading)
    gaps = []
    for row in rows:
        require(row.get('original_source') is True and
                row.get('signal_id') == scene['signal_id'] and
                row.get('activity') == case.activity and
                row.get('exception') == case.exception and
                row.get('signal_indication') is not None,
                'original signal/activity source missing')
        gaps.append(signed_body_station(row['body_vertices_xy_m'], origin, heading,
                                        signal_station))
    return {'case_id': ASSIGNMENT + '__' + case.name,
            'frames': 900, 'rate_hz': 20, 'signal_id': scene['signal_id'],
            'signal_xy': scene['signal_xy'],
            'signal_source_sha256': scene['signal_source_sha256'],
            'body_gap_history_m': gaps,
            'terminal_body_front_approach_gap_m': gaps[-1]['body_front_approach_gap_m'],
            'terminal_body_rear_approach_gap_m': gaps[-1]['body_rear_approach_gap_m'],
            'intended_quantity_m': THIRTY_FEET_M,
            'legal_measurement_datum': 'unresolved',
            'physical_acceptance_claimed': False,
            'legal_verdict': 'unresolved'}
