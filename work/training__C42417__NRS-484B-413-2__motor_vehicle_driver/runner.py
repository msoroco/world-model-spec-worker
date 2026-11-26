import argparse
import json
from pathlib import Path
from capture import check as capture_check, capture

def check(c):
    base="training__C42417__NRS-484B-413-2__motor_vehicle_driver__selected_c8ca9085__condition_"
    expected={base+"a":40,base+"b":20,base+"c":30.48}
    case=c.get("case_id")
    if case not in expected or c.get("selected_case_id")!=case:raise ValueError("Exact case differs")
    if (c.get("law_id"),c.get("cell_id"),c.get("actor"))!=("NRS-484B-413-2","C42417","motor_vehicle_driver"):raise ValueError("Assignment differs")
    if (c.get("rate_hz"),c.get("duration_s"),c.get("duration_frames"))!=(20,30,600):raise ValueError("Full window required")
    if [x.get("name") for x in c.get("cameras",[])]!=["overview","approach","reference_corner","driver_reference"]:raise ValueError("Four cameras required")
    if any(x.get("fps")!=20 or x.get("width",0)<16 or x.get("height",0)<16 for x in c["cameras"]):raise ValueError("Camera cadence/dimensions differ")
    if c.get("layout")!="business_district" or c.get("maneuver")!="right_turn" or c.get("precipitation")!="rain":raise ValueError("Fixed scene differs")
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
