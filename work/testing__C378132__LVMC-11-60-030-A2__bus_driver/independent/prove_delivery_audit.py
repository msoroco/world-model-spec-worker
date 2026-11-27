"""CPU test of original-shaped A2 audit joins; creates no original evidence."""
from __future__ import annotations
import argparse
import json
import tempfile
from pathlib import Path
from delivery_audit import ASSIGNMENT,VIEWS,CHECKS,sha,verify,locate

REPO=Path(__file__).resolve().parents[3]
ROOT=Path(__file__).resolve().parents[1]
SCRATCH=REPO/'.runtime-work/c378132-a2/delivery-audit-tests'


def write(path,value):
    path.write_text(json.dumps(value,sort_keys=True)+'\n')


def fixture(root,case):
    case_id=case['case_id'];suffix=case_id.split('__')[-1]
    source_folder=ROOT/'cases'/suffix/'diagnostic-sources'
    site=json.loads((source_folder/'site.json').read_text())
    native=json.loads((source_folder/'native.json').read_text())
    # Unit test supplies original-shaped source types; no real recording is claimed.
    site['source_class']='original_independent_review'
    write(root/'site.json',site);write(root/'native.json',native)
    write(root/'physical-source.json',{'test_only':True})
    rows=[{'video_frame':i,'time_s':i/20} for i in range(900)]
    (root/'video_frames.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
    for view in VIEWS:(root/(view+'.mkv')).write_bytes(('test-only-'+view).encode())
    source={'case_id':case_id,'passed':True,'source_kind':'original_native_capture','frames':900,
        'frame_map_sha256':sha(root/'video_frames.jsonl'),'native_sha256':sha(root/'native.json')}
    decode={'case_id':case_id,'passed':True,'videos':{view:{'frames':900,'sha256':sha(root/(view+'.mkv'))} for view in VIEWS}}
    physical={'case_id':case_id,'provenance_kind':'native','diagnostic_fixture':False,
        'maneuver_completed':True,'physical_checks':{name:{'status':'met',
        'sources':{'physical-source.json':sha(root/'physical-source.json')}} for name in ('setup','target','maneuver')}}
    pixels={'format':'worker-original-pixel-review','case_id':case_id,'diagnostic_fixture':False,
        'reviewer':'unit-test-only','frame_map_sha256':sha(root/'video_frames.jsonl'),
        'video_sha256':sha(root/'overview.mkv'),
        'observations':{name:{'visible':True,'view':'overview','frame':450,'description':'unit-test source join'}
                        for name in ('bus_body','location_boundary','public_street','designation_signs','loading_activity')}}
    activity={'case_id':case_id,'diagnostic_fixture':False,'reviewer':'unit-test-only',
        'frame_map_sha256':sha(root/'video_frames.jsonl'),
        'loading_purpose':case['loading_purpose'],'stop_reason':case['stop_reason'],
        'bus_class':case['bus_class'],'complete_interval':True,'interval_frames':[200,500]}
    designation={'case_id':case_id,'authority':'City Traffic Engineer','reviewer':'unit-test-only',
        'diagnostic_fixture':False,'signs_reviewed':True,
        'designated_locations':['bus_stop','bus_stand','passenger_loading_zone','route_origin','route_destination'],
        'assigned_route_reviewed':True,'frame_map_sha256':sha(root/'video_frames.jsonl'),
        'site_sha256':sha(root/'site.json')}
    core={'scenes':[{'t':i*50} for i in range(900)]}
    return case_id,source,decode,physical,pixels,activity,designation,core


def main():
    plan=json.loads((ROOT/'case-plan.json').read_text())
    cases={case['case_id']:case for case in plan['cases']}
    parser=argparse.ArgumentParser();parser.add_argument('case_id',choices=sorted(cases));parser.add_argument('--negative',action='store_true')
    args=parser.parse_args();SCRATCH.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='bus-a2-proof-',dir=SCRATCH) as name:
        root=Path(name);items=list(fixture(root,cases[args.case_id]))
        if args.negative:
            items[6]['signs_reviewed']=False
            verify(items[0],root,*items[1:])
            raise AssertionError('unreviewed designation accepted')
        audit=verify(items[0],root,*items[1:])
        if audit['checks']!={key:True for key in CHECKS}:
            raise AssertionError('delivery checks incomplete')
        items[5]['loading_purpose']='cargo_only' if items[5]['loading_purpose']!='cargo_only' else 'passenger'
        try:verify(items[0],root,*items[1:])
        except ValueError as error:
            if 'original purpose, exception or bus class differs' not in str(error):raise
        else:raise AssertionError('changed loading purpose accepted')
        print(args.case_id+': unit-test A2 source join and purpose rejection passed; no original capture claimed')


if __name__=='__main__':main()
