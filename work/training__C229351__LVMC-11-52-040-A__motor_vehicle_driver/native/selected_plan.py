"""Exact, source-gated roadway rest requests for LVMC 11.52.040(A).

Requested yaw and activity are experimental settings. Roadway status, lawful
traffic direction, actual standing/parking, exception applicability and legal
result require independent original-source review.
"""
import hashlib
import json
import math
from pathlib import Path

AID = 'training__C229351__LVMC-11-52-040-A__motor_vehicle_driver'
CELL = {'layout': 'road', 'maneuver': 'parallel_park', 'control': 'road_edge'}
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
POSES = {'parallel_lawful': 0.0, 'angled_traffic_side': 35.0,
         'parallel_against_traffic': 180.0}
CASES = {AID + '__' + activity + '_' + pose: {'activity': activity,
         'pose': pose, 'requested_yaw_offset_deg': yaw}
         for activity in ('parking', 'standing') for pose, yaw in POSES.items()}
SOURCE_KEYS = ('map_name', 'roadway_boundary_source_id', 'edge_tangent_source_id',
               'lawful_traffic_source_id', 'parking_permission_source_id',
               'roadway_class_source_id', 'vehicle_identity_source_id',
               'driver_identity_source_id', 'rest_activity_source_id',
               'reviewed_source_sha256', 'reviewer')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def review_survey(survey):
    require(survey.get('source_kind') == 'original_native_road_edge_survey',
            'original road-edge survey required')
    require(survey.get('fixed_cell') == CELL, 'survey cell mismatch')
    for key in SOURCE_KEYS:
        require(isinstance(survey.get(key), str) and survey[key].strip(),
                'missing original source: ' + key)
    require(survey.get('chapter_exception_status') in
            ('none_found', 'applicable', 'unknown'),
            'Chapter exception status must be source reviewed')
    require(isinstance(survey.get('chapter_exception_source_refs'), list),
            'Chapter exception source inventory required')
    if survey['chapter_exception_status'] == 'applicable':
        require(survey['chapter_exception_source_refs'],
                'applicable exception needs original authority')
    require(isinstance(survey.get('edge_tangent_xy'), list) and
            isinstance(survey.get('lawful_direction_xy'), list),
            'edge and lawful direction source vectors required')
    for key in ('edge_tangent_xy', 'lawful_direction_xy'):
        value = survey[key]
        require(len(value) == 2 and all(type(x) in (int, float) and
                math.isfinite(x) for x in value) and math.hypot(*value) > 0,
                'invalid original direction: ' + key)
    require(len(survey.get('spawn_xyz_yaw_deg', [])) == 4 and
            len(survey.get('rest_xyz_m', [])) == 3 and
            survey.get('vehicle_blueprint'),
            'source-aligned original vehicle and rest geometry required')
    return survey


def request(case_id, survey):
    require(case_id in CASES, 'unknown exact case')
    review_survey(survey)
    setting = CASES[case_id]
    return {'case_id': case_id, 'fixed_cell': CELL,
            'source_survey_sha256': survey['reviewed_source_sha256'],
            'activity_requested': setting['activity'],
            'rest_pose_requested': setting['pose'],
            'requested_yaw_offset_deg': setting['requested_yaw_offset_deg'],
            'fixed_rest_xyz_m': survey['rest_xyz_m'],
            'fixed_roadway_source': survey['roadway_boundary_source_id'],
            'fixed_lawful_direction_source': survey['lawful_traffic_source_id'],
            'chapter_exception_status': survey['chapter_exception_status'],
            'actual_activity_observed': None, 'actual_rest_pose_observed': None,
            'legal_result': None}


def compare(plans):
    require(set(plans) == set(CASES), 'all six exact cases required')
    fixed = ('fixed_cell', 'source_survey_sha256', 'fixed_rest_xyz_m',
             'fixed_roadway_source', 'fixed_lawful_direction_source',
             'chapter_exception_status')
    first = next(iter(CASES))
    for field in fixed:
        require(all(plans[c][field] == plans[first][field] for c in CASES),
                'comparison fixed source changed: ' + field)
    for case_id, setting in CASES.items():
        require(plans[case_id]['activity_requested'] == setting['activity'] and
                plans[case_id]['rest_pose_requested'] == setting['pose'] and
                plans[case_id]['requested_yaw_offset_deg'] ==
                setting['requested_yaw_offset_deg'], 'case setting changed')
    return {'case_ids': list(CASES), 'fixed_source_fields': list(fixed),
            'requested_activities': ['standing', 'parking'],
            'requested_poses': list(POSES), 'original_review_pending': True,
            'legal_result': None}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--survey', required=True)
    args = parser.parse_args()
    survey = json.loads(Path(args.survey).read_text())
    print(json.dumps(compare({case: request(case, survey) for case in CASES}),
                     sort_keys=True))
