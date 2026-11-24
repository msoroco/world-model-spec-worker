"""Build exact unselected turn-signal offline constructions."""
import hashlib
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
BASE=HERE.parent.name+'__selected_c8ca9085__condition_'
RUNNER='''import argparse
import json
from pathlib import Path

def check(c):
    base="training__C42417__NRS-484B-413-2__motor_vehicle_driver__selected_c8ca9085__condition_"
    expected={base+"a":40,base+"b":20}
    case=c.get("case_id")
    if case not in expected or c.get("selected_case_id")!=case:raise ValueError("Exact case differs")
    if (c.get("law_id"),c.get("cell_id"),c.get("actor"))!=("NRS-484B-413-2","C42417","motor_vehicle_driver"):raise ValueError("Assignment differs")
    if (c.get("rate_hz"),c.get("duration_s"),c.get("duration_frames"))!=(20,30,600):raise ValueError("Full window required")
    if [x.get("name") for x in c.get("cameras",[])]!=["overview","approach","reference_corner","driver_reference"]:raise ValueError("Four cameras required")
    if any(x.get("fps")!=20 or x.get("width",0)<16 or x.get("height",0)<16 for x in c["cameras"]):raise ValueError("Camera cadence/dimensions differ")
    if c.get("layout")!="business_district" or c.get("maneuver")!="right_turn" or c.get("precipitation")!="rain":raise ValueError("Fixed scene differs")
    if c.get("turn_onset_frame")!=300 or c.get("speed_mps")!=10 or c.get("signal_distance_m")!=expected[case]:raise ValueError("Signal-distance comparison differs")
    if c.get("observed_indicator_required") is not True or c.get("physical_verified") is not False or c.get("legal_verdict") is not None:raise ValueError("Source or legal claim differs")
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
    def test_changed_distance(self):
        c=copy.deepcopy(self.c);c["signal_distance_m"]+=1
        with self.assertRaisesRegex(ValueError,"Signal-distance"):check(c)
    def test_wrong_district(self):
        c=copy.deepcopy(self.c);c["layout"]="other_area"
        with self.assertRaisesRegex(ValueError,"Fixed scene"):check(c)
'''
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def build():
    entries=[]
    for suffix,distance in (('a',40),('b',20)):
        case=BASE+suffix
        c={'case_id':case,'selected_case_id':case,'law_id':'NRS-484B-413-2','cell_id':'C42417',
           'actor':'motor_vehicle_driver','rate_hz':20,'duration_s':30,'duration_frames':600,
           'cameras':[{'name':n,'fps':20,'width':w,'height':h} for n,w,h in (
               ('overview',1920,1080),('approach',1280,720),('reference_corner',1280,720),('driver_reference',1280,720))],
           'layout':'business_district','maneuver':'right_turn','precipitation':'rain',
           'turn_onset_frame':300,'speed_mps':10,'signal_distance_m':distance,
           'observed_indicator_required':True,'physical_verified':False,'legal_verdict':None}
        construction={'format':'worker-inline-construction','case_id':case,'cell_id':'C42417','actor':'motor_vehicle_driver',
                      'entrypoint':'runner.py','files':[{'path':'config.json','content':json.dumps(c,indent=2)+'\n'},
                                                    {'path':'runner.py','content':RUNNER},{'path':'tests/test_offline.py','content':TESTS}],
                      'recording_description':{'channels':[{'name':n,'method':m,'sampling_rate_hz':20,'time_window':'600 frames'} for n,m in (
                          ('raw_ego_path_and_heading','original ego transform/heading'),
                          ('observed_turn_indicator','original lamp-state or image readback'),
                          ('four_camera_video','four named original camera streams'))],
                          'limitations':['Native turn motion and actual indicator pixels unverified']},
                      'status':'exact_unselected_offline_draft'}
        p=HERE/('condition_'+suffix+'-construction.json');p.write_text(json.dumps(construction,indent=2)+'\n')
        entries.append({'case_id':case,'construction':p.name,'construction_sha256':sha(p)})
    m={'format':'draft-execution-manifest','cases':entries}
    (HERE/'draft-manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    return m
if __name__=='__main__':print(json.dumps(build(),indent=2))
