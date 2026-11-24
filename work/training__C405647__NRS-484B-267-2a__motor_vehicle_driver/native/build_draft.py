"""Build exact unselected emergency-approach offline packages."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent.name+'__selected_d6045110__condition_'
RUNNER='''import argparse
import json
from pathlib import Path

def check(c):
    base="training__C405647__NRS-484B-267-2a__motor_vehicle_driver__selected_d6045110__condition_"
    expected={base+"a":"reduce_speed",base+"b":"maintain_speed"}
    case=c.get("case_id")
    if case not in expected or c.get("selected_case_id")!=case:raise ValueError("Exact case differs")
    if (c.get("law_id"),c.get("cell_id"),c.get("actor"))!=("NRS-484B-267-2a","C405647","motor_vehicle_driver"):raise ValueError("Assignment differs")
    if (c.get("rate_hz"),c.get("duration_s"),c.get("duration_frames"))!=(20,30,600):raise ValueError("Full window required")
    if [x.get("name") for x in c.get("cameras",[])]!=["overview","approach","reference_corner","driver_reference"]:raise ValueError("Four cameras required")
    if any(x.get("fps")!=20 or x.get("width",0)<16 or x.get("height",0)<16 for x in c["cameras"]):raise ValueError("Camera cadence/dimensions differ")
    if c.get("condition")!=expected[case]:raise ValueError("Controlled speed condition differs")
    if c.get("other_vehicle_kind")!="authorized_emergency_vehicle" or c.get("other_vehicle_speed_mps")!=2:raise ValueError("Moving emergency vehicle differs")
    if c.get("warning_lamps")!="qualifying_flashing_request" or c.get("officer_direction") is not None:raise ValueError("Lamp or officer condition differs")
    if c.get("ego_initial_speed_mps")!=14 or c.get("ego_target_speed_mps")!=(7 if expected[case]=="reduce_speed" else 14):raise ValueError("Speed intervention differs")
    if c.get("posted_limit_mps")!=15 or c.get("visibility_m")!=200 or c.get("wet_road") is not False:raise ValueError("Reasonable-speed context differs")
    if c.get("physical_verified") is not False or c.get("legal_verdict") is not None:raise ValueError("Physical or legal result claimed")
    return {"case_id":case,"frames":600,"simulation_started":False,"selected_for_delivery":False}

if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--check",action="store_true");a=ap.parse_args()
    if not a.check:raise SystemExit("Native capture and saved processing not implemented")
    print(json.dumps(check(json.loads(Path("config.json").read_text())),sort_keys=True))
'''
TESTS='''import copy
import json
import unittest
from pathlib import Path
from runner import check
class DraftContract(unittest.TestCase):
    def setUp(self):self.c=json.loads(Path("config.json").read_text())
    def test_window(self):self.assertEqual(check(self.c)["frames"],600)
    def test_missing_camera(self):
        c=copy.deepcopy(self.c);c["cameras"].pop()
        with self.assertRaisesRegex(ValueError,"Four cameras"):check(c)
    def test_short_window(self):
        c=copy.deepcopy(self.c);c["duration_frames"]=599
        with self.assertRaisesRegex(ValueError,"Full window"):check(c)
    def test_lamps(self):
        c=copy.deepcopy(self.c);c["warning_lamps"]=None
        with self.assertRaisesRegex(ValueError,"Lamp"):check(c)
    def test_speed(self):
        c=copy.deepcopy(self.c);c["ego_target_speed_mps"]+=1
        with self.assertRaisesRegex(ValueError,"Speed intervention"):check(c)
'''

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def build():
    entries=[]
    for suffix,condition in (('a','reduce_speed'),('b','maintain_speed')):
        case=BASE+suffix
        config={'case_id':case,'selected_case_id':case,'law_id':'NRS-484B-267-2a','cell_id':'C405647',
                'actor':'motor_vehicle_driver','rate_hz':20,'duration_s':30,'duration_frames':600,
                'cameras':[{'name':n,'fps':20,'width':w,'height':h} for n,w,h in (
                    ('overview',1920,1080),('approach',1280,720),('reference_corner',1280,720),('driver_reference',1280,720))],
                'condition':condition,'other_vehicle_kind':'authorized_emergency_vehicle','other_vehicle_speed_mps':2,
                'warning_lamps':'qualifying_flashing_request','officer_direction':None,
                'ego_initial_speed_mps':14,'ego_target_speed_mps':7 if suffix=='a' else 14,
                'posted_limit_mps':15,'visibility_m':200,'wet_road':False,
                'physical_verified':False,'legal_verdict':None}
        construction={'format':'worker-inline-construction','case_id':case,'cell_id':'C405647','actor':'motor_vehicle_driver',
                      'entrypoint':'runner.py','files':[{'path':'config.json','content':json.dumps(config,indent=2)+'\n'},
                                                    {'path':'runner.py','content':RUNNER},{'path':'tests/test_offline.py','content':TESTS}],
                      'recording_description':{'channels':[{'name':n,'method':m,'sampling_rate_hz':20,'time_window':'600 frames'} for n,m in (
                          ('ego_speed_and_transform','original ego actor velocity/transform'),
                          ('emergency_actor_and_lamps','original actor transform and lamp state'),
                          ('four_camera_video','four named original camera streams'))],
                          'limitations':['Original lamps, vehicle classification, visibility, reasonable-speed judgment and pixels unverified']},
                      'status':'exact_unselected_offline_draft'}
        p=HERE/('condition_'+suffix+'-construction.json');p.write_text(json.dumps(construction,indent=2)+'\n')
        entries.append({'case_id':case,'construction':p.name,'construction_sha256':sha(p)})
    manifest={'format':'draft-execution-manifest','cases':entries}
    (HERE/'draft-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest
if __name__=='__main__':print(json.dumps(build(),indent=2))
