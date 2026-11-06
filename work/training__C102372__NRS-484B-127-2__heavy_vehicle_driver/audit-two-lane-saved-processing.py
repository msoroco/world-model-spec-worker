"""Independent raw-source audit of the 480-frame two-lane saved finalizer."""
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from finalize import finalize
from measure_gap import sha

spec=importlib.util.spec_from_file_location('fixture',HERE/'prove-two-lane-saved-processing.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
os.environ['PATH']=str(ROOT/'.runtime-work/linux_arm64')+os.pathsep+os.environ.get('PATH','')

with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c102372-two-lane-saved-audit-') as temporary:
    root=fixture.make_source(Path(temporary)/'source')
    finalize(root,root/'analysis-report.json')
    result=json.loads((root/'result.json').read_text())
    report=json.loads((root/'analysis-report.json').read_text())
    capture=json.loads((root/'capture/manifest.json').read_text())
    if capture['sources']['road.xodr']!=sha(root/'road.xodr'):
        raise AssertionError('Capture/road source hash differs')
    rows={name:[json.loads(line) for line in (root/name).read_text().splitlines()]
          for name in ('native_samples.jsonl','trace.jsonl','capture/evidence.jsonl','video_frames.jsonl')}
    if any(len(group)!=480 for group in rows.values()):raise AssertionError('Full saved joins absent')
    for index,(native,trace,evidence,join) in enumerate(zip(*rows.values())):
        frame=native['carla_frame']
        if (native['native_frame'],trace['frame'],evidence['original_frame'],
            join['native_frame'],join['carla_frame'])!=(index,frame,frame,index,frame):
            raise AssertionError('Independent saved frame join differs')
    road=ET.parse(root/'road.xodr').getroot().find('road')
    lanes=road.findall('lanes/laneSection/right/lane')
    if [(int(l.get('id')),float(l.find('width').get('a'))) for l in lanes]!=[(-1,4.),(-2,4.)]:
        raise AssertionError('Independent two-lane road differs')
    profile=road.findall('elevationProfile/elevation')
    def distance(row):
        start=max(x for x,_ in row['ego']['body_xy_m'])
        end=min(x for x,_ in row['lead']['body_xy_m'])
        count=math.ceil((end-start)/.1);step=(end-start)/count;total=0
        for index in range(count):
            station=start+(index+.5)*step
            segment=max((p for p in profile if float(p.get('s'))<=station),
                        key=lambda p:float(p.get('s')))
            u=station-float(segment.get('s'))
            slope=float(segment.get('b'))+2*float(segment.get('c'))*u+3*float(segment.get('d'))*u*u
            total+=math.hypot(1,slope)*step
        return total
    minimum=min(distance(row) for row in rows['native_samples.jsonl'])
    measured=report['measurements']['truck_following_gap']['value']
    if abs(minimum-measured['min_surface_gap_m'])>.002 or measured['relation_to_500ft']!='below':
        raise AssertionError('Independent two-lane road-arc gap differs')
    for name in ('overview','ego_forward','lead_gap','crest_context'):
        p=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
            '-show_entries','stream=nb_read_frames','-of','default=noprint_wrappers=1:nokey=1',
            str(root/(name+'.mkv'))],capture_output=True,text=True,check=True)
        if p.stdout.strip()!='480':raise AssertionError('Independent video frame count differs')
    if result['accepted'] or result['provenance_kind']!='synthetic_cpu' or result['legal_verdict_claimed']:
        raise AssertionError('Two-lane saved result claims physical acceptance')
    print(json.dumps({'passed':True,'frames':480,'four_videos_decoded':True,
        'minimum_surface_gap_m':round(minimum,6),'physical_or_accepted_claim':False},sort_keys=True))
