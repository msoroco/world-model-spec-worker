"""Independent source-bound audit of C125763's controlled comparisons."""
import hashlib
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
OPPOSITE_ID='yield_sign_opposite_approach_context'
OPPOSITE_CASES=(ASSIGNMENT+'__yield_ego_left_near_time',
                ASSIGNMENT+'__yield_opposite_left_turn')


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


def audit_opposite_context_receipts(root):
    root=Path(root)
    manifest=json.loads((root/'execution-manifest.json').read_text())
    entries={row['case_id']:row for row in manifest['cases']}
    examples=[]
    hashes={}
    for case_id in OPPOSITE_CASES:
        entry=entries[case_id]
        receipt_path=root/entry['compatibility']['receipt']
        payload=receipt_path.read_bytes()
        receipt_hash=hashlib.sha256(payload).hexdigest()
        require(receipt_hash==entry['compatibility']['sha256'],
                'Exact opposite-context receipt hash changed')
        receipt=json.loads(payload)
        require(receipt.get('passed') is True and
                receipt.get('case_id')==case_id and
                receipt.get('candidate_id')=='primary' and
                receipt.get('construction_sha256')==entry['construction_sha256'] and
                receipt.get('negative_removed')=='controller_history.jsonl',
                'Exact source-bound opposite-context receipt required')
        recipe=json.loads(Path(entry['fixture_recipe']).read_text())
        source=Path(recipe['generator']['source'])
        require(hashlib.sha256(source.read_bytes()).hexdigest()==
                recipe['generator']['sha256'],
                'Opposite-context diagnostic source hash changed')
        files=json.loads(source.read_text())['files']
        measured=receipt['measurement_examples']
        for key in ('crossing_identity','entry_timing',
                    'device_qualification_context','opposite_left_turn_context',
                    'relative_right_side'):
            require(key in measured and measured[key].get('sources'),
                    'Missing original opposite-context measurement source')
            for name,expected in measured[key]['sources'].items():
                require(name in files and
                        hashlib.sha256(files[name].encode()).hexdigest()==expected,
                        'Opposite-context original source hash differs')
        examples.append(measured)
        hashes[case_id]=receipt_hash
    left,opposite=examples
    a,b=(x['crossing_identity']['value'] for x in examples)
    require(all(a[k]==b[k] for k in
                ('native_map_id','intersection_id','ego_highway_id',
                 'same_statutory_crossing')) and
            a['other_highway_id']!=b['other_highway_id'] and
            b['other_highway_id']==b['ego_highway_id'],
            'Fixed crossing or opposite-highway contrast missing')
    device_a,device_b=(x['device_qualification_context']['value']
                       for x in examples)
    require(device_a==device_b and device_a['native_yield_sign_id']==17 and
            all(device_a[key]=='unresolved' for key in
                ('official_device_judgment','governance_judgment',
                 'subsection_4_judgment')),
            'Fixed yield-sign identity or unresolved device review changed')
    turn_a,turn_b=(x['opposite_left_turn_context']['value']
                   for x in examples)
    require(turn_a['opposite_approach'] is False and
            turn_b['opposite_approach'] is True and
            turn_a['exception_judgment']==turn_b['exception_judgment']=='unresolved',
            'Opposite-approach contrast or open exception judgment changed')
    timing_a,timing_b=(x['entry_timing']['value'] for x in examples)
    require(timing_a['absolute_difference_s']==timing_b['absolute_difference_s'] and
            timing_a['approximately_same_time_judgment']==
            timing_b['approximately_same_time_judgment']=='unresolved',
            'Fixed measured entry timing changed')
    require(left['relative_right_side']['value']['inapplicable_to_opposite_exception'] is False and
            opposite['relative_right_side']['value']['inapplicable_to_opposite_exception'] is True,
            'Opposite exception side context differs')
    return {'comparison_id':OPPOSITE_ID,'case_ids':list(OPPOSITE_CASES),
            'software_comparison_passed':True,'receipt_sha256':hashes,
            'fixed_crossing_and_device_passed':True,
            'opposite_approach_contrast_passed':True,
            'exception_judgment':'unresolved',
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}


def audit(root,attempts):
    root=Path(root)
    plan=json.loads((root/'case-plan.json').read_text())
    declared={row['comparison_id']:row for row in plan['comparisons']}
    require(len(declared)==len(plan['comparisons']) and
            set(declared)==set(EXPECTED)|{OPPOSITE_ID},
            'Selected comparison coverage differs')
    results=[]
    for name,ids in EXPECTED.items():
        row=declared[name]
        require(tuple(row['case_ids'])==ids and row.get('fixed_conditions') and
                row.get('deliberate_differences'),
                'Incomplete or changed comparison declaration')
        require(all(case in attempts for case in ids),'Missing exact comparison attempt')
        results.append(audit_pair(name,attempts[ids[0]],attempts[ids[1]]))
    row=declared[OPPOSITE_ID]
    require(tuple(row['case_ids'])==OPPOSITE_CASES and
            row.get('fixed_conditions') and row.get('deliberate_differences'),
            'Incomplete or changed opposite-context declaration')
    results.append(audit_opposite_context_receipts(root))
    return {'format':'worker-c125763-software-comparison-audit',
            'software_comparisons_passed':True,'comparisons':results,
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False,
            'delivery_ready':False}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--name',choices=sorted(EXPECTED))
    parser.add_argument('--left',type=Path)
    parser.add_argument('--right',type=Path)
    parser.add_argument('--opposite-context',action='store_true')
    args=parser.parse_args()
    if args.opposite_context:
        require(not args.name and not args.left and not args.right,
                'Opposite-context audit uses the exact manifest')
        print(json.dumps(audit_opposite_context_receipts(Path(__file__).resolve().parent),indent=2))
    else:
        require(args.name and args.left and args.right,
                'Pair audit needs exact name and attempts')
        print(json.dumps(audit_pair(args.name,args.left,args.right),indent=2))
