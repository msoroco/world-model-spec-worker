"""Exercise pinned completion and lifecycle on three synthetic outcomes per case."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
output_root=Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT","")).resolve()
if not output_root.is_relative_to(ROOT/".runtime-work"):
    raise RuntimeError("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work before runtime imports")
sys.path.insert(0,str(ROOT/"runtime/scenario_pipeline"))
from worker_exchange.native_output import physical_result,seal_capture
from worker_exchange.saved_processing import record_native_exit,acknowledge_owner_release


def write(path,value):path.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+"\n")
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def lines(path,values):path.write_text("".join(json.dumps(value,sort_keys=True)+"\n" for value in values))


def fixture(folder,config,kind):
    folder.mkdir(parents=True,exist_ok=True)
    write(folder/"config.json",config)
    points=[(65-i*3,2.2) for i in range(5)]
    if kind=="incomplete_motion":points=[(65,2.2)]*5
    body=[{"frame":i,"time_s":i/20,"actor_id":8,
           "body_vertices_xy_m":[[x-2.5,y-1],[x+2.5,y-1],[x+2.5,y+1],[x-2.5,y+1]],
           "heading_deg":180} for i,(x,y) in enumerate(points)]
    lines(folder/"trace.jsonl",[{"frame":r["frame"],"time_s":r["time_s"]} for r in body])
    lines(folder/"video_frames.jsonl",[{"carla_frame":r["frame"],"video_frame":r["frame"],
                                          "time_s":r["time_s"]} for r in body])
    if kind!="missing_evidence":lines(folder/"passing-body-history.jsonl",body)
    write(folder/"acquisition-provenance.json",{"diagnostic_fixture":True})
    result=physical_result(folder,{"case_id":config["selected_case_id"],"target_checks":[]})
    expected={"complete_motion":"met","incomplete_motion":"not_met","missing_evidence":"unverified"}[kind]
    if result["physical_checks"]["maneuver"]["status"]!=expected or result["maneuver_completed"]!=(expected=="met"):
        raise AssertionError("pinned physical result differs: "+kind)
    if result.get("provenance_kind")!="synthetic_fixture" or result.get("diagnostic_fixture") is not True:
        raise AssertionError("synthetic physical proof made a Native claim")
    return result


def lifecycle(folder,construction):
    folder.mkdir(parents=True,exist_ok=True)
    write(folder/"construction.json",construction)
    (folder/"runner.py").write_text("# synthetic lifecycle source\n")
    lines(folder/"trace.jsonl",[{"frame":0}])
    lines(folder/"video_frames.jsonl",[{"carla_frame":0,"video_frame":0,"time_s":0}])
    write(folder/"acquisition-provenance.json",{"diagnostic_fixture":True})
    try:record_native_exit(folder)
    except Exception:pass
    else:raise AssertionError("Native exit accepted before closure")
    seal=seal_capture(folder,frames=1,restoration={"restored":True},errors=[],
                      encoder_exit_codes={"overview":0,"approach":0,"reference_corner":0,"driver_reference":0})
    record_native_exit(folder)
    receipt=folder/"owner-release.json"
    try:acknowledge_owner_release(folder,receipt,False)
    except ValueError:pass
    else:raise AssertionError("unacknowledged owner release accepted")
    acknowledge_owner_release(folder,receipt,True)
    return seal["events"]+["native_exit","owner_released","saved_processing_started"]


def main():
    manifest_path=HERE/"execution-manifest.json";manifest=json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        suffix=entry["case_id"].rsplit("__",1)[-1]
        folder=HERE/"cases"/suffix
        construction=json.loads((HERE/entry["construction"]).read_text())
        config=json.loads(next(item["content"] for item in construction["files"] if item["path"]=="config.json"))
        with tempfile.TemporaryDirectory(dir=ROOT/".runtime-work",prefix="c135705-physical-") as temp:
            root=Path(temp);fixtures=[]
            for kind in ("complete_motion","incomplete_motion","missing_evidence"):
                result=fixture(root/kind,config,kind)
                result_path=folder/f"physical-{kind}.json";log_path=folder/f"physical-{kind}.log"
                write(result_path,result)
                log_path.write_text(f"Pinned physical_result: {entry['case_id']} {kind} = {result['physical_checks']['maneuver']['status']}; synthetic diagnostic fixture only.\n")
                fixtures.append({"kind":kind,"command":
                    "export SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c135705-direct-runtime; .venv-cpu/bin/python work/"+HERE.name+"/prove_physical_cases.py",
                    "exit_code":0,"log":str(log_path.relative_to(HERE)),"log_sha256":sha(log_path),
                    "result":str(result_path.relative_to(HERE)),"result_sha256":sha(result_path)})
            events=lifecycle(root/"lifecycle",construction)
        life_log=folder/"physical-lifecycle.log"
        life_log.write_text("Pinned seal_capture, record_native_exit, acknowledge_owner_release ordering; synthetic fixture owns no CARLA resources.\n"+" -> ".join(events)+"\n")
        receipt={"construction_sha256":entry["construction_sha256"],"fixtures":fixtures,
            "lifecycle":{"events":events,"exit_code":0,"log":str(life_log.relative_to(HERE)),
                         "log_sha256":sha(life_log)}}
        receipt_path=folder/"physical-preparation.json";write(receipt_path,receipt)
        entry["physical_preparation"]={"receipt":str(receipt_path.relative_to(HERE)),
                                       "sha256":sha(receipt_path)}
        print(suffix,"three physical outcomes and lifecycle passed")
    manifest_path.write_text(json.dumps(manifest,indent=2,allow_nan=False)+"\n")


if __name__=="__main__":main()
