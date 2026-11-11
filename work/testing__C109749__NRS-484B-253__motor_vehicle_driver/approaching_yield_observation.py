"""Describe a subject yield while an opposing body is approaching the junction.

The observed distance and order do not define the legal phrase immediate hazard.
"""
import json
import math
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon

from measurements import analyze


def _body(row, role):
    return MultiPoint(row[role]['body_vertices_xy_m']).convex_hull


def observe(attempt):
    attempt = Path(attempt)
    report = analyze(attempt)
    geometry = json.loads((attempt / 'intersection_geometry.json').read_text())
    polygon = Polygon(geometry['intersection_polygon_xy_m'])
    rows = [json.loads(line) for line in
            (attempt / 'interaction_history.jsonl').read_text().splitlines() if line]
    if polygon.is_empty or not polygon.is_valid or polygon.intersects(_body(rows[0], 'oncoming')):
        raise ValueError('Initial opposing complete body must start outside sourced junction')
    direction = geometry['oncoming_direction_xy']
    conflict = geometry['conflict_point_xy_m']
    approaching = []
    for row in rows:
        opponent = row['oncoming']
        remaining = sum((conflict[i]-opponent['position_xy_m'][i])*direction[i] for i in (0, 1))
        closing = sum(opponent['velocity_xy_mps'][i]*direction[i] for i in (0, 1))
        if (remaining > 0 and closing > 0.5 and not polygon.intersects(_body(row, 'oncoming'))
                and polygon.intersects(_body(row, 'ego'))
                and math.hypot(*row['ego']['velocity_xy_mps']) < 0.1
                and row['ego_left_indicator']):
            approaching.append({'frame': row['frame'], 'distance_to_conflict_m': remaining,
                                 'closing_speed_mps': closing,
                                 'kinematic_time_to_conflict_s': remaining/closing})
    entry = report['oncoming_first_in_intersection_frame']
    clearance = report['initial_oncoming_clearance_frame']
    turn = report['ego_turn_start_frame']
    if not approaching or entry is None or clearance is None or turn is None:
        raise ValueError('Sourced approaching-yield sequence incomplete')
    if not max(item['frame'] for item in approaching) < entry < clearance < turn:
        raise ValueError('Approaching yield must precede opposing entry, clearance and turn')
    return {'format': 'c109749-approaching-yield-observation',
            'initial_frame': rows[0]['frame'], 'approaching_yield_samples': approaching,
            'opposing_entry_frame': entry, 'opposing_clearance_frame': clearance,
            'ego_turn_start_frame': turn, 'source_hashes': report['sources'],
            'legal_verdict_asserted': False, 'physical_acceptance_claimed': False}
