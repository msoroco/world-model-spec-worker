"""Build exact unselected school crossing offline constructions."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent.name
BASE = ASSIGNMENT + "__selected_1290826d__condition_"
CASES = {"a": "entry_during_crossing", "b": "entry_after_crossing"}
RUNNER = '''import argparse
import json
from pathlib import Path

def check(config):
    base="training__C394563__LVMC-11-18-020__motor_vehicle_driver__selected_1290826d__condition_"
    expected={base+"a":"entry_during_crossing",base+"b":"entry_after_crossing"}
    case=config.get("case_id")
    if case not in expected or config.get("selected_case_id")!=case:
        raise ValueError("Exact case identity differs")
    if (config.get("law_id"),config.get("cell_id"),config.get("actor"))!=("LVMC-11-18-020","C394563","motor_vehicle_driver"):
        raise ValueError("Law/cell/actor identity differs")
    if (config.get("rate_hz"),config.get("duration_s"),config.get("duration_frames"))!=(20,30,600):
        raise ValueError("Full 30-second source window required")
    if [c.get("name") for c in config.get("cameras",[])]!=["overview","approach","reference_corner","driver_reference"]:
        raise ValueError("Four source cameras required")
    if any(c.get("fps")!=20 or c.get("width",0)<16 or c.get("height",0)<16 for c in config["cameras"]):
        raise ValueError("Camera cadence or dimensions differ")
    if config.get("condition")!=expected[case]:
        raise ValueError("Controlled entry condition differs")
    if config.get("school_xing_sign_x_m")!=-35 or config.get("crosswalk_x_m")!=0 or config.get("crosswalk_width_m")!=3.6576:
        raise ValueError("Sign/crosswalk source geometry differs")
    if config.get("pedestrian_crossing_interval_s")!=[10,14] or config.get("pedestrian_approach_side") is not True:
        raise ValueError("Same-side person interval differs")
    if config.get("ego_wait_interval_s")!=([10,14] if expected[case]=="entry_after_crossing" else []):
        raise ValueError("Ego release policy differs")
    if config.get("physical_verified") is not False or config.get("legal_verdict") is not None:
        raise ValueError("Physical or legal result claimed")
    return {"case_id":case,"frames":600,"simulation_started":False,"selected_for_delivery":False}

if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--check",action="store_true")
    args=parser.parse_args()
    if not args.check:raise SystemExit("Native capture and saved processing are not implemented")
    print(json.dumps(check(json.loads(Path("config.json").read_text())),sort_keys=True))
'''
TESTS = '''import copy
import json
import unittest
from pathlib import Path
from runner import check

class DraftContract(unittest.TestCase):
    def setUp(self):self.config=json.loads(Path("config.json").read_text())
    def test_exact_window(self):self.assertEqual(check(self.config)["frames"],600)
    def test_missing_camera(self):
        bad=copy.deepcopy(self.config);bad["cameras"].pop()
        with self.assertRaisesRegex(ValueError,"Four source cameras"):check(bad)
    def test_short_window(self):
        bad=copy.deepcopy(self.config);bad["duration_frames"]=599
        with self.assertRaisesRegex(ValueError,"30-second"):check(bad)
    def test_changed_sign(self):
        bad=copy.deepcopy(self.config);bad["school_xing_sign_x_m"]=-20
        with self.assertRaisesRegex(ValueError,"Sign/crosswalk"):check(bad)
    def test_missing_person(self):
        bad=copy.deepcopy(self.config);bad["pedestrian_approach_side"]=False
        with self.assertRaisesRegex(ValueError,"Same-side"):check(bad)
'''

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def build():
    entries=[]
    for suffix, condition in CASES.items():
        case=BASE+suffix
        config={"case_id":case,"selected_case_id":case,"law_id":"LVMC-11-18-020",
                "cell_id":"C394563","actor":"motor_vehicle_driver",
                "rate_hz":20,"duration_s":30,"duration_frames":600,
                "cameras":[{"name":n,"fps":20,"width":w,"height":h} for n,w,h in (
                    ("overview",1920,1080),("approach",1280,720),
                    ("reference_corner",1280,720),("driver_reference",1280,720))],
                "condition":condition,"school_xing_sign_x_m":-35,"crosswalk_x_m":0,
                "crosswalk_width_m":3.6576,"crosswalk_color":"yellow",
                "pedestrian_crossing_interval_s":[10,14],"pedestrian_approach_side":True,
                "ego_wait_interval_s":[10,14] if suffix=="b" else [],
                "physical_verified":False,"legal_verdict":None}
        construction={"format":"worker-inline-construction","case_id":case,
                      "cell_id":"C394563","actor":"motor_vehicle_driver",
                      "entrypoint":"runner.py","files":[
                          {"path":"config.json","content":json.dumps(config,indent=2)+"\n"},
                          {"path":"runner.py","content":RUNNER},
                          {"path":"tests/test_offline.py","content":TESTS}],
                      "recording_description":{"channels":[
                          {"name":"ego_front_entry","method":"original actor footprint and transform",
                           "sampling_rate_hz":20,"time_window":"600 frames"},
                          {"name":"person_crosswalk_sign","method":"original person transform and school crossing/sign geometry",
                           "sampling_rate_hz":20,"time_window":"600 frames"},
                          {"name":"four_camera_video","method":"four named original source streams",
                           "sampling_rate_hz":20,"time_window":"600 frames"}],
                          "limitations":["Native marking, sign authority, person intention and original pixels unverified"]},
                      "status":"exact_unselected_offline_draft"}
        path=HERE/("condition_"+suffix+"-construction.json")
        path.write_text(json.dumps(construction,indent=2)+"\n")
        entries.append({"case_id":case,"construction":path.name,"construction_sha256":sha(path)})
    manifest={"format":"draft-execution-manifest","cases":entries}
    (HERE/"draft-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    return manifest

if __name__=="__main__":print(json.dumps(build(),indent=2))
