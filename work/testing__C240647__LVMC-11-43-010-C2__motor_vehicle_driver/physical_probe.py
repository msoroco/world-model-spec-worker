"""Exercise exact maneuver realization and Native lifecycle on CPU fixtures."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from analysis import measure

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
KINDS=("complete_motion","incomplete_motion","missing_evidence")

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def role_sequence(rows, right, left):
    values=[]
    for row in rows:
        if row["section"] != "circulating":
            continue
        role="right" if row["lane_id"]==right else "left" if row["lane_id"]==left else "unmapped"
        if not values or values[-1]!=role:
            values.append(role)
    return values

def run(case_id,kind,output):
    plan=json.loads((HERE/"case-plan.json").read_text())
    case=next((row for row in plan["cases"] if row["case_id"]==case_id),None)
    if kind not in KINDS or case is None:
        raise ValueError("exact right-lane case or fixture kind missing")
    output_root=Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT","")).resolve()
    if REPO/".runtime-work" not in output_root.parents and output_root != REPO/".runtime-work":
        raise ValueError("SCENARIO_PIPELINE_OUTPUT_ROOT must be under .runtime-work")
    temp_root=REPO/".runtime-work/c240647-owner/temp"
    temp_root.mkdir(parents=True,exist_ok=True)
    name=case_id.removeprefix(HERE.name+"__")
    source=HERE/"cases"/name/"diagnostic-sources"
    with tempfile.TemporaryDirectory(dir=temp_root) as temporary:
        stage=Path(temporary)
        for packet in ("map","history","inventory"):
            shutil.copyfile(source/(packet+".json"),stage/(packet+".json"))
        (stage/"fixture-provenance.json").write_text(json.dumps({"provenance_kind":"synthetic_fixture",
            "diagnostic_fixture":True})+"\n")
        construction=json.loads((HERE/"cases"/name/"construction.json").read_text())
        config=json.loads(next(item["content"] for item in construction["files"] if item["path"]=="config.json"))
        for filename,value in (("construction.json",construction),("config.json",config)):
            (stage/filename).write_text(json.dumps(value,sort_keys=True)+"\n")
        (stage/"case-plan.json").write_bytes((HERE/"case-plan.json").read_bytes())
        if kind=="incomplete_motion":
            packet=json.loads((stage/"history.json").read_text())
            alternate="connector-through_exit" if case["actual_exit_request"]=="right_exit" else "connector-right_exit"
            for row in packet["frames"][-2:]:
                row["section"]="exit"
                row["exit_connector_id"]=alternate
                row["lane_id"]="exit-alternate"
            path=stage/"history.json"
            path.write_text(json.dumps(packet,sort_keys=True)+"\n")
            inventory=json.loads((stage/"inventory.json").read_text())
            inventory["sources"]["history"]["sha256"]=sha(path)
            (stage/"inventory.json").write_text(json.dumps(inventory,sort_keys=True)+"\n")
        elif kind=="missing_evidence":
            (stage/"history.json").unlink()
        status,error,measured="unverified",None,None
        try:
            measured=measure(stage)
            history=json.loads((stage/"history.json").read_text())
            mapped=json.loads((stage/"map.json").read_text())
            left=mapped.get("lanes",{}).get("left",{}).get("lane_id")
            sequence=role_sequence(history["frames"],measured["right_lane_id"],left)
            target={"right":["right"],"left":["left"],"left_then_right":["left","right"],
                    "right_then_left":["right","left"],"single_right":["right"]}[case["roundabout_lane_request"]]
            requested=None if case["actual_exit_request"]=="no_exit" else "connector-"+case["actual_exit_request"]
            realized=(measured["operator_intended_exit_role"]==case["operator_intent_request"] and
                      sequence==target and measured["first_observed_exit_connector_id"]==requested)
            status="met" if realized else "not_met"
        except ValueError as failure:
            error=str(failure)
            if kind!="missing_evidence" or "Missing required source" not in error:
                raise
        expected={"complete_motion":"met","incomplete_motion":"not_met","missing_evidence":"unverified"}[kind]
        if status!=expected:
            raise ValueError("physical fixture outcome differs: "+kind)
        result={"case_id":case_id,"physical_checks":{"maneuver":{"status":status,
            "method":"source-bound independent intent, ordered lane and first connector remeasurement",
            "sources":{key:sha(stage/(key+".json")) for key in ("map","history") if (stage/(key+".json")).is_file()},
            "error":error,"physical_causation_claimed":False}},
            "maneuver_completed":status=="met","realized_observables":{} if measured is None else {
              "source_frame_count":{"value":measured["source_frame_count"],"unit":"frames",
                "method":"original actor map/connector readback","statistic":"frame count",
                "time_window":"observed route","reference":"history.json"}},
            "measured_right_turn":measured,"provenance_kind":"synthetic_fixture",
            "diagnostic_fixture":True,"physical_acceptance_claimed":False,"legal_judgment":None}
        Path(output).write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
        lifecycle=None
        if kind=="complete_motion":
            sys.path.insert(0,str(REPO/"runtime/scenario_pipeline"))
            from worker_exchange.native_output import seal_capture
            from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, copy_sources
            (stage/"runner.py").write_text((HERE/"runner.py").read_text())
            (stage/"acquisition-provenance.json").write_text(json.dumps({
                "provenance_kind":"synthetic_fixture","diagnostic_fixture":True,
                "physical_acceptance_claimed":False})+"\n")
            (stage/"trace.jsonl").write_text("".join(json.dumps({"frame":i+100,
                "time_s":i/20,"lane_id":measured["last_circulating_lane_id"]})+"\n" for i in range(9)))
            (stage/"video_frames.jsonl").write_text("".join(json.dumps({
                "video_frame":i,"carla_frame":i+100,"native_frame":i+100,"time_s":i/20})+"\n" for i in range(9)))
            seal=seal_capture(stage,frames=9,restoration={"restored":True,
                "settings_readback":"synthetic CPU closure fixture"},errors=[],encoder_exit_codes={"fixture":0})
            native_exit=record_native_exit(stage)
            owner=acknowledge_owner_release(stage,stage/"owner-release.json",True)
            with tempfile.TemporaryDirectory(dir=temp_root) as saved:
                copy_sources(stage,Path(saved))
            if native_exit["capture_seal_sha256"]!=sha(stage/"capture-seal.json") or owner[
                    "native_exit_sha256"]!=sha(stage/"native-exit.json"):
                raise ValueError("Native lifecycle closure receipts differ")
            lifecycle=seal["events"]+["native_exit","owner_released","saved_processing_started"]
        return {"case_id":case_id,"kind":kind,"status":status,"diagnostic_fixture":True,
                "physical_acceptance_claimed":False,"lifecycle":lifecycle}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--case",required=True)
    parser.add_argument("--kind",choices=KINDS,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(run(args.case,args.kind,args.output),sort_keys=True))

if __name__ == "__main__":
    main()
