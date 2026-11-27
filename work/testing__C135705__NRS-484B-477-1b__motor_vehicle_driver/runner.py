"""Lazy source-gated Native entrypoint for exact C135705 alley-width cases."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

from native_capture import CAMERAS, capture
from width_measurement import ASSIGNMENT


def check(root):
    config = json.loads((root / "config.json").read_text())
    plan_bytes = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(plan_bytes).hexdigest() != config.get("plan_sha256"):
        raise ValueError("exact alley-width plan changed")
    plan = json.loads(plan_bytes)
    case_id = config.get("selected_case_id")
    matches = [row for row in plan["cases"] if row["case_id"] == case_id]
    if len(matches) != 1 or (config.get("assignment_id"), config.get("law_id"),
                             config.get("cell_id"), config.get("actor")) != (
                             ASSIGNMENT, "NRS-484B-477-1b", "C135705", "motor_vehicle_driver"):
        raise ValueError("exact alley-width identity differs")
    if config.get("variant") != matches[0]["variant"]:
        raise ValueError("selected width condition differs")
    if (config.get("rate_hz"), config.get("frame_count"), config.get("duration_s")) != (20,900,45):
        raise ValueError("original capture cadence differs")
    if config.get("approach_direction") not in (-1,1):
        raise ValueError("surveyed approach direction invalid")
    if {c["name"] for c in config["cameras"]} != CAMERAS:
        raise ValueError("four-view capture differs")
    return case_id, config


def _load_operator(path, digest):
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError("reviewed Native operator source hash differs")
    spec=importlib.util.spec_from_file_location("reviewed_alley_width_operator",path)
    if spec is None or spec.loader is None:
        raise ValueError("reviewed Native operator cannot load")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module,"make_operator",None)):
        raise ValueError("reviewed Native operator factory missing")
    return module


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--check",action="store_true")
    parser.add_argument("--host")
    parser.add_argument("--port",type=int)
    parser.add_argument("--output-dir",type=Path)
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    case_id,config=check(root)
    if args.check:
        print("exact alley-width bundle passed: "+case_id)
        return
    if not args.host or not args.port or not args.output_dir or not args.output_dir.is_dir():
        raise ValueError("Native host, port and output directory required")
    names=("SCENARIO_ALLEY_WIDTH_SITE_PACKET","SCENARIO_ALLEY_WIDTH_SITE_SHA256",
           "SCENARIO_ALLEY_WIDTH_OPERATOR_MODULE","SCENARIO_ALLEY_WIDTH_OPERATOR_SHA256")
    values=[os.environ.get(name) for name in names]
    if not all(values):
        raise ValueError("reviewed source-hashed alley site and operator required")
    site_path,site_sha,operator_path,operator_sha=values
    site_bytes=Path(site_path).read_bytes()
    if hashlib.sha256(site_bytes).hexdigest()!=site_sha:
        raise ValueError("reviewed alley site source hash differs")
    site=json.loads(site_bytes)
    if site.get("alley_kind")!="other_alley" or site.get("public_highway_status") is not True:
        raise ValueError("reviewed qualifying alley site missing")
    module=_load_operator(Path(operator_path).resolve(),operator_sha)
    import carla
    client=carla.Client(args.host,args.port)
    client.set_timeout(30)
    operator=module.make_operator(client.get_world(),site,case_id,config["approach_direction"])
    from pipeline_capture import PipelineCapture
    operator.pipeline_capture=PipelineCapture(client,operator.ego,args.output_dir,case_id)
    try:
        capture(operator,case_id,args.output_dir/"original-attempt",
                after_tick=operator.pipeline_capture.capture)
        from finalize_native import finalize
        finalize(args.output_dir,case_id=case_id,restored=operator.restored)
    finally:
        if not operator.closed:
            operator.cleanup()


if __name__=="__main__":
    main()
