"""CPU wiring proof for independent original-source bus duration auditor."""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from delivery_audit import ASSIGNMENT,SUFFIXES,VIEWS,CHECKS,sha,verify

REPO=Path(__file__).resolve().parents[3]
SCRATCH=REPO/'.runtime-work/c393262-bus/delivery-audit-tests'


def fixture(root: Path, suffix: str):
    case_id=ASSIGNMENT+'__'+suffix
    (root/'physical-source.json').write_text('{"test_only":true}\n')
    rows=[{'video_frame':i,'time_s':i/20} for i in range(900)]
    (root/'video_frames.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
    for view in VIEWS:
        (root/(view+'.mkv')).write_bytes(('test-only-'+view).encode())
    source={'case_id':case_id,'passed':True,'source_kind':'original_native_capture','frames':900,'frame_map_sha256':sha(root/'video_frames.jsonl')}
    decode={'case_id':case_id,'passed':True,'videos':{view:{'frames':900,'sha256':sha(root/(view+'.mkv'))} for view in VIEWS}}
    physical={'case_id':case_id,'provenance_kind':'native','diagnostic_fixture':False,'maneuver_completed':True,
              'physical_checks':{name:{'status':'met','sources':{'physical-source.json':sha(root/'physical-source.json')}} for name in ('setup','target','maneuver')}}
    pixels={'format':'worker-original-pixel-review','case_id':case_id,'diagnostic_fixture':False,'reviewer':'test-only-reviewer',
            'frame_map_sha256':sha(root/'video_frames.jsonl'),'video_sha256':sha(root/'overview.mkv'),
            'observations':{name:{'visible':True,'view':'overview','frame':450,'description':'test-only join'} for name in ('bus_body','stop_boundary','residential_context','designation_signs')}}
    relation=suffix.split('_')[-1]
    measured={'below':13,'at':15,'above':17}[relation]
    activity={'case_id':case_id,'diagnostic_fixture':False,'reviewer':'test-only-reviewer','frame_map_sha256':sha(root/'video_frames.jsonl'),
              'conduct':suffix.split('_')[0],'complete_interval':True,'intervening_loading':False,'measured_duration_s':measured}
    designation={'case_id':case_id,'authority':'City Traffic Engineer','reviewer':'test-only-reviewer','diagnostic_fixture':False,
                 'applicable_duration_s':15,'conditions_reviewed':True,'frame_map_sha256':sha(root/'video_frames.jsonl')}
    core={'scenes':[{'t':i*50} for i in range(900)]}
    return case_id,source,decode,physical,pixels,activity,designation,core


def main():
    parser=argparse.ArgumentParser();parser.add_argument('case_id',choices=[ASSIGNMENT+'__'+s for s in SUFFIXES]);parser.add_argument('--negative',action='store_true')
    args=parser.parse_args();SCRATCH.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='bus-duration-proof-',dir=SCRATCH) as name:
        root=Path(name);e=list(fixture(root,args.case_id.removeprefix(ASSIGNMENT+'__')))
        if args.negative:
            e[6]['applicable_duration_s']=None
            verify(e[0],root,*e[1:])
            raise AssertionError('missing actual designated duration accepted')
        audit=verify(e[0],root,*e[1:])
        if audit['checks']!={key:True for key in CHECKS}:
            raise AssertionError('delivery checks incomplete')
        e[5]['intervening_loading']=True
        try:verify(e[0],root,*e[1:])
        except ValueError as error:
            if str(error)!='measured uninterrupted standing/parking interval missing':raise
        else:raise AssertionError('unreviewed loading interruption accepted')
        print(args.case_id+': diagnostic source-join audit passed; no original capture claimed')

if __name__=='__main__':main()
