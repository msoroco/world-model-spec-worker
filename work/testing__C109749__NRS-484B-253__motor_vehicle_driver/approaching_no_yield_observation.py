"""Describe a subject turn while the opposing complete body is still approaching outside."""
import json
from pathlib import Path
from shapely.geometry import MultiPoint, Polygon
from measurements import analyze


def observe(attempt):
    attempt = Path(attempt)
    report = analyze(attempt)
    geometry = json.loads((attempt/'intersection_geometry.json').read_text())
    polygon = Polygon(geometry['intersection_polygon_xy_m'])
    rows = [json.loads(line) for line in (attempt/'interaction_history.jsonl').read_text().splitlines() if line]
    body = lambda row: MultiPoint(row['oncoming']['body_vertices_xy_m']).convex_hull
    if polygon.is_empty or not polygon.is_valid or polygon.intersects(body(rows[0])):
        raise ValueError('Initial opposing complete body must start outside sourced junction')
    turn = report['ego_turn_start_frame']
    entry = report['oncoming_first_in_intersection_frame']
    clearance = report['initial_oncoming_clearance_frame']
    if turn is None or entry is None or clearance is None or not turn < entry < clearance:
        raise ValueError('Subject turn must precede opposing entry and clearance')
    turn_row = next(row for row in rows if row['frame']==turn)
    opponent = turn_row['oncoming']
    direction=geometry['oncoming_direction_xy']
    closing=sum(opponent['velocity_xy_mps'][i]*direction[i] for i in (0,1))
    if polygon.intersects(body(turn_row)) or closing <= 0.5 or not turn_row['ego_left_indicator']:
        raise ValueError('No sourced signalled turn with opposing body approaching outside')
    return {'format':'c109749-approaching-no-yield-observation', 'initial_frame':rows[0]['frame'],
            'ego_turn_start_frame':turn,'opposing_entry_frame':entry,
            'initial_oncoming_clearance_frame':clearance,'opposing_closing_speed_mps_at_turn':closing,
            'source_hashes':report['sources'],'legal_verdict_asserted':False,'physical_acceptance_claimed':False}
