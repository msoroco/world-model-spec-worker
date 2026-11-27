"""CPU exercise of measured circulation outcomes and Native ownership closure."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile

from direction import load_source, measure_history

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
SCRATCH=REPO/".runtime-work/c238432"
KINDS=("complete_motion","incomplete_motion","missing_evidence")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(case_id,kind,output):
    if kind not in KINDS or case_id not in {row["case_id"] for row in json.loads((HERE/"case-plan.json").read_text())["cases"]}:
        raise ValueError("exact direction case and physical fixture required")
    if Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT","")).resolve()!=SCRATCH:
        raise ValueError("runtime output must stay under assignment scratch")
    suffix=case_id.split("__")[-1]
    source=HERE/"cases"/suffix/"diagnostic-sources"
    with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
        stage=Path(temporary)
        for name in ("map","history","inventory"):
            shutil.copyfile(source/(name+".json"),stage/(name+".json"))
        construction_source=HERE/"construction.json" if suffix=="counterclockwise" else HERE/"cases"/suffix/"construction.json"
        construction=json.loads(construction_source.read_text())
        (stage/"construction.json").write_text(json.dumps(construction,sort_keys=True)+"\n")
        config=next(json.loads(item["content"]) for item in construction["files"] if item["path"]=="config.json")
        (stage/"config.json").write_text(json.dumps(config,sort_keys=True)+"\n")
        if kind=="incomplete_motion":
            history=json.loads((stage/"history.json").read_text())
            ring=[row for row in history["frames"] if row["section"]=="ring"]
            reverse_xy=[(row["x"],row["y"]) for row in reversed(ring)]
            for row,(x,y) in zip(ring,reverse_xy):
                row["x"],row["y"]=x,y
            (stage/"history.json").write_text(json.dumps(history,sort_keys=True)+"\n")
            inventory=json.loads((stage/"inventory.json").read_text())
            inventory["sources"]["history"]["sha256"]=sha(stage/"history.json")
            (stage/"inventory.json").write_text(json.dumps(inventory,sort_keys=True)+"\n")
        if kind=="missing_evidence":
            (stage/"history.json").unlink()
        measured=None
        error=None
        status="unverified"
        try:
            if not (stage/"history.json").is_file():
                raise ValueError("Missing required source: history.json")
            packet=load_source(stage/"map.json",sha(stage/"map.json"),case_id)
            history=json.loads((stage/"history.json").read_text())
            measured=measure_history(packet,history,case_id,expected_frames=9)
            status="met" if measured["observed_direction"]==measured["requested_direction"] else "not_met"
        except ValueError as failure:
            error=str(failure)
            if kind!="missing_evidence" or "Missing required source" not in error:
                raise
        expected={"complete_motion":"met","incomplete_motion":"not_met","missing_evidence":"unverified"}[kind]
        if status!=expected:
            raise ValueError("physical motion fixture differs: "+kind)
        result={"case_id":case_id,"physical_checks":{"maneuver":{
            "status":status,"method":"original map-bound signed actor ring arc",
            "sources":{name:sha(stage/(name+".json")) for name in ("map","history")
                       if (stage/(name+".json")).is_file()},"error":error,
            "physical_causation_claimed":False}},"maneuver_completed":status=="met",
            "realized_observables":{} if measured is None else {"signed_arc_rad":{
                "value":measured["signed_arc_rad"],"unit":"rad",
                "method":"source-bound polar angle integration","statistic":"signed circular arc",
                "time_window":"original ring frames","reference":"history.json"}},
            "measured_direction":measured,"provenance_kind":"synthetic_fixture",
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
            first=history["frames"][0]["frame"]
            (stage/"trace.jsonl").write_text("".join(json.dumps({"frame":first+i,
                "time_s":i/20})+"\n" for i in range(9)))
            (stage/"video_frames.jsonl").write_text("".join(json.dumps({
                "video_frame":i,"carla_frame":first+i,"native_frame":first+i,
                "time_s":i/20})+"\n" for i in range(9)))
            seal=seal_capture(stage,frames=9,restoration={"restored":True,
                "settings_readback":"synthetic CPU closure fixture"},errors=[],
                encoder_exit_codes={"fixture":0})
            native=record_native_exit(stage)
            released=acknowledge_owner_release(stage,stage/"owner-release.json",True)
            with tempfile.TemporaryDirectory(dir=SCRATCH) as saved:
                copy_sources(stage,Path(saved))
            if native["capture_seal_sha256"]!=sha(stage/"capture-seal.json") or released[
                    "native_exit_sha256"]!=sha(stage/"native-exit.json"):
                raise ValueError("Native lifecycle source hash changed")
            lifecycle=seal["events"]+["native_exit","owner_released","saved_processing_started"]
        return {"case_id":case_id,"kind":kind,"status":status,"lifecycle":lifecycle,
                "diagnostic_fixture":True,"physical_acceptance_claimed":False}


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--case",required=True)
    parser.add_argument("--kind",choices=KINDS,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(run(args.case,args.kind,args.output),sort_keys=True))
