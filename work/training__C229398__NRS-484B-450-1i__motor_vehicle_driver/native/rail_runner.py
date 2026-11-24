"""Unselected railroad-rail curbside capture contract; no simulator is launched by --check."""
import argparse
import json
from pathlib import Path


def check(cfg):
    if cfg.get("case_id") != "training__C229398__NRS-484B-450-1i__motor_vehicle_driver__selected_98183a3f__condition_a":
        raise ValueError("wrong exact case")
    if (cfg.get("law_id"),cfg.get("cell_id"),cfg.get("actor")) != ("NRS-484B-450-1i","C229398","motor_vehicle_driver"):
        raise ValueError("wrong law, cell or actor")
    if cfg.get("rate_hz") != 20 or cfg.get("duration_s") != 30 or cfg.get("duration_frames") != 600:
        raise ValueError("full 30-second 20 Hz window required")
    if cfg.get("rail_source_kind") != "map_survey_or_native_survey" or cfg.get("target_footprint_gap_m") != 12.5:
        raise ValueError("rail survey or placement changed")
    cameras=cfg.get("cameras")
    if not isinstance(cameras,list) or [c.get("name") for c in cameras] != ["overview","approach","reference_corner","driver_reference"]:
        raise ValueError("four named cameras required")
    if any(c.get("fps")!=20 or c.get("width",0)<16 or c.get("height",0)<16 for c in cameras):
        raise ValueError("camera profile incomplete")
    phases=cfg.get("control_phases")
    if not isinstance(phases,list) or [(p.get("first_frame"),p.get("last_frame")) for p in phases] != [(0,199),(200,599)]:
        raise ValueError("controller does not cover all frames")
    if cfg.get("physical_verified") is not False or cfg.get("legal_verdict") is not None:
        raise ValueError("physical or legal claim in draft")
    return {"checked":True,"frames":600,"fps":20,"simulation_started":False}


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--check",action="store_true")
    args=parser.parse_args()
    if not args.check:
        raise SystemExit("Draft requires Native survey/acquisition before execution")
    print(json.dumps(check(json.loads(Path("config.json").read_text()))))
