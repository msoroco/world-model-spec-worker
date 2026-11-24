"""Source-bound geometry for NRS 484B.297(2); measurements are not verdicts."""

import hashlib
import json
import math
from pathlib import Path

FRAMES = 600
HZ = 20


def _unit(xy):
    if len(xy) != 2 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in xy):
        raise ValueError('Missing finite vector')
    norm = math.hypot(*xy)
    if norm < 1e-9:
        raise ValueError('Zero direction vector')
    return (xy[0] / norm, xy[1] / norm)


def _source(source):
    if source.get('source_kind') not in ('synthetic_diagnostic', 'original_native'):
        raise ValueError('Source provenance missing')
    for key in ('highway_authority_source', 'highway_boundary_source', 'sidewalk_inventory_source',
                'subsection_6_obstruction_source', 'traffic_route_source'):
        if not source.get(key):
            raise ValueError('Required context source missing: ' + key)
    if source.get('sidewalk_present') is not False:
        raise ValueError('No-sidewalk activation not sourced')
    if source.get('subsection_6_obstruction') is not False:
        raise ValueError('Subsection 6 exception cannot be assumed away')
    half_width = source.get('highway_half_width_m')
    if not isinstance(half_width, (int, float)) or half_width <= 0:
        raise ValueError('Highway boundary invalid')
    anchor = source.get('highway_centerline_anchor_xy_m')
    if not isinstance(anchor, list) or len(anchor) != 2 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in anchor):
        raise ValueError('Highway centreline anchor missing')
    return _unit(source['traffic_direction_xy'])


def measure(source, frames):
    """Return frame joined side and facing measurements with explicit unknowns."""
    traffic_dir = _source(source)
    if len(frames) != FRAMES:
        raise ValueError('Incomplete 30-second source trace')
    rows = []
    for i, row in enumerate(frames):
        if row.get('video_frame') != i or abs(row.get('time_s', -1) - i / HZ) > 1e-8:
            raise ValueError('Source frame/time join failed')
        if not row.get('pedestrian_id') or not row.get('vehicle_id'):
            raise ValueError('Participant identity missing')
        px, py = row['pedestrian_xy_m']
        vx, vy = row['vehicle_xy_m']
        if not all(math.isfinite(v) for v in (px, py, vx, vy)):
            raise ValueError('Nonfinite position')
        heading = _unit(row['pedestrian_heading_xy'])
        anchor_x, anchor_y = source['highway_centerline_anchor_xy_m']
        cross = traffic_dir[0] * (py - anchor_y) - traffic_dir[1] * (px - anchor_x)
        side = 'traffic_right' if cross < 0 else 'traffic_left' if cross > 0 else 'centerline'
        facing_dot = heading[0] * traffic_dir[0] + heading[1] * traffic_dir[1]
        longitudinal_gap = (px - vx) * traffic_dir[0] + (py - vy) * traffic_dir[1]
        rows.append({'video_frame': i, 'time_s': i / HZ, 'pedestrian_id': row['pedestrian_id'],
                     'vehicle_id': row['vehicle_id'], 'highway_side': side,
                     'within_highway_boundary': abs(cross) <= source['highway_half_width_m'],
                     'heading_traffic_dot': round(facing_dot, 6),
                     'vehicle_longitudinal_gap_m': round(longitudinal_gap, 3),
                     'approaching_vehicle_ahead': longitudinal_gap > 0 and facing_dot < 0})
    return {'source_kind': source['source_kind'], 'frames': FRAMES, 'rate_hz': HZ,
            'activation_context': {'no_sidewalk_sourced': True, 'subsection_6_obstruction_sourced_false': True,
                                   'highway_authority_source': source['highway_authority_source']},
            'counts': {'traffic_right': sum(r['highway_side'] == 'traffic_right' for r in rows),
                       'traffic_left': sum(r['highway_side'] == 'traffic_left' for r in rows),
                       'facing_opposite_traffic': sum(r['heading_traffic_dot'] < 0 for r in rows),
                       'approaching_vehicle_ahead': sum(r['approaching_vehicle_ahead'] for r in rows)},
            'measurements': rows, 'legal_verdict': None, 'physical_completion': False}


def prove():
    source = {'source_kind': 'synthetic_diagnostic', 'highway_authority_source': 'fixture:road-public-access',
              'highway_boundary_source': 'fixture:survey-boundary', 'sidewalk_inventory_source': 'fixture:no-sidewalk',
              'subsection_6_obstruction_source': 'fixture:no-obstructed-sidewalk',
              'traffic_route_source': 'fixture:eastbound-lane', 'sidewalk_present': False,
              'subsection_6_obstruction': False, 'highway_half_width_m': 6.0,
              'highway_centerline_anchor_xy_m': [0.0, 0.0],
              'traffic_direction_xy': [1.0, 0.0]}
    def sample(y, heading):
        return [{'video_frame': i, 'time_s': i / HZ, 'pedestrian_id': 'ped-1', 'vehicle_id': 'vehicle-1',
                 'pedestrian_xy_m': [20 - i * .02, y], 'vehicle_xy_m': [-30 + i * .04, -1.75],
                 'pedestrian_heading_xy': heading} for i in range(FRAMES)]
    a = measure(source, sample(-4.0, [-1, 0]))
    b = measure(source, sample(4.0, [1, 0]))
    assert a['counts']['traffic_right'] == FRAMES and a['counts']['facing_opposite_traffic'] == FRAMES
    assert b['counts']['traffic_left'] == FRAMES and b['counts']['facing_opposite_traffic'] == 0
    rejects = []
    for kind in ('short', 'missing_sidewalk', 'exception', 'time_join', 'participant'):
        bad_source = dict(source)
        bad = sample(-4.0, [-1, 0])
        if kind == 'short': bad.pop()
        if kind == 'missing_sidewalk': bad_source.pop('sidewalk_inventory_source')
        if kind == 'exception': bad_source['subsection_6_obstruction'] = True
        if kind == 'time_join': bad[8]['time_s'] += .05
        if kind == 'participant': bad[8].pop('pedestrian_id')
        try: measure(bad_source, bad)
        except ValueError as exc: rejects.append({'negative': kind, 'error': str(exc)})
        else: raise AssertionError(kind + ' was accepted')
    return {'format': 'worker-source-measurement-proof', 'assignment_id': 'training__C230259__NRS-484B-297-2__pedestrian',
            'source_kind': 'synthetic_diagnostic', 'frames': FRAMES,
            'case_a_counts': a['counts'], 'case_b_counts': b['counts'],
            'negative_rejections': rejects, 'physical_completion': False, 'legal_verdict': None}


if __name__ == '__main__':
    receipt = prove()
    Path(__file__).with_name('walking-side-proof.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))
