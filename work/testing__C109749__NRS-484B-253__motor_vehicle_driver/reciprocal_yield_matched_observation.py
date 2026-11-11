"""Measured stopped-outside movement for a reciprocal matched-control draft.

This records a later actor's body and speed while the subject turns. It does
not decide whether the actor had a legal duty or whether a signal sufficed.
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
    rows = [json.loads(line) for line in (attempt/'interaction_history.jsonl').read_text().splitlines() if line.strip()]
    turn = report['ego_turn_start_frame']
    initial_clearance = report['initial_oncoming_clearance_frame']
    if turn is None or initial_clearance is None or initial_clearance >= turn:
        raise ValueError('Sourced initial clearance before subject turn missing')
    turn_row = next(row for row in rows if row['frame'] == turn)
    if not turn_row['ego_left_indicator']:
        raise ValueError('Original left-indicator readback absent at turn')
    ego_exit = next((row['frame'] for row in rows if row['frame'] >= turn and
                     not _body_intersects(row['ego']['body_vertices_xy_m'], polygon)), None)
    if ego_exit is None:
        raise ValueError('Sourced subject junction clearance missing')
    window = [row for row in rows if turn <= row['frame'] < ego_exit]
    if any(_body_intersects(row['reciprocal']['body_vertices_xy_m'], polygon) for row in window):
        raise ValueError('Later opposing complete body entered during subject turn')
    stopped = next((row['frame'] for row in window if
                    math.hypot(*row['reciprocal']['velocity_xy_mps']) < 0.1), None)
    if stopped is None or not report['reciprocal_stopped_outside_during_turn']:
        raise ValueError('Later opposing stopped-outside observation missing')
    return {'initial_oncoming_clearance_frame':initial_clearance,
            'ego_turn_start_frame':turn,'ego_exit_frame':ego_exit,
            'later_opposing_stopped_outside_frame':stopped,
            'later_opposing_entry_frame':None,
            'legal_verdict_asserted':False,'sources':report['sources']}
