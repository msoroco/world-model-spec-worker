"""Build exact, unselected angle-parking offline constructions."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent.name
CASES = {"condition_a": 45.0, "condition_b": 70.0}
RUNNER = '''import argparse
import json
from pathlib import Path

def check(config):
    base="training__C385967__NRS-484B-460__motor_vehicle_driver__selected_03f318de__condition_"
    expected={base+"a":45.0,base+"b":70.0}
    case=config.get("case_id")
    if case not in expected or config.get("selected_case_id")!=case:
        raise ValueError("Exact case identity differs")
    if (config.get("law_id"),config.get("cell_id"),config.get("actor"))!=(
            "NRS-484B-460","C385967","motor_vehicle_driver"):
        raise ValueError("Law/cell/actor identity differs")
    if (config.get("rate_hz"),config.get("duration_s"),config.get("duration_frames"))!=(20,30,600):
        raise ValueError("Full 30-second source window required")
    if [c.get("name") for c in config.get("cameras",[])]!=[
            "overview","approach","reference_corner","driver_reference"]:
        raise ValueError("Four source cameras required")
    if any(c.get("fps")!=20 or c.get("width",0)<16 or c.get("height",0)<16
           for c in config["cameras"]):
        raise ValueError("Camera cadence or dimensions differ")
    if config.get("parked_heading_request_deg")!=expected[case]:
        raise ValueError("Controlled parked heading differs")
    if config.get("device_indicated_angle_deg")!=45 or config.get("curb_heading_deg")!=0:
        raise ValueError("Device/curb reference differs")
    if config.get("standing_from_s")!=12 or config.get("space_id")!="angle_space_1":
        raise ValueError("At-rest space contract differs")
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
    def test_changed_heading(self):
        bad=copy.deepcopy(self.config);bad["parked_heading_request_deg"]+=1
        with self.assertRaisesRegex(ValueError,"parked heading"):check(bad)
    def test_missing_device_angle(self):
        bad=copy.deepcopy(self.config);bad["device_indicated_angle_deg"]=None
        with self.assertRaisesRegex(ValueError,"Device/curb"):check(bad)
'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    entries=[]
    for condition, heading in CASES.items():
        case=ASSIGNMENT+"__selected_03f318de__"+condition
        config={"case_id":case,"selected_case_id":case,"law_id":"NRS-484B-460",
                "cell_id":"C385967","actor":"motor_vehicle_driver",
                "rate_hz":20,"duration_s":30,"duration_frames":600,
                "cameras":[{"name":n,"fps":20,"width":w,"height":h} for n,w,h in (
                    ("overview",1920,1080),("approach",1280,720),
                    ("reference_corner",1280,720),("driver_reference",1280,720))],
                "parked_heading_request_deg":heading,"device_indicated_angle_deg":45,
                "curb_heading_deg":0,"standing_from_s":12,"space_id":"angle_space_1",
                "physical_verified":False,"legal_verdict":None}
        construction={"format":"worker-inline-construction","case_id":case,
                      "cell_id":"C385967","actor":"motor_vehicle_driver",
                      "entrypoint":"runner.py","files":[
                          {"path":"config.json","content":json.dumps(config,indent=2)+"\n"},
                          {"path":"runner.py","content":RUNNER},
                          {"path":"tests/test_offline.py","content":TESTS}],
                      "recording_description":{"channels":[
                          {"name":"raw_ego_heading_and_speed","method":"original actor transform/velocity",
                           "sampling_rate_hz":20,"time_window":"600 frames"},
                          {"name":"angle_device_and_curb","method":"original sign, space and road-edge geometry",
                           "sampling_rate_hz":20,"time_window":"600 frames"},
                          {"name":"four_camera_video","method":"four named source streams",
                           "sampling_rate_hz":20,"time_window":"600 frames"}],
                          "limitations":["Native sign/curb geometry, parking motion and original pixels unverified"]},
                      "status":"exact_unselected_offline_draft"}
        path=HERE/(condition+"-construction.json")
        path.write_text(json.dumps(construction,indent=2)+"\n")
        entries.append({"case_id":case,"construction":path.name,"construction_sha256":sha(path)})
    manifest={"format":"draft-execution-manifest","cases":entries}
    (HERE/"draft-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    return manifest


if __name__=="__main__":print(json.dumps(build(),indent=2))
