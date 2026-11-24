"""Construct 30-second source-bound continuous-rotation diagnostic requests.

These are new unselected CPU drafts. The older 12-second Native requests and
their historical receipts remain intact for review.
"""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parents[1]
FRAMES = 600
RATE_HZ = 20
RADIUS_M = 23.75
SPEED_MPS = 8.0
START_RAD = -math.pi / 2

ENTRY = '''"""CPU source check for an unselected 30-second roundabout draft."""
import argparse
import hashlib
import json
import math
from pathlib import Path

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def check():
    root=Path.cwd();cfg=json.loads((root/'config.json').read_text())
    assignment=json.loads((root/'assignment-source.json').read_text())
    plan=json.loads((root/'case-plan.json').read_text())
    rows=[json.loads(x) for x in (root/'requested-tracks.jsonl').read_text().splitlines()]
    assert assignment['assignment_id']==plan['assignment_id']==cfg['assignment_id']
    assert assignment['law']['text']==plan['source_law']['text']
    assert assignment['local_snapshot']['law_sha256']==plan['source_law']['sha256']
    assert sha(root/'assignment-source.json')==cfg['assignment_sha256']
    assert sha(root/'case-plan.json')==cfg['case_plan_sha256']
    assert sha(root/'requested-tracks.jsonl')==cfg['tracks_sha256']
    assert cfg['frames']==600 and cfg['rate_hz']==20 and cfg['duration_s']==30
    assert cfg['cameras']=={'overview':[1920,1080],'approach':[1280,720],
                           'reference_corner':[1280,720],'driver_reference':[1280,720]}
    assert cfg['frozen_cell']==plan['frozen_cell']
    assert len(rows)==600
    direction=cfg['requested_rotation_sign']
    assert direction in (-1,1)
    last=None
    for i,row in enumerate(rows):
        theta=-math.pi/2+direction*8*(i+1)/20/23.75
        if row['frame']!=i or abs(row['time_s']-(i+1)/20)>1e-6:
            raise ValueError('Nonconsecutive 30-second frame clock')
        if abs(row['ego_x_m']-23.75*math.cos(theta))>1e-5 or abs(row['ego_y_m']-23.75*math.sin(theta))>1e-5:
            raise ValueError('Requested circular path altered')
        if row['ego_speed_mps']!=8 or row['requested_rotation_sign']!=direction:
            raise ValueError('Requested rotation control altered')
        if last is not None and (row['requested_unwrapped_angle_rad']-last)*direction<=0:
            raise ValueError('Requested rotation is not continuous')
        last=row['requested_unwrapped_angle_rad']
    return {'source_bound':True,'requested_frames':600,
            'continuous_requested_rotation':True,'native_executed':False,
            'original_native_observed':False,'delivery_ready':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    if not args.check:raise RuntimeError('30-second Native capture has not been integrated')
    print(json.dumps(check()))
'''

TEST = '''import json
import unittest
from pathlib import Path
from capture import check

class ExactDraft(unittest.TestCase):
    def test_source_bound(self):
        result=check()
        self.assertEqual(result['requested_frames'],600)
        self.assertTrue(result['continuous_requested_rotation'])
        self.assertFalse(result['original_native_observed'])
        self.assertFalse(result['delivery_ready'])

    def test_exact_direction(self):
        cfg=json.loads(Path('config.json').read_text())
        suffix=cfg['case_id'].rsplit('__',1)[-1]
        self.assertEqual(cfg['requested_rotation_sign'],1 if suffix=='witness_1' else -1)
'''


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')


def build():
    assignment=ROOT/'inputs'/CASE.name/'assignment.json'
    plan=CASE/'case-plan.json'
    plan_data=json.loads(plan.read_text())
    entries=[]
    for suffix,direction in (('witness_1',1),('witness_2',-1)):
        case_id=CASE.name+'__'+suffix
        folder=HERE/'30s'/suffix
        folder.mkdir(parents=True,exist_ok=True)
        rows=[]
        for frame in range(FRAMES):
            time_s=(frame+1)/RATE_HZ
            angle=START_RAD+direction*SPEED_MPS*time_s/RADIUS_M
            rows.append({'case_id':case_id,'frame':frame,'time_s':time_s,
                         'source_kind':'authored_native_request',
                         'ego_x_m':round(RADIUS_M*math.cos(angle),6),
                         'ego_y_m':round(RADIUS_M*math.sin(angle),6),
                         'ego_heading_deg':round(math.degrees(angle+direction*math.pi/2)%360,6),
                         'ego_speed_mps':SPEED_MPS,'requested_rotation_sign':direction,
                         'requested_unwrapped_angle_rad':round(angle,9),
                         'requested_radius_m':RADIUS_M,'island_center_xy_m':[0,0],
                         'roundabout_verified':False})
        tracks=folder/'requested-tracks.jsonl'
        tracks.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows))
        cfg={'format':'c234827-30-second-draft-v1','assignment_id':CASE.name,
             'case_id':case_id,'law_id':plan_data['law_id'],'cell_id':plan_data['cell_id'],
             'actor':plan_data['actor'],'frozen_cell':plan_data['frozen_cell'],
             'frames':FRAMES,'rate_hz':RATE_HZ,'duration_s':30,
             'cameras':{'overview':[1920,1080],'approach':[1280,720],
                        'reference_corner':[1280,720],'driver_reference':[1280,720]},
             'requested_rotation_sign':direction,'requested_speed_mps':SPEED_MPS,
             'requested_radius_m':RADIUS_M,
             'assignment_sha256':sha(assignment),'case_plan_sha256':sha(plan),
             'tracks_sha256':sha(tracks),'native_execution_integrated':False,
             'original_native_observed':False,'delivery_ready':False}
        write(folder/'config.json',cfg)
        files=[{'path':'capture.py','content':ENTRY},
               {'path':'tests/test_exact.py','content':TEST},
               {'path':'config.json','content':(folder/'config.json').read_text()},
               {'path':'requested-tracks.jsonl','content':tracks.read_text()},
               {'path':'assignment-source.json','content':assignment.read_text()},
               {'path':'case-plan.json','content':plan.read_text()}]
        proposal={'case_id':case_id,'law_id':plan_data['law_id'],
                  'cell_id':plan_data['cell_id'],'actor':plan_data['actor'],
                  'entrypoint':'capture.py','files':files,
                  'status':'unselected_cpu_diagnostic',
                  'recording_description':'Thirty seconds at 20 Hz and four source cameras requested; original Native rotation unobserved.'}
        path=folder/'construction.json';write(path,proposal)
        entries.append({'case_id':case_id,'construction':str(path.relative_to(CASE)),
                        'construction_sha256':sha(path),'candidates':[],
                        'candidate_risk':{'status':'physical',
                          'reason':'Original roundabout geometry, motion, lane retention and camera visibility remain unverified.'}})
    manifest={'format':'worker-unselected-draft-construction-manifest-v1',
              'assignment_id':CASE.name,'status':'draft_not_selected',
              'cases':entries,'original_native_observed':False,'delivery_ready':False}
    target=CASE/'draft-30s-execution-manifest.json';write(target,manifest)
    return target


if __name__=='__main__':print(build())
