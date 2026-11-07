"""Exact unselected C104393 synthetic package positive and missing-source negative."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import pickle
import shutil
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
sys.path.insert(0,str(ROOT/"runtime/pipeline/scenario_pipeline"))
sys.path.insert(0,str(HERE/"native"))
from geometry import open_drive
from traffic_spec_adapter.adapter import load_graph
from worker_exchange.package_compatibility import run,materialize_case
from worker_exchange.runtime_cli import execution_env

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write_rows(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text("".join(json.dumps(row,allow_nan=False)+"\n" for row in rows))

def build_fixture(source,feet,config):
    source.mkdir(parents=True)
    rows=[json.loads(line) for line in (HERE/f"synthetic-saved-fixtures/{feet}/native_samples.jsonl").read_text().splitlines()]
    request=config["native_request"]
    if len(rows)!=840:raise ValueError("Expected 840 synthetic source rows")
    radius=request["turn_radius_m"]
    if radius==24.0:
        for i,row in enumerate(rows[521:],start=521):
            angle=min((i-520)*.25/(radius+1.75),math.pi/2)
            x=(radius+1.75)*math.sin(angle)
            y=-radius+(radius+1.75)*math.cos(angle)
            heading=-math.degrees(angle)
            c,s=math.cos(math.radians(heading)),math.sin(math.radians(heading))
            row["ego_xy_m"]=[x,y]
            row["heading_deg"]=heading
            row["native_body_xy_m"]=[[round(x+u*c-v*s,6),round(y+u*s+v*c,6)]
                for u,v in ((-2,-.8),(-2,.8),(2,-.8),(2,.8))]
    (source/"road_geometry.json").write_text(json.dumps({
        "native_map_sha256":request["map_sha256"],"authored_map_sha256":request["map_sha256"],
        "turn_radius_m":request["turn_radius_m"],"lane_link_confirmed":True,
        "area_classification":request["area"],"provenance":"synthetic_cpu_fixture"})+"\n")
    graph=load_graph(ROOT/"runtime/pipeline/fixtures/retained-speed/capture/native/graphs/base/00021714.pkl")
    graph_dir=source/"capture/native/graphs/base";graph_dir.mkdir(parents=True)
    trace=[];evidence=[];mapping=[];body=[];frames=[]
    channels={c["name"]:[] for c in config["recording_description"]["channels"]}
    for i,row in enumerate(rows):
        frame=row["native_frame"];time=row["time_s"]
        x,y=row["ego_xy_m"]
        speed=0 if i==0 else math.dist(rows[i-1]["ego_xy_m"],row["ego_xy_m"])*20
        vertices=[[a,b,z] for a,b in row["native_body_xy_m"] for z in (0,1.5)]
        trace.append({"frame":frame,"time_s":time,"position":{"x":x,"y":y,"z":.5},
            "position_m":[x,y,.5],"heading_deg":row["heading_deg"],"speed_mps":speed,
            "speed_mph":speed/.44704,"control":{"throttle":0,"brake":0,"hand_brake":False}})
        evidence.append({"original_frame":frame,"recording_time_s":time,
            "replay_frame":frame,"replay_simulation_time_s":time,"actor_id":107,
            "ego":{"body_vertices_m":vertices,"position_m":[x,y,.5],
                   "heading_deg":row["heading_deg"],"speed_mps":speed,
                   "speed_provenance":"original_trace_actor_get_velocity","synthetic_diagnostic":True},
            "world":{"weather":{"cloudiness":0,"precipitation":0,"wetness":0,"fog_density":0},
                "road_projection":{"road_id":1 if i<520 else 2,"section_id":0,
                    "lane_id":-1,"s_m":x+130}}})
        mapping.append({"video_frame":i,"native_frame":frame,"carla_frame":frame,"time_s":time})
        body.append({"frame":frame,"time_s":time,"body_vertices_m":vertices})
        frames.append({"frame":frame,"simulation_time":time,"time_s":time,
            "base":f"graphs/base/{frame:08d}.pkl",
            "abstract":f"graphs/abstract/{frame:08d}.pkl","synthetic_diagnostic":True})
        graph.graph["frame"]=frame
        (graph_dir/f"{frame:08d}.pkl").write_bytes(pickle.dumps(graph,protocol=4))
        values={"sig.turn_indicator":{"observed_left_indicator_state":row["signal"]=="left"},
            "drv.distance_while":{"signal":row["signal"],"xy_m":[x,y]},
            "kin.path_length":{"xy_m":[x,y]},
            "drv.turning":{"heading_deg":row["heading_deg"]},
            "env.precipitation":row["weather"],"kin.speed":speed,
            "native_body_pose_control":row,"camera_frame_join":mapping[-1]}
        for name in channels:channels[name].append({"time_s":time,"value":values[name]})
    write_rows(source/"trace.jsonl",trace)
    write_rows(source/"capture/evidence.jsonl",evidence)
    write_rows(source/"video_frames.jsonl",mapping)
    write_rows(source/"native_samples.jsonl",rows)
    write_rows(source/"body_history.jsonl",body)
    write_rows(source/"capture/native/frames.jsonl",frames)
    for name,values in channels.items():write_rows(source/"channels"/(name+".jsonl"),values)
    (source/"road.xodr").write_text(open_drive(radius))
    (source/"capture/recorder_info.txt").write_text("Create 107: vehicle.lincoln.mkz_2020\n")
    (source/"capture/manifest.json").write_text(json.dumps({"extraction_confirmed":True,
        "frames":840,"synthetic_diagnostic":True,
        "sources":{"road.xodr":sha(source/"road.xodr"),"trace.jsonl":sha(source/"trace.jsonl")}})+"\n")
    for camera in config["cameras"]:
        subprocess.run(["ffmpeg","-nostdin","-hide_banner","-loglevel","error","-y",
            "-f","lavfi","-i","color=c=black:s=32x32:r=20:d=42",
            "-frames:v","840","-c:v","ffv1",str(source/(camera["name"]+".mkv"))],
            check=True,timeout=180)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--feet",type=int,choices=(90,100,110,290,300,310),default=300)
    parser.add_argument("--candidate",choices=("primary","fallback1","fallback2","fallback3"),default="primary")
    args=parser.parse_args()
    manifest=HERE/"draft-execution-manifest.json"
    case=HERE.name+"__"+str(args.feet)
    construction=json.loads((HERE/f"draft-candidates/{args.feet}/{args.candidate}/construction.json").read_text())
    config=json.loads(next(f["content"] for f in construction["files"] if f["path"]=="config.json"))
    scratch=Path(tempfile.mkdtemp(dir=ROOT/".runtime-work",prefix="c104393-413-v1-"))
    source=scratch/"source"
    build_fixture(source,args.feet,config)
    receipt=run(manifest,case,source,scratch/"output",ROOT/"runtime/pipeline/library",
        ROOT/".runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck",args.candidate)
    negative=scratch/"negative"
    materialize_case(manifest,case,negative,source,args.candidate)
    (negative/"native_samples.jsonl").unlink()
    failure=subprocess.run([sys.executable,str(negative/"finalize.py"),
        "--attempt",str(negative),"--output",str(negative/"analysis-report.json")],
        cwd=negative,env=execution_env(),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
        text=True,timeout=300)
    if failure.returncode==0 or "Missing required source: native_samples.jsonl" not in failure.stdout:
        raise RuntimeError("Missing-source negative failed: "+failure.stdout[-1000:])
    summary={"format":"c104393-unselected-v1-compatibility-probe","case_id":case,
        "candidate_id":args.candidate,"positive":receipt,"negative_exit_code":failure.returncode,
        "negative_removed":"native_samples.jsonl","synthetic":True,"selected":False,
        "physical_success_claimed":False,"scratch":str(scratch)}
    (HERE/f"compatibility-probe-{args.feet}-{args.candidate}.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps({k:v for k,v in summary.items() if k!="positive"},indent=2))

if __name__=="__main__":main()
