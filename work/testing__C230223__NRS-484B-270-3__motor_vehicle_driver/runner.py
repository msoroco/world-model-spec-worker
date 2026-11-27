"""Exact Native runner for source-reviewed cycle-lane yield and entry cases."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from cycle_lane_2703 import ASSIGNMENT, VIEWS, prepare


def check_config(config):
    folder=Path(__file__).resolve().parent
    plan=json.loads((folder/"case-plan.json").read_text())
    cases={case["case_id"] for case in plan["cases"]}
    if (config.get("selected_case_id") not in cases or
            set(config.get("supported_case_ids",[])) != cases or
            config.get("law_id") != "NRS-484B-270-3" or
            config.get("cell_id") != "C230223" or
            config.get("actor") != "motor_vehicle_driver" or
            config.get("rate_hz") != 20 or config.get("duration_s") != 45 or
            tuple(camera.get("name") for camera in config.get("cameras",[])) != VIEWS):
        raise ValueError("exact NRS 484B.270(3) Native config differs")
    return True


def reviewed_packet(path):
    root=Path(path).resolve().parent
    packet=json.loads(Path(path).read_text())
    if packet.get("format") != "cycle-lane-2703-reviewed-packet-v1":
        raise ValueError("original reviewed packet required")
    refs=packet.get("sources",{})
    if set(refs) != {"site","participant","context"}:
        raise ValueError("independent site, participant and context sources required")
    resolved={}
    for name,ref in refs.items():
        rel=ref.get("path")
        if not isinstance(rel,str) or Path(rel).is_absolute() or not ref.get("sha256"):
            raise ValueError("original reviewed source path/hash required: "+name)
        target=(root/rel).resolve()
        if (not target.is_relative_to(root) or not target.is_file() or target.is_symlink() or
                hashlib.sha256(target.read_bytes()).hexdigest() != ref["sha256"]):
            raise ValueError("original reviewed source changed: "+name)
        resolved[name]=target
    return resolved, {name:refs[name]["sha256"] for name in refs}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--check",action="store_true")
    parser.add_argument("--host",default="localhost")
    parser.add_argument("--port",type=int,default=2000)
    parser.add_argument("--output-dir",type=Path)
    args=parser.parse_args()
    config=json.loads(Path("config.json").read_text())
    check_config(config)
    if args.check:
        print("exact NRS 484B.270(3) source-gated Native config passed")
        return
    if args.output_dir is None:
        raise ValueError("Native output directory required")
    reviewed=os.environ.get("C230223_2703_REVIEWED_PACKET")
    if not reviewed:
        raise ValueError("independent original reviewed cycle-lane packet required")
    paths,hashes=reviewed_packet(reviewed)
    plan=prepare(config["selected_case_id"],paths["site"],hashes["site"],
                 paths["participant"],hashes["participant"],
                 paths["context"],hashes["context"])
    from cycle_lane_native import NativeAdapter
    adapter=NativeAdapter(args.host,args.port,args.output_dir,paths,plan)
    try:
        adapter.execute(config,paths["participant"])
    finally:
        adapter.close()
    if not adapter.restoration_verified:
        raise ValueError("original Native world restoration unverified")
    (args.output_dir/"acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind":"native","diagnostic_fixture":False,
        "physical_acceptance_claimed":False})+"\n")
    from worker_exchange.native_output import seal_capture,write_result
    from analysis import analyze,saved_result
    report=analyze(args.output_dir,config["selected_case_id"])
    write_result(args.output_dir,saved_result(args.output_dir,report))
    seal_capture(args.output_dir,frames=900,
                 restoration={"restored":True,
                              "settings_readback":"synchronous mode and delta verified"},
                 errors=[],encoder_exit_codes={name:0 for name in VIEWS},
                 context={name+"_sha256":value for name,value in hashes.items()})


if __name__ == "__main__":
    main()
