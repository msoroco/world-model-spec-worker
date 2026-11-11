"""Source-only engineering completion check for the selected left turn."""

from hashlib import sha256
import json
from math import hypot
from pathlib import Path

from turn_source_measurement import measure


def _center(row):
    corners=row['body_corners_xy_m']
    return [sum(point[axis] for point in corners)/4 for axis in (0,1)]


def assess(attempt, case_id, *, minimum_progress_m=1.0):
    root=Path(attempt)
    observed=measure(root,case_id)
    source=root/'body_footprints.jsonl'
    rows=[json.loads(line) for line in source.read_text().splitlines() if line.strip()]
    start=_center(rows[0]);end=_center(rows[-1])
    displacement=hypot(end[0]-start[0],end[1]-start[1])
    complete=displacement>=minimum_progress_m and observed['frame_count']==len(rows)
    return {'status':'met' if complete else 'not_met',
            'method':'Original body-center displacement across ordered sourced approach, entry and departure phases',
            'sources':{'body_footprints.jsonl':sha256(source.read_bytes()).hexdigest(),
                       **observed['source_sha256']},
            'intervals':[{'first_frame':rows[0]['frame'],'last_frame':rows[-1]['frame'],
                          'first_time_s':rows[0]['time_s'],'last_time_s':rows[-1]['time_s']}],
            'details':{'body_center_displacement_m':displacement,
                       'minimum_engineering_progress_m':minimum_progress_m,
                       'approach_and_entry_right_of_centerline':observed['approach_all_original_corners_right_of_centerline']},
            'legal_verdict_claimed':False}
