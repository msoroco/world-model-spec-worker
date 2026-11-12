"""Independent source-bound audit of C125763's two controlled comparisons."""
import json
import math
from pathlib import Path

from audit_delivery import audit as audit_delivery
from runner import ASSIGNMENT

EXPECTED={'yield_sign_relative_side':(
    ASSIGNMENT+'__yield_ego_left_near_time',
    ASSIGNMENT+'__yield_ego_right_near_time'),
          'yield_sign_entry_timing':(
    ASSIGNMENT+'__yield_ego_left_near_time',
    ASSIGNMENT+'__yield_ego_left_separated')}


def require(ok,message):
    if not ok:raise ValueError(message)


def _load(root):
    root=Path(root)
    analysis_name=('analysis-report.json' if (root/'analysis-report.json').is_file()
                   else 'saved-analysis.json')
    proof=audit_delivery(root,analysis_name=analysis_name)
    cfg=json.loads((root/'config.json').read_text())
    ctx=json.loads((root/'junction_context.json').read_text())
    measurements=json.loads((root/analysis_name).read_text())['measurements']
    return {'proof':proof,'config':cfg,'context':ctx,
            'values':{key:value['value'] for key,value in measurements.items()}}


def audit_pair(name,left,right):
    require(name in EXPECTED,'Unknown declared comparison')
    a,b=_load(left),_load(right)
    require((a['proof']['case_id'],b['proof']['case_id'])==EXPECTED[name],
            'Exact case IDs or comparison order differ')
    ac,bc=a['context'],b['context']
    fixed=('native_map_id','intersection_id','intersection_polygon_xy_m',
           'same_statutory_crossing','native_yield_sign_id',
           'crossing_geometry_source','median_spacing_source',
           'all_entrances_source','sign_governance_source',
           'sign_face_video_source','ego_highway_id','ego_road_id',
           'ego_approach_forward_xy')
    require(all(ac.get(key)==bc.get(key) for key in fixed),
            'Fixed crossing, ego approach or governing sign differs')
    cfg_a,cfg_b=a['config'],b['config']
    require(cfg_a['actor']==cfg_b['actor']=='motor_vehicle_driver' and
            cfg_a['rate_hz']==cfg_b['rate_hz']==20 and
            cfg_a['duration_s']==cfg_b['duration_s'] and
            cfg_a['required_atoms']==cfg_b['required_atoms'],
            'Fixed actor, duration or observation contract differs')
    av,bv=a['values'],b['values']
    time_a=av['entry_timing']['absolute_difference_s']
    time_b=bv['entry_timing']['absolute_difference_s']
    if name=='yield_sign_relative_side':
        require(ac['other_highway_id']==bc['other_highway_id'] and
                cfg_a.get('other_release_frame')==cfg_b.get('other_release_frame') and
                ac['other_approach_forward_xy']!=bc['other_approach_forward_xy'] and
                av['relative_right_side']['other_spatially_right'] is True and
                bv['relative_right_side']['other_spatially_right'] is False and
                math.isclose(time_a,time_b,abs_tol=1e-9),
                'Relative side change or fixed entry timing not demonstrated')
    else:
        require(ac['other_highway_id']==bc['other_highway_id'] and
                type(cfg_a.get('other_release_frame')) is int and
                type(cfg_b.get('other_release_frame')) is int and
                cfg_b['other_release_frame']<cfg_a['other_release_frame'] and
                ac['other_road_id']==bc['other_road_id'] and
                ac['other_approach_forward_xy']==bc['other_approach_forward_xy'] and
                av['relative_right_side']['other_spatially_right'] is True and
                bv['relative_right_side']['other_spatially_right'] is True and
                time_a<time_b,
                'Fixed approaches or measured timing difference missing')
    return {'comparison_id':name,'software_comparison_passed':True,
            'cases':list(EXPECTED[name]),
            'entry_time_differences_s':[time_a,time_b],
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}


def audit(root,attempts):
    root=Path(root)
    plan=json.loads((root/'case-plan.json').read_text())
    declared={row['comparison_id']:row for row in plan['comparisons']}
    require(set(declared)==set(EXPECTED),'Selected comparison coverage differs')
    results=[]
    for name,ids in EXPECTED.items():
        row=declared[name]
        require(tuple(row['case_ids'])==ids and row.get('fixed_conditions') and
                row.get('deliberate_differences'),
                'Incomplete or changed comparison declaration')
        require(all(case in attempts for case in ids),'Missing exact comparison attempt')
        results.append(audit_pair(name,attempts[ids[0]],attempts[ids[1]]))
    return {'format':'worker-c125763-software-comparison-audit',
            'software_comparisons_passed':True,'comparisons':results,
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False,
            'delivery_ready':False}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--name',choices=sorted(EXPECTED),required=True)
    parser.add_argument('--left',type=Path,required=True)
    parser.add_argument('--right',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(audit_pair(args.name,args.left,args.right),indent=2))
