"""Independently compare source-measured path and roadway occupancy."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_path import measure

AID='training__C230224__LVMC-11-40-120__cycle_or_scooter_operator'
FIXED=('device_subtype','path_continuous','path_adjacent','path_usable_reviewed',
       'path_polygon_xy_m','roadway_polygon_xy_m','path_obstruction_polygon_xy_m',
       'device_subtype_source','rider_identity_source','path_surface_source',
       'path_continuity_source','path_adjacency_source','path_obstruction_source',
       'path_usability_review_source','roadway_boundary_source')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare(left,right,diagnostic=False,negative=False):
    left,right=Path(left),Path(right)
    first,second=measure(left),measure(right)
    context=[json.loads((root/'path_context.json').read_text()) for root in (left,right)]
    expected='synthetic_diagnostic' if diagnostic else 'original_source_review'
    if any(item['review_kind']!=expected for item in context):
        raise ValueError('Original source comparison review absent')
    if context[0].get('case_id')!=AID+'__probe_01' or context[1].get('case_id')!=AID+'__probe_02':
        raise ValueError('Comparison case identity differs')
    if negative:
        context[1]['path_usable_reviewed']=False
    if any(context[0].get(key)!=context[1].get(key) for key in FIXED):
        raise ValueError('Fixed adjacent path, device or rider context differs')
    if context[0]['path_usable_reviewed'] is not True or context[0]['path_adjacent'] is not True:
        raise ValueError('Usable adjacent path source review missing')
    if first['moving_frame_count']!=600 or second['moving_frame_count']!=600:
        raise ValueError('Full moving-frame comparison missing')
    if first['path_occupancy_moving_frames']!=600 or first['roadway_occupancy_moving_frames']!=0:
        raise ValueError('Selected path-use occupancy not observed')
    if second['roadway_occupancy_moving_frames']!=600 or second['path_occupancy_moving_frames']!=0:
        raise ValueError('Selected roadway-use occupancy not observed')
    return {'format':'worker-lvmc-path-choice-comparison-v1','comparison_id':AID+'__path_choice',
        'case_ids':[AID+'__probe_01',AID+'__probe_02'],'passed':True,
        'diagnostic_fixture':diagnostic,'physical_acceptance_claimed':False,
        'legal_verdict_claimed':False,'fixed_conditions_checked':list(FIXED),
        'deliberate_difference':'measured rider/device footprint path versus roadway occupancy',
        'source_sha256':{'probe_01':{name:sha(left/name) for name in ('video_frames.jsonl','native_rider_trace.jsonl','path_context.json')},
                         'probe_02':{name:sha(right/name) for name in ('video_frames.jsonl','native_rider_trace.jsonl','path_context.json')}},
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
