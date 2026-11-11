"""Materialize current-runtime, unselected source-bound right-exit constructions."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'offline/bundles'
DEST=ROOT/'current-runtime-drafts'
NAMES=('capture.py','check.py','config.json','assignment-source.json',
       'case-plan.json','right-exit-road.xodr','requested-tracks.jsonl',
       'measurement-contract.json')
TEST='''import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from capture import check_capture

class TestRightExitSource(unittest.TestCase):
    def test_source_and_camera_profile(self):
        value=check_capture(Path(__file__).resolve().parents[1])
        self.assertEqual(value['camera_names'],
            ['overview','approach','reference_corner','driver_reference'])
        self.assertEqual(value['requested_phases'],['circulation','entry','exit'])
        self.assertFalse(value['original_native_observed'])
'''

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

cases=[]
for witness in ('reference','contrast'):
    entries=[]
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        source=SOURCE/witness/candidate
        files=[{'path':name,'content':(source/name).read_text()} for name in NAMES]
        files.append({'path':'tests/test_capture.py','content':TEST})
        proposal={'case_id':ROOT.name+'__'+witness,'law_id':'LVMC-11-43-010-C2',
                  'cell_id':'C132497','actor':'motor_vehicle_driver',
                  'entrypoint':'capture.py','files':files,
                  'status':'unselected_cpu_draft',
                  'original_native_observed':False,'delivery_ready':False}
        target=DEST/witness/candidate/'construction.json'
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(proposal,indent=2)+'\n')
        entries.append({'id':candidate,'construction':str(target.relative_to(ROOT)),
                        'construction_sha256':sha(target)})
    cases.append({'case_id':ROOT.name+'__'+witness,
                  'construction':entries[0]['construction'],
                  'construction_sha256':entries[0]['construction_sha256'],
                  'candidate_risk':{'status':'physical',
                      'reason':'Full roundabout, original route, lane occupancy and pixels unverified'},
                  'candidates':[{'id':entry['id'],
                                 'construction':entry['construction'],
                                 'construction_sha256':entry['construction_sha256'],
                                 'trigger':{'source':'saved Native rows',
                                            'metric':{'fallback1':'lane_center_deviation_m',
                                                      'fallback2':'first_40_visible_frames',
                                                      'fallback3':'first_40_stopped_frames'}[entry['id']],
                                            'failure_condition':{'fallback1':'> 0.2 m',
                                                                 'fallback2':'< 20 frames',
                                                                 'fallback3':'< 20 frames'}[entry['id']]},
                                 'changed_knobs':[{'fallback1':'requested_speed_mps',
                                                   'fallback2':'camera_policy',
                                                   'fallback3':'pre_entry_dwell_s'}[entry['id']]]}
                                for entry in entries[1:]]})
manifest={'format':'worker-unselected-current-runtime-offline-v1',
          'assignment_id':ROOT.name,'status':'draft_not_selected',
          'cases':cases,'original_native_observed':False,'delivery_ready':False}
path=ROOT/'draft-current-runtime-manifest.json'
path.write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'cases':len(cases),'constructions':8,'manifest_sha256':sha(path)}))
