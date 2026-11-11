"""Source-bound descriptive check for the opposing-inside yield branch.

This checks a staged movement sequence, not legal right-of-way or an immediate
hazard threshold.
"""
import json
import math
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon

from measurements import analyze


def _body(row, actor):
    return MultiPoint(row[actor]['body_vertices_xy_m']).convex_hull


def observe(attempt):
    attempt = Path(attempt)
    report = analyze(attempt)
    geometry = json.loads((attempt / 'intersection_geometry.json').read_text())
    polygon = Polygon(geometry['intersection_polygon_xy_m'])
    rows = [json.loads(line) for line in (attempt / 'interaction_history.jsonl').read_text().splitlines() if line]
    if polygon.is_empty or not polygon.is_valid or not polygon.covers(_body(rows[0], 'oncoming')):
        raise ValueError('Initial opposing complete body is not inside sourced junction')
    yielded = [row['frame'] for row in rows
               if polygon.intersects(_body(row, 'ego')) and polygon.intersects(_body(row, 'oncoming'))
               and math.hypot(*row['ego']['velocity_xy_mps']) < 0.1
               and row['ego_left_indicator']]
    if not yielded:
        raise ValueError('No sourced subject yield while both bodies overlap junction')
    clearance = report['initial_oncoming_clearance_frame']
    turn = report['ego_turn_start_frame']
    if clearance is None or turn is None or not max(yielded) < clearance < turn:
        raise ValueError('Initial opposing clearance must precede subject left turn')
    return {'format': 'c109749-inside-yield-observation',
            'initial_frame': rows[0]['frame'], 'subject_yield_frames': yielded,
            'initial_oncoming_clearance_frame': clearance,
            'ego_turn_start_frame': turn, 'source_hashes': report['sources'],
            'legal_verdict_asserted': False, 'physical_acceptance_claimed': False}
