"""Independent fixed-context and deliberate-difference green-arrow audit."""

import argparse
import hashlib
import json
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(attempt,case):
    folder=Path(attempt)
    result=read(folder/'result.json')
    config=read(folder/'config.json')
    context=read(folder/'intersection-context.json')
    survey=read(folder/'context-survey.json')
    review=read(folder/'independent-review.json')
    if (result.get('case_id')!=case or config.get('selected_case_id')!=case
            or result.get('provenance_kind')!='native'
            or result.get('diagnostic_fixture') is not False
            or context.get('source_kind')!='original_native_context_survey'
            or survey.get('source_kind')!='original_native_context_survey'
            or review.get('format')!='worker-c111603-independent-source-review-v1'
            or review.get('case_id')!=case or not review.get('reviewer_id')):
        raise ValueError('Comparison lacks independently reviewed original source')
    facts=dict(result.get('measured_values',{}))
    facts['fixed_context']={key:context.get(key) for key in (
        'map_name','map_sha256','arrow_opendrive_id','arrow_direction',
        'intersection_bounds_m','adjacent_crosswalk_bounds_m')}
    facts['capture_profile']={key:config.get(key) for key in
                              ('rate_hz','duration_s','cameras')}
    facts['participant_setup']={key:survey.get(key) for key in
        ('pedestrian_spawn_xyz_yaw','other_traffic_spawn_xyz_yaw',
         'pedestrian_permission_source','other_traffic_permission_source')}
    return dict(result,measured_values=facts)


def check(left,right,comparison):
    cases=comparison['case_ids']
    if (left.get('case_id')!=cases[0] or right.get('case_id')!=cases[1]
            or any(row.get('provenance_kind')!='native' or
                   row.get('diagnostic_fixture') is not False for row in (left,right))):
        raise ValueError('Comparison lacks two original exact-case Native sources')
    if any(row.get('accepted') is not False or row.get('legal_verdict_claimed') is not False
           for row in (left,right)):
        raise ValueError('Comparison prelabels legal outcome')
    a,b=left.get('measured_values',{}),right.get('measured_values',{})
    for key in ('fixed_context','capture_profile','participant_setup'):
        if not a.get(key) or a[key]!=b.get(key):
            raise ValueError('Undeclared comparison source difference')
    if (a.get('frames')!=600 or b.get('frames')!=600
            or a.get('rate_hz')!=20 or b.get('rate_hz')!=20
            or a.get('first_ego_entry_frame') is None
            or b.get('first_ego_entry_frame') is None):
        raise ValueError('Comparison lacks joined original arrow and turn source')
    variable=comparison['deliberate_differences']
    if variable==['direction']:
        if (a.get('first_direction_mismatch_frame') is not None
                or b.get('first_direction_mismatch_frame') is None):
            raise ValueError('Comparison lacks measured turn-direction contrast')
    elif variable==['illumination']:
        if (a.get('first_unlit_intersection_motion_frame') is not None
                or b.get('first_unlit_intersection_motion_frame') is None):
            raise ValueError('Comparison lacks measured arrow-interval contrast')
    elif variable==['pedestrian_priority']:
        if (a.get('first_pedestrian_crosswalk_motion_overlap_frame') is not None
                or b.get('first_pedestrian_crosswalk_motion_overlap_frame') is None):
            raise ValueError('Comparison lacks measured pedestrian-timing contrast')
    elif variable==['traffic_priority']:
        if (a.get('first_other_traffic_motion_overlap_frame') is not None
                or b.get('first_other_traffic_motion_overlap_frame') is None):
            raise ValueError('Comparison lacks measured other-traffic-timing contrast')
    else:
        raise ValueError('Comparison changed declared difference')
    return {'comparison_id':comparison['comparison_id'],'case_ids':cases,
            'deliberate_differences':variable,'legal_verdict_claimed':False}


def selftest(comparison,negative):
    facts={'frames':600,'rate_hz':20,'first_ego_entry_frame':200,
        'first_direction_mismatch_frame':None,
        'first_unlit_intersection_motion_frame':None,
        'first_pedestrian_crosswalk_motion_overlap_frame':None,
        'first_other_traffic_motion_overlap_frame':None,
        'fixed_context':{'map_name':'original_map','arrow_opendrive_id':'201'},
        'capture_profile':{'rate_hz':20,'duration_s':30},
        'participant_setup':{'pedestrian_spawn_xyz_yaw':[1,2,1,0]}}
    base={'provenance_kind':'native','diagnostic_fixture':False,
          'accepted':False,'legal_verdict_claimed':False}
    left=dict(base,case_id=comparison['case_ids'][0],measured_values=dict(facts))
    second=dict(facts)
    target={'direction':'first_direction_mismatch_frame',
            'illumination':'first_unlit_intersection_motion_frame',
            'pedestrian_priority':'first_pedestrian_crosswalk_motion_overlap_frame',
            'traffic_priority':'first_other_traffic_motion_overlap_frame'}
    second[target[comparison['deliberate_differences'][0]]]=240
    right=dict(base,case_id=comparison['case_ids'][1],measured_values=second)
    if negative:
        second['fixed_context']={'map_name':'another_map'}
        check(left,right,comparison)
        raise AssertionError('Changed original intersection accepted')
    result=check(left,right,comparison)
    try:check(left,dict(right,provenance_kind='synthetic_fixture'),comparison)
    except ValueError:pass
    else:raise AssertionError('Diagnostic fixture accepted as original')
    return dict(result,original_capture_attested=False,predicates_tested=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--comparison',required=True)
    parser.add_argument('--self-test',action='store_true')
    parser.add_argument('--negative',action='store_true')
    parser.add_argument('--left');parser.add_argument('--right');parser.add_argument('--output')
    args=parser.parse_args()
    plan=read(Path(__file__).with_name('case-plan.json'))
    comparison=next((row for row in plan['comparisons']
                     if row['comparison_id']==args.comparison),None)
    if comparison is None:
        raise ValueError('Unknown exact comparison')
    if args.self_test:
        result=selftest(comparison,args.negative)
    else:
        result=check(source(args.left,comparison['case_ids'][0]),
                     source(args.right,comparison['case_ids'][1]),comparison)
        result.update(format='worker-c111603-original-comparison-audit-v1',
                      left_sha256=sha(Path(args.left)/'result.json'),
                      right_sha256=sha(Path(args.right)/'result.json'),
                      auditor_sha256=sha(__file__))
        Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':
    main()
