import argparse
import json
from pathlib import Path
from capture import check as capture_check, execute as capture_execute
from finalize import finalize as finalize_saved

def check(config):
    base = "training__C329654__NRS-484B-253__motor_vehicle_driver__selected_d457f261__condition_"
    expected = {base+"a": ("yield_then_turn", 15.0), base+"b": ("turn_before_pass", 9.0)}
    case = config.get("case_id")
    if case not in expected or config.get("selected_case_id") != case:
        raise ValueError("Exact case identity differs")
    if (config.get("law_id"),config.get("cell_id"),config.get("actor")) != (
            "NRS-484B-253","C329654","motor_vehicle_driver"):
        raise ValueError("Law/cell/actor identity differs")
    if (config.get("rate_hz"),config.get("duration_s"),config.get("duration_frames")) != (20,30,600):
        raise ValueError("Full 30-second source window required")
    if [c.get("name") for c in config.get("cameras",[])] != [
            "overview","approach","reference_corner","driver_reference"]:
        raise ValueError("Four source cameras required")
    if any(c.get("fps") != 20 or c.get("width",0) < 16 or c.get("height",0) < 16
           for c in config["cameras"]):
        raise ValueError("Camera cadence or dimensions differ")
    if (config.get("yield_policy"),config.get("turn_release_s")) != expected[case]:
        raise ValueError("Controlled turn release differs")
    if config.get("oncoming_conflict_s") != 12.5 or config.get("left_signal_requested") is not True:
        raise ValueError("Opposing source or turn signal differs")
    if config.get("physical_verified") is not False or config.get("legal_verdict") is not None:
        raise ValueError("Physical or legal result claimed")
    capture_check(config)
    return {"case_id":case,"frames":600,"simulation_started":False,"selected_for_delivery":False}

if __name__ == "__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--check",action="store_true")
    parser.add_argument("--output-dir");parser.add_argument("--process-saved")
    parser.add_argument("--host",default="127.0.0.1");parser.add_argument("--port",type=int,default=2000)
    args=parser.parse_args()
    if sum((args.check,bool(args.output_dir),bool(args.process_saved))) != 1:
        raise SystemExit("Choose exactly one check, Native capture or saved analysis")
    config=json.loads(Path("config.json").read_text())
    check(config)
    if args.check:
        print(json.dumps(check(config),sort_keys=True))
    elif args.output_dir:
        print(json.dumps(capture_execute(config,args.output_dir,args.host,args.port),sort_keys=True))
    else:
        target=Path(args.process_saved)
        print(json.dumps(finalize_saved(target,target / "analysis-report.json"),sort_keys=True))
