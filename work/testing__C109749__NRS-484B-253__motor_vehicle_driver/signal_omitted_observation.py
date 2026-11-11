"""Describe an unsignalled left turn after yielding to an inside opposing body."""
import json
import math
from pathlib import Path
from shapely.geometry import MultiPoint, Polygon
from measurements import analyze


def observe(attempt):
    attempt=Path(attempt)
    report=analyze(attempt)
    geometry=json.loads((attempt/'intersection_geometry.json').read_text())
    polygon=Polygon(geometry['intersection_polygon_xy_m'])
    rows=[json.loads(line) for line in (attempt/'interaction_history.jsonl').read_text().splitlines() if line]
    body=lambda row,role: MultiPoint(row[role]['body_vertices_xy_m']).convex_hull
    if polygon.is_empty or not polygon.is_valid or not polygon.covers(body(rows[0],'oncoming')):
        raise ValueError('Initial opposing complete body must start inside sourced junction')
    if any(row['ego_left_indicator'] for row in rows):
        raise ValueError('Omitted-signal branch has an observed left indicator')
    yielded=[row['frame'] for row in rows if polygon.intersects(body(row,'ego'))
             and polygon.intersects(body(row,'oncoming'))
             and math.hypot(*row['ego']['velocity_xy_mps'])<0.1]
    clearance=report['initial_oncoming_clearance_frame']
    turn=report['ego_turn_start_frame']
    if not yielded or clearance is None or turn is None or not max(yielded)<clearance<turn:
        raise ValueError('Unsignalled yield, clearance and turn sequence incomplete')
    return {'format':'c109749-signal-omitted-observation','initial_frame':rows[0]['frame'],
            'subject_yield_frames':yielded,'ego_left_indicator_frames':[],
            'initial_oncoming_clearance_frame':clearance,'ego_turn_start_frame':turn,
            'source_hashes':report['sources'],'legal_verdict_asserted':False,
            'physical_acceptance_claimed':False}
