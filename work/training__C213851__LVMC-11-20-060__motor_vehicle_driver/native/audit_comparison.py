"""Independent paired source audit for the two road-exit stop policies."""

import json
from pathlib import Path

from measure_sidewalk import measure, rows, sha


def audit(stop_attempt, cross_attempt, assignment_id):
    stop_attempt = Path(stop_attempt)
    cross_attempt = Path(cross_attempt)
    cases = (assignment_id + '__stop_before_sidewalk',
             assignment_id + '__cross_without_stop')
    measures = (measure(stop_attempt, cases[0]),
                measure(cross_attempt, cases[1]))
    for name in ('road.xodr', 'site-review.json'):
        if sha(stop_attempt / name) != sha(cross_attempt / name):
            raise ValueError('Paired sidewalk context changed: ' + name)
    left = rows(stop_attempt / 'native-rows.jsonl')
    right = rows(cross_attempt / 'native-rows.jsonl')
    for a, b in zip(left, right):
        fixed = ('native_frame', 'video_frame', 'time_s', 'source_cameras',
                 'vehicle_actor_id', 'pedestrian_actor_id',
                 'vehicle_half_extent_m', 'pedestrian_xy_m')
        if any(a[key] != b[key] for key in fixed):
            raise ValueError('Paired sidewalk actor, pedestrian or capture context changed')
        if a['vehicle_xy_m'][0] != b['vehicle_xy_m'][0]:
            raise ValueError('Paired sidewalk lateral route changed')
    if (measures[0]['observed_pre_sidewalk_stop_frames'] <= 0 or
            measures[1]['observed_pre_sidewalk_stop_frames'] != 0 or
            measures[0]['first_observed_body_sidewalk_cross_frame'] <=
            measures[1]['first_observed_body_sidewalk_cross_frame']):
        raise ValueError('Paired sidewalk stop-policy difference not observed')
    return {'format': 'road-to-driveway-independent-comparison',
            'passed': True, 'case_ids': list(cases),
            'fixed_source_sha256': {name: sha(stop_attempt / name)
                                    for name in ('road.xodr', 'site-review.json')},
            'measurements': list(measures),
            'physical_or_legal_outcome_claimed': False}
