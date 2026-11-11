"""Original-source description of proceeding before an inside opposing actor clears."""
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
    polygon = Polygon(json.loads((attempt / 'intersection_geometry.json').read_text())
                      ['intersection_polygon_xy_m'])
    rows = [json.loads(line) for line in
            (attempt / 'interaction_history.jsonl').read_text().splitlines() if line]
    if polygon.is_empty or not polygon.is_valid or not polygon.covers(_body(rows[0], 'oncoming')):
        raise ValueError('Initial opposing complete body is not inside sourced junction')
    turn = report['ego_turn_start_frame']
    clearance = report['initial_oncoming_clearance_frame']
    if turn is None or clearance is None or turn >= clearance:
        raise ValueError('Subject turn must begin before initial opposing clearance')
    overlap = [row['frame'] for row in rows if row['frame'] <= turn
               and polygon.intersects(_body(row, 'ego'))
               and polygon.intersects(_body(row, 'oncoming'))
               and math.hypot(*row['ego']['velocity_xy_mps']) > 0.5
               and row['ego_left_indicator']]
    if not overlap or turn not in overlap:
        raise ValueError('No sourced moving subject turn with opposing body inside')
    return {'format': 'c109749-inside-no-yield-observation',
            'initial_frame': rows[0]['frame'], 'moving_overlap_frames': overlap,
            'ego_turn_start_frame': turn, 'initial_oncoming_clearance_frame': clearance,
            'source_hashes': report['sources'], 'legal_verdict_asserted': False,
            'physical_acceptance_claimed': False}
