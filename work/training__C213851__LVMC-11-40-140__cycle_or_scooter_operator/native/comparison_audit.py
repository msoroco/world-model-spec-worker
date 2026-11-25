"""Independently compare stop/yield and roll-through at one reviewed sidewalk."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from finalize_sidewalk import measure

AID=HERE.name
FIXED=('district','district_source_id','origin_kind','origin_source_id','travel_direction',
    'sidewalk_continuation_across_origin','sidewalk_continuation_source_id',
    'sidewalk_boundary_source_id','rider_class','rider_class_source_id',
    'pedestrian_conflict_source_id','sidewalk_boundary_point_xyz_m',
    'sidewalk_approach_direction_xyz','pedestrian_conflict_polygon_xy_m',
    'camera_sha256')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare(left,right,diagnostic=False,negative=False):
    left,right=Path(left),Path(right)
    first,second=measure(left),measure(right)
    context=[json.loads((root/'sidewalk_context.json').read_text()) for root in (left,right)]
    expected='synthetic_diagnostic' if diagnostic else 'original_source_review'
    if any(item.get('review_kind')!=expected for item in context):
        raise ValueError('Original source sidewalk comparison review absent')
    if context[0].get('case_id')!=AID+'__probe_01' or context[1].get('case_id')!=AID+'__probe_02':
        raise ValueError('Sidewalk comparison case identity differs')
    if negative:
        context[1]['sidewalk_continuation_source_id']='changed-source'
    if any(context[0].get(key)!=context[1].get(key) for key in FIXED):
        raise ValueError('Fixed district, driveway, sidewalk or pedestrian context differs')
    if first['frame_count']!=600 or second['frame_count']!=600:
        raise ValueError('Full Native sidewalk comparison missing')
    if not first['pre_entry_near_zero_frames'] or second['pre_entry_near_zero_frames']:
        raise ValueError('Measured stop versus roll-through contrast absent')
    if first['pedestrian_on_crossing_at_entry'] or not second['pedestrian_on_crossing_at_entry']:
        raise ValueError('Measured pedestrian conflict timing contrast absent')
    return {'format':'worker-lvmc-sidewalk-stop-yield-comparison-v1',
        'comparison_id':AID+'__stop_yield_comparison',
        'case_ids':[AID+'__probe_01',AID+'__probe_02'],'passed':True,
        'diagnostic_fixture':diagnostic,'physical_acceptance_claimed':False,
        'legal_verdict_claimed':False,'fixed_conditions_checked':list(FIXED),
        'deliberate_difference':'source-measured pre-sidewalk stop and pedestrian conflict timing',
        'source_sha256':{suffix:{name:sha(root/name) for name in
            ('video_frames.jsonl','sidewalk-native.jsonl','sidewalk_context.json')}
            for suffix,root in (('probe_01',left),('probe_02',right))},
        'measurements':{'probe_01':first,'probe_02':second}}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--left',required=True)
    parser.add_argument('--right',required=True)
    parser.add_argument('--diagnostic',action='store_true')
    parser.add_argument('--negative-selftest',action='store_true')
    args=parser.parse_args()
    print(json.dumps(compare(args.left,args.right,args.diagnostic,args.negative_selftest),sort_keys=True))


if __name__=='__main__':
    main()
