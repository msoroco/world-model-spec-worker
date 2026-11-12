"""Measure a far opposing approach when the subject starts its left turn.

The engineering TTC control does not decide the statutory immediate hazard.
"""
import json
from pathlib import Path

from measurements import analyze, _body_intersects


def observe(attempt):
    attempt = Path(attempt)
    report = analyze(attempt)
    config = json.loads((attempt / 'config.json').read_text())
    if config.get('hazard_legal_threshold', 'missing') is not None:
        raise ValueError('Far-approach legal hazard threshold must remain unset')
    release = config.get('controller_release_ttc_s')
    if isinstance(release, bool) or not isinstance(release, (int, float)) or release <= 0:
        raise ValueError('Positive engineering release TTC required')
    geometry = json.loads((attempt / 'intersection_geometry.json').read_text())
    polygon = geometry['intersection_polygon_xy_m']
    rows = [json.loads(line) for line in
            (attempt / 'interaction_history.jsonl').read_text().splitlines() if line.strip()]
    turn = report['ego_turn_start_frame']
    entry = report['oncoming_first_in_intersection_frame']
    if turn is None or entry is None or turn >= entry:
        raise ValueError('Ego turn must precede opposing body entry')
    if not all(not _body_intersects(row['oncoming']['body_vertices_xy_m'], polygon)
               for row in rows if row['frame'] <= turn):
        raise ValueError('Complete opposing body must remain outside through turn start')
    selected = next(row for row in rows if row['frame'] == turn)
    sample = next(item for item in report['opposing_conflict_samples'] if item['frame'] == turn)
    ttc = sample['kinematic_time_to_conflict_s']
    if (sample['remaining_distance_m'] <= 0 or sample['closing_speed_mps'] <= 0.5
            or ttc is None or ttc < release):
        raise ValueError('Measured far approach must exceed engineering release TTC')
    if not selected['ego_left_indicator']:
        raise ValueError('Left indicator must be on when turn starts')
    return {'format': 'c109749-far-approach-observation',
            'ego_turn_start_frame': turn, 'opposing_entry_frame': entry,
            'turn_sample': sample, 'engineering_release_ttc_s': release,
            'source_hashes': report['sources'], 'legal_verdict_asserted': False,
            'physical_acceptance_claimed': False}
