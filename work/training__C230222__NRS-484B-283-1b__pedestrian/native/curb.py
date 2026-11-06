"""Source-bound curb departure and conditional stopping margins; no legal verdict."""
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def point(value, name):
    if not isinstance(value, list) or len(value) != 2 or any(
        type(v) not in (int, float) or not math.isfinite(v) for v in value
    ):
        raise ValueError('Invalid original ' + name)
    return tuple(float(v) for v in value)


def measure(samples_path, context_path):
    samples_path, context_path = Path(samples_path), Path(context_path)
    road = context_path.parent / 'road.xodr'
    for path in (samples_path, context_path, road):
        if not path.is_file():
            raise ValueError('Missing required source: ' + path.name)
    context = json.loads(context_path.read_text())
    if context.get('authored_road_sha256') != sha(road):
        raise ValueError('Curb source road hash differs')
    kind = context.get('source_kind')
    if kind not in ('synthetic_scene_request', 'native_observation'):
        raise ValueError('Curb source provenance missing')
    if context.get('frozen_cell') != {'layout': 'road', 'maneuver': 'travel', 'control': 'curb'}:
        raise ValueError('Frozen curb cell differs')
    if context.get('road_width_m') != 7 or context.get('vehicle_conflict_y_m') != 0:
        raise ValueError('Curb geometry differs')
    edge = point(context.get('curb_edge_xy_m'), 'curb edge')
    direction = point(context.get('pedestrian_crossing_forward_xy'), 'crossing direction')
    if abs(math.hypot(*direction) - 1) > .001:
        raise ValueError('Curb crossing direction invalid')
    reaction = context.get('assumed_driver_reaction_s')
    deceleration = context.get('assumed_deceleration_mps2')
    if reaction != [0.8, 1.2] or deceleration != [3.0, 5.0]:
        raise ValueError('Curb conditional stopping assumptions differ')
    if kind == 'native_observation' and (
        not context.get('native_road_sha256') or not context.get('vehicle_source_audit_sha256')
    ):
        raise ValueError('Native curb road or vehicle provenance missing')
    rows = [json.loads(line) for line in samples_path.read_text().splitlines() if line.strip()]
    if len(rows) != 240:
        raise ValueError('Full 240-frame curb source required')
    previous = None
    entry = None
    vehicle_at_arrival = None
    pedestrian_speed_change = None
    for index, row in enumerate(rows):
        frame, time = row.get('native_frame'), row.get('time_s')
        if type(frame) is not int or type(time) not in (int, float) or not math.isfinite(time):
            raise ValueError('Curb frame/time invalid')
        if previous is not None and (frame != previous['native_frame'] + 1 or abs(time - previous['time_s'] - .05) > .002):
            raise ValueError('Curb frame/time order invalid')
        if row.get('pedestrian_id') != context.get('pedestrian_id') or row.get('vehicle_id') != context.get('vehicle_id'):
            raise ValueError('Curb source actor identity differs')
        pose = point(row.get('pedestrian_xy_m'), 'pedestrian pose')
        vehicle = point(row.get('vehicle_xy_m'), 'vehicle pose')
        body = row.get('pedestrian_footprint_xy_m')
        if not isinstance(body, list) or len(body) != 4:
            raise ValueError('Curb pedestrian footprint missing')
        vertices = [point(v, 'pedestrian footprint') for v in body]
        if len(set(vertices)) != 4 or math.dist(pose, (sum(v[0] for v in vertices)/4,
                                                       sum(v[1] for v in vertices)/4)) > .05:
            raise ValueError('Curb pedestrian pose/footprint differs')
        speed = row.get('vehicle_speed_mps')
        ped_speed = row.get('pedestrian_speed_mps')
        if type(speed) not in (int, float) or type(ped_speed) not in (int, float) or speed < 0 or ped_speed < 0:
            raise ValueError('Curb source speed invalid')
        if kind == 'native_observation' and not row.get('original_frame_sha256'):
            raise ValueError('Native curb original frame missing')
        progress = [sum((v[i] - edge[i]) * direction[i] for i in (0, 1)) for v in vertices]
        if entry is None and max(progress) > 0:
            entry = (previous, row)
        if pedestrian_speed_change is None and previous is not None and previous['pedestrian_speed_mps'] == 0 and ped_speed > 0:
            pedestrian_speed_change = (previous, row)
        if vehicle_at_arrival is None and vehicle[1] >= context['vehicle_conflict_y_m']:
            vehicle_at_arrival = row
        previous = row
    if any(x is None for x in (entry, pedestrian_speed_change, vehicle_at_arrival)) or entry[0] is None:
        raise ValueError('Curb departure, entry or vehicle arrival not bracketed')
    entry_row = entry[1]
    distance = context['vehicle_conflict_y_m'] - entry_row['vehicle_xy_m'][1]
    v = float(entry_row['vehicle_speed_mps'])
    if distance <= 0 or v <= 0:
        raise ValueError('Vehicle must approach conflict point at curb entry')
    shortest = v*reaction[0] + v*v/(2*deceleration[1])
    longest = v*reaction[1] + v*v/(2*deceleration[0])
    margin = [distance-longest, distance-shortest]
    relation = ('conditional_yield_possible' if margin[0] > 0 else
                'conditional_yield_impossible' if margin[1] < 0 else
                'conditional_yield_indeterminate')
    arrival = vehicle_at_arrival
    pedestrian_x = arrival['pedestrian_xy_m'][0]
    overlap = abs(pedestrian_x - context['vehicle_lane_center_x_m']) <= context['vehicle_body_half_width_m'] + .12
    return {'format': 'c230222-curb-source-observation-v1',
            'source_sha256': {path.name: sha(path) for path in (samples_path, context_path, road)},
            'source_kind': kind, 'original_frames': len(rows), 'rate_hz': 20,
            'first_curb_departure': {'first_frame': pedestrian_speed_change[1]['native_frame'],
                                     'time_interval_s': [pedestrian_speed_change[0]['time_s'],
                                                         pedestrian_speed_change[1]['time_s']]},
            'first_roadway_entry': {'first_frame': entry_row['native_frame'],
                                     'time_interval_s': [entry[0]['time_s'], entry_row['time_s']]},
            'vehicle_distance_at_entry_m': distance, 'vehicle_speed_at_entry_mps': v,
            'conditional_stopping_distance_range_m': [shortest, longest],
            'conditional_stopping_margin_range_m': margin,
            'conditional_yield_relation': relation,
            'authored_overlap_at_vehicle_arrival': overlap,
            'actual_driver_yield_observed': False, 'driver_capability_measured': False,
            'impossibility_to_yield_proven': False, 'introductory_exceptions_reviewed': False,
            'legal_verdict_claimed': False}
