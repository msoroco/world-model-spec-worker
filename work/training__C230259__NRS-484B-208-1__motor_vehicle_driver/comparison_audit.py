"""Independent source-bound paired audit of post-overtake left occupancy."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def one(root,case):
    root = Path(root)
    config = json.loads((root/'config.json').read_text())
    context = json.loads((root/'context.json').read_text())
    report = json.loads((root/'analysis-report.json').read_text())
    rows = [json.loads(line) for line in (root/'native-actors.jsonl').read_text().splitlines()]
    if config['case_id']!=case or len(rows)!=600 or any(
            row['frame']!=i for i,row in enumerate(rows)):
        raise ValueError('Incomplete or wrong exact comparison source')
    if any(row['source_kind']!='synthetic_native_sample' for row in rows):
        raise ValueError('Comparison provenance changed')
    if report.get('legal_verdict') is not None or context.get('legal_verdict') is not None:
        raise ValueError('Comparison cannot assign legal outcome')
    observed = report['left_lane_scope']
    return {'case_id':case,
        'requested_continuation':config['slow_extreme_left_lane_continuation'],
        'slow_left_after_overtake_frames':observed['slow_extreme_left_after_overtake_frames'],
        'overtake_crossing_frame':observed['overtake_crossing_frame'],
        'fixed_conditions_id':context['fixed_conditions_id'],
        'source_kind':context['source_kind'],
        'source_hashes':{name:sha(root/name) for name in
            ('config.json','context.json','native-actors.jsonl',
             'native-road-context.json','native-map-readback.json','analysis-report.json')}}


def audit(root_a,root_b,case_a,case_b,comparison):
    a,b = one(root_a,case_a),one(root_b,case_b)
    if (a['fixed_conditions_id']!=b['fixed_conditions_id'] or
            a['source_kind']!=b['source_kind'] or
            a['overtake_crossing_frame']!=b['overtake_crossing_frame']):
        raise ValueError('Comparison fixed conditions differ')
    if (a['requested_continuation'] is not True or
            b['requested_continuation'] is not False or
            a['slow_left_after_overtake_frames']<=0 or
            b['slow_left_after_overtake_frames']!=0):
        raise ValueError('Selected measured continuation contrast absent')
    return {'format':'c230259-independent-comparison-audit-v1',
        'comparison_id':comparison,'cases':[a,b],
        'deliberate_difference':'slow_extreme_left_lane_continuation',
        'observed_post_overtake_left_frames_delta':
            a['slow_left_after_overtake_frames']-b['slow_left_after_overtake_frames'],
        'diagnostic_fixture':True,'physical_acceptance':False,'legal_verdict':None,
        'limitations':['Authored posting, facility and driver notice remain unverified.',
                       'Observed lane occupancy does not decide subsection 2 exceptions.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('root-a','root-b','case-a','case-b','comparison','output'):
        parser.add_argument('--'+name,required=True)
    args = parser.parse_args()
    result = audit(args.root_a,args.root_b,args.case_a,args.case_b,args.comparison)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'comparison_id':args.comparison,
        'observed_post_overtake_left_frames_delta':
            result['observed_post_overtake_left_frames_delta'],
        'physical_acceptance':False}))
