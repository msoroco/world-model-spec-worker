"""Independent same-device, same-road signed U-turn comparison audit."""
import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

ASSIGNMENT='training__C104538__NRS-484B-403-2__motor_vehicle_driver'
COMPARISON=ASSIGNMENT+'__witness_comparison'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(root,name):
    path=Path(root)/name
    if not path.is_file():
        raise ValueError('Comparison source missing: '+str(path))
    return json.loads(path.read_text()) if name.endswith('.json') else path.read_text()


def audit(left,right):
    road1,road2=Path(left)/'road.xodr',Path(right)/'road.xodr'
    if not road1.is_file() or not road2.is_file() or sha(road1)!=sha(road2):
        raise ValueError('Controlled comparison road geometry differs')
    sign1,sign2=read(left,'sign-review.json'),read(right,'sign-review.json')
    fixed=('sign_code','governs_approach','governed_approach_lane_id',
           'opposing_lane_id','governed_native_xy_bounds_m')
    if any(sign1.get(k)!=sign2.get(k) for k in fixed):
        raise ValueError('Controlled comparison device or governed region differs')
    if sign1.get('sign_code')!='no_u_turn' or sign1.get('governs_approach') is not True:
        raise ValueError('Controlled comparison prohibition cue unverified')
    paths=[]
    for root in (left,right):
        path=Path(root)/'native_samples.jsonl'
        if not path.is_file():
            raise ValueError('Comparison Native source missing')
        rows=[json.loads(s) for s in path.read_text().splitlines()]
        if len(rows)!=600:
            raise ValueError('Comparison frame duration differs')
        paths.append((path,rows))
    one,two=(pair[1] for pair in paths)
    def reversal(rows):
        initial=rows[0]['native_forward_xy']
        final=rows[-1]['native_forward_xy']
        return (rows[-1]['native_lane_id']!=rows[0]['native_lane_id'] and
                sum(a*b for a,b in zip(initial,final)) < -0.94)
    first_turn=reversal(one)
    second_turn=reversal(two)
    if first_turn or not second_turn:
        raise ValueError('Controlled comparison measured path contrast missing')
    if one[0]['native_center_xy_m']!=two[0]['native_center_xy_m'] or one[0]['native_lane_id']!=two[0]['native_lane_id']:
        raise ValueError('Controlled comparison approach differs')
    return {'format':'c104538-source-bound-comparison-audit-v1',
            'comparison_id':COMPARISON,'passed':True,
            'fixed_conditions':['authored road geometry','prohibition cue','governed region',
                                'approach body/lane','600-frame capture contract'],
            'deliberate_difference':'requested and measured U-turn path',
            'measured_paths':{'witness_1_u_turn':first_turn,'witness_2_u_turn':second_turn},
            'source_hashes':{'road.xodr':sha(road1),
                             'witness_1_native_samples.jsonl':sha(paths[0][0]),
                             'witness_2_native_samples.jsonl':sha(paths[1][0]),
                             'witness_1_sign_review.json':sha(Path(left)/'sign-review.json'),
                             'witness_2_sign_review.json':sha(Path(right)/'sign-review.json')},
            'original_native_observed':False,'legal_verdict_claimed':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--comparison',required=True)
    parser.add_argument('--left')
    parser.add_argument('--right')
    parser.add_argument('--selftest',action='store_true')
    parser.add_argument('--negative-selftest',action='store_true')
    args=parser.parse_args()
    if args.comparison!=COMPARISON:
        raise ValueError('Wrong comparison identity')
    if args.selftest or args.negative_selftest:
        folder=Path(__file__).resolve().parents[1]
        repo=folder.parents[1]
        left=folder/'v2-source/witness_1'
        right=folder/'v2-source/witness_2'
        if args.negative_selftest:
            with tempfile.TemporaryDirectory(dir=repo/'.runtime-work',prefix='c104538-comparison-') as tmp:
                copy=Path(tmp)
                for name in ('road.xodr','sign-review.json','native_samples.jsonl'):
                    shutil.copyfile(right/name,copy/name)
                sign=json.loads((copy/'sign-review.json').read_text())
                sign['sign_code']='other'
                (copy/'sign-review.json').write_text(json.dumps(sign)+'\n')
                print(json.dumps(audit(left,copy),sort_keys=True))
                return
        print(json.dumps(audit(left,right),sort_keys=True))
        return
    if not args.left or not args.right:
        raise ValueError('Both original attempts required')
    result=audit(args.left,args.right)
    result['original_native_observed']=True
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':
    main()
