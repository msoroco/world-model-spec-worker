"""CPU source-join proof for the original bus-stop auditor."""
from __future__ import annotations
import argparse
import json
import tempfile
from pathlib import Path
from delivery_audit import ASSIGNMENT,SUFFIXES,VIEWS,CHECKS,sha,verify

REPO=Path(__file__).resolve().parents[3]
SCRATCH=REPO/'.runtime-work/c386411-bus/delivery-audit-tests'
POLYGON=[[-42,-8],[-18,-8],[-18,0],[-42,0]]


def write(path,value):
    path.write_text(json.dumps(value,sort_keys=True)+'\n')


def fixture(root,suffix):
    case_id=ASSIGNMENT+'__'+suffix
    conduct,relation=suffix.split('_')
    write(root/'physical-source.json',{'test_only':True})
    rows=[{'video_frame':i,'time_s':i/20} for i in range(900)]
    (root/'video_frames.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
    for view in VIEWS:
        (root/(view+'.mkv')).write_bytes(('test-only-'+view).encode())
    center=[-30,-4] if relation=='inside' else [-30,-12]
    body=[[center[0]-4,center[1]-1],[center[0]+4,center[1]-1],
          [center[0]+4,center[1]+1],[center[0]-4,center[1]+1]]
    write(root/'site.json',{'source_class':'original_independent_review','cell_id':'C386411',
        'public_street':True,'stop_polygon_xy_m':POLYGON})
    write(root/'native.json',{'frames':[{'frame':i,'time_s':i/20,'bus_footprint_xy_m':body,
        'inside_stop_boundary':relation=='inside','outside_other_permitted_location':relation=='outside'}
        for i in range(900)]})
    source={'case_id':case_id,'passed':True,'source_kind':'original_native_capture','frames':900,
        'frame_map_sha256':sha(root/'video_frames.jsonl'),'native_sha256':sha(root/'native.json')}
    decode={'case_id':case_id,'passed':True,'videos':{view:{'frames':900,'sha256':sha(root/(view+'.mkv'))} for view in VIEWS}}
    physical={'case_id':case_id,'provenance_kind':'native','diagnostic_fixture':False,
        'maneuver_completed':True,'physical_checks':{name:{'status':'met',
        'sources':{'physical-source.json':sha(root/'physical-source.json')}} for name in ('setup','target','maneuver')}}
    pixels={'format':'worker-original-pixel-review','case_id':case_id,'diagnostic_fixture':False,
        'reviewer':'test-only-reviewer','frame_map_sha256':sha(root/'video_frames.jsonl'),
        'video_sha256':sha(root/'overview.mkv'),
        'observations':{name:{'visible':True,'view':'overview','frame':450,'description':'test-only source join'}
                        for name in ('bus_body','stop_boundary','public_street','designation_signs')}}
    activity={'case_id':case_id,'diagnostic_fixture':False,'reviewer':'test-only-reviewer',
        'frame_map_sha256':sha(root/'video_frames.jsonl'),'conduct':conduct,
        'complete_interval':True,'intervening_loading':False,'interval_frames':[200,500]}
    designation={'case_id':case_id,'authority':'City Traffic Engineer','reviewer':'test-only-reviewer',
        'diagnostic_fixture':False,'signed':True,'route_termini_reviewed':True,
        'other_permitted_locations_reviewed':True,'frame_map_sha256':sha(root/'video_frames.jsonl'),
        'site_sha256':sha(root/'site.json')}
    core={'scenes':[{'t':i*50} for i in range(900)]}
    return case_id,source,decode,physical,pixels,activity,designation,core


def main():
    parser=argparse.ArgumentParser();parser.add_argument('case_id',choices=[ASSIGNMENT+'__'+s for s in SUFFIXES]);parser.add_argument('--negative',action='store_true')
    args=parser.parse_args();SCRATCH.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='bus-stop-proof-',dir=SCRATCH) as name:
        root=Path(name);items=list(fixture(root,args.case_id.removeprefix(ASSIGNMENT+'__')))
        if args.negative:
            items[6]['signed']=False
            verify(items[0],root,*items[1:])
            raise AssertionError('unsigned stop designation accepted')
        audit=verify(items[0],root,*items[1:])
        if audit['checks']!={key:True for key in CHECKS}:
            raise AssertionError('delivery checks incomplete')
        items[5]['intervening_loading']=True
        try:verify(items[0],root,*items[1:])
        except ValueError as error:
            if str(error)!='complete standing/parking activity unverified':raise
        else:raise AssertionError('unreviewed activity interruption accepted')
        print(args.case_id+': source-join bus-stop audit passed; no original capture claimed')


if __name__=='__main__':main()
