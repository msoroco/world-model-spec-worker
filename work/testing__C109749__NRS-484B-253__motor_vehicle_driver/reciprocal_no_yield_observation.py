"""Source-bound motion observation for the distinct reciprocal no-yield case.

The case requires the later opposing complete body to enter the junction while
the subject is still turning. This describes motion, not a legal right-of-way
finding. A mere nonzero approach speed outside the junction is insufficient.
"""

import json
import math
from pathlib import Path

from measurements import analyze, _body_intersects


def observe(attempt):
    attempt = Path(attempt)
    report = analyze(attempt)
    geometry = json.loads((attempt/'intersection_geometry.json').read_text())
    polygon = geometry['intersection_polygon_xy_m']
    direction = geometry['oncoming_direction_xy']
    rows = [json.loads(line) for line in (attempt/'interaction_history.jsonl').read_text().splitlines() if line.strip()]
    first_turn = report['ego_turn_start_frame']
    initial_clearance = report['initial_oncoming_clearance_frame']
    if first_turn is None or initial_clearance is None or initial_clearance >= first_turn:
        raise ValueError('Sourced initial yield and subsequent turn missing')
    if _body_intersects(rows[0]['reciprocal']['body_vertices_xy_m'], polygon):
        raise ValueError('Later opposing body already inside at capture start')
    turn_row = next(row for row in rows if row['frame'] == first_turn)
    if not turn_row['ego_left_indicator']:
        raise ValueError('Original left-indicator readback absent at turn')
    ego_exit = next((row['frame'] for row in rows if row['frame'] >= first_turn and
                     not _body_intersects(row['ego']['body_vertices_xy_m'], polygon)), None)
    if ego_exit is None:
        raise ValueError('Sourced ego junction clearance missing')
    entry = next((row for row in rows if first_turn <= row['frame'] < ego_exit and
                  _body_intersects(row['reciprocal']['body_vertices_xy_m'], polygon)), None)
    if entry is None:
        raise ValueError('Later opposing body did not enter during subject turn')
    for row in rows:
        if first_turn <= row['frame'] <= entry['frame']:
            closing = sum(row['reciprocal']['velocity_xy_mps'][i]*direction[i] for i in (0, 1))
            if not math.isfinite(closing) or closing <= 0.5:
                raise ValueError('Later opposing original motion stopped before entry')
    return {'initial_oncoming_clearance_frame':initial_clearance,
            'ego_turn_start_frame':first_turn,'ego_exit_frame':ego_exit,
            'later_opposing_entry_frame':entry['frame'],
            'later_opposing_stopped_outside_during_turn':report['reciprocal_stopped_outside_during_turn'],
            'legal_verdict_asserted':False,'sources':report['sources']}
