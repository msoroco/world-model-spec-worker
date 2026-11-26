"""Build exact unselected turn-signal offline constructions."""
import hashlib
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
BASE=HERE.parent.name+'__probe_'
RUNNER='''import argparse
import json
from pathlib import Path
from capture import check as capture_check, capture

def check(c):
    base="training__C42387__NRS-484B-413-2__motor_vehicle_driver__probe_"
    expected={base+"a":35,base+"b":20,base+"c":30.48}
    case=c.get("case_id")
    if case not in expected or c.get("selected_case_id")!=case:raise ValueError("Exact case differs")
    if (c.get("law_id"),c.get("cell_id"),c.get("actor"))!=("NRS-484B-413-2","C42387","motor_vehicle_driver"):raise ValueError("Assignment differs")
    if (c.get("rate_hz"),c.get("duration_s"),c.get("duration_frames"))!=(20,30,600):raise ValueError("Full window required")
    if [x.get("name") for x in c.get("cameras",[])]!=["overview","approach","reference_corner","driver_reference"]:raise ValueError("Four cameras required")
    if any(x.get("fps")!=20 or x.get("width",0)<16 or x.get("height",0)<16 for x in c["cameras"]):raise ValueError("Camera cadence/dimensions differ")
    if c.get("layout")!="business_district" or c.get("maneuver")!="right_turn" or c.get("precipitation")!="clear":raise ValueError("Fixed scene differs")
    if c.get("turn_onset_frame")!=300 or c.get("speed_mps")!=10 or c.get("signal_distance_m")!=expected[case]:raise ValueError("Signal-distance comparison differs")
    if c.get("controller_lookahead_base_m") not in (4.0,2.5):raise ValueError("Unknown controller candidate")
    if c.get("observed_indicator_required") is not True or c.get("physical_verified") is not False or c.get("legal_verdict") is not None:raise ValueError("Source or legal claim differs")
    return capture_check(c)
if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--check",action="store_true")
    ap.add_argument("--output-dir");ap.add_argument("--host");ap.add_argument("--port",type=int);a=ap.parse_args()
    config=json.loads(Path("config.json").read_text())
    if a.check:print(json.dumps(check(config),sort_keys=True))
    else:
        if not (a.output_dir and a.host and a.port):ap.error("Original capture needs --output-dir, --host and --port")
        print(json.dumps(capture(config,Path(a.output_dir),a.host,a.port),sort_keys=True))
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
def description():
    names=('sig.turn_indicator','sig.hand_signal','drv.distance_while',
           'kin.path_length','drv.turning','drv.lane_change','env.precipitation',
           'kin.speed','native_body_pose_control','other_vehicle_pose','camera_frame_join')
    return {'channels':[{'name':name,'unit':'structured','sampling_rate_hz':20,
        'method':'Retain original Native source and synchronized frame for saved verification',
        'time_window':'entire 30 s / 600-frame attempt',
        'reference_frame':'original Native frame and time',
        'uncertainty':'50 ms sampled state; district and lamp pixels require review'}
        for name in names],
        'context_inputs':[{'name':'area_classification','unit':'categorical',
            'method':'authored business-district context joined to surveyed Native map; review pending'}],
        'limitations':['No legal conclusion from offline or synthetic data',
                       'Original district, body, lamp pixels and four cameras require review']}
def build():
    entries=[]
    for suffix,distance in (('a',35),('b',20),('c',30.48)):
        case=BASE+suffix
        c={'case_id':case,'selected_case_id':case,'law_id':'NRS-484B-413-2','cell_id':'C42387',
           'actor':'motor_vehicle_driver','rate_hz':20,'duration_s':30,'duration_frames':600,
           'cameras':[{'name':n,'fps':20,'width':w,'height':h} for n,w,h in (
               ('overview',1920,1080),('approach',1280,720),('reference_corner',1280,720),('driver_reference',1280,720))],
           'layout':'business_district','maneuver':'right_turn','precipitation':'clear',
           'turn_onset_frame':300,'speed_mps':10,'signal_distance_m':distance,
           'controller_lookahead_base_m':4.0,
           'observed_indicator_required':True,'physical_verified':False,'legal_verdict':None,
           'required_atoms':['sig.turn_indicator','kin.heading','kin.speed'],
           'source_packets':[], 'recording_description':description(),
           'supported_case_ids':[BASE+'a',BASE+'b',BASE+'c'],
           'case':{'case_id':case,'recording_description':description()}}
        construction={'format':'worker-inline-construction','case_id':case,'cell_id':'C42387','actor':'motor_vehicle_driver',
                      'entrypoint':'runner.py','files':[{'path':'config.json','content':json.dumps(c,indent=2)+'\n'},
                                                    {'path':'runner.py','content':RUNNER},{'path':'tests/test_offline.py','content':TESTS}]
                      + [{'path':name,'content':(HERE/name).read_text()} for name in
                         ('capture.py','geometry.py','controller.py','cameras.py','measure_observed.py','saved_measure.py','physical_preparation.py','finalize.py')],
                      'recording_description':description(),
                      'status':'exact_unselected_offline_draft'}
        p=HERE/('condition_'+suffix+'-construction.json');p.write_text(json.dumps(construction,indent=2)+'\n')
        fallback=json.loads(json.dumps(construction))
        fallback_config=json.loads(fallback['files'][0]['content'])
        fallback_config['controller_lookahead_base_m']=2.5
        fallback['files'][0]['content']=json.dumps(fallback_config,indent=2)+'\n'
        fallback['status']='exact_unselected_offline_fallback_draft'
        alternate=HERE/('condition_'+suffix+'-fallback1-construction.json')
        alternate.write_text(json.dumps(fallback,indent=2)+'\n')
        entries.append({'case_id':case,'construction':p.name,'construction_sha256':sha(p),
            'candidates':[{'id':'fallback1','construction':alternate.name,
                'construction_sha256':sha(alternate)}]})
    m={'format':'draft-execution-manifest','cases':entries}
    (HERE/'draft-manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    return m
if __name__=='__main__':print(json.dumps(build(),indent=2))
