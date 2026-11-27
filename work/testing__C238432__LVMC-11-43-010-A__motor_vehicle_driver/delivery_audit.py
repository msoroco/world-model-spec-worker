"""Independently reopen original roundabout packets, actor joins and four videos."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from analysis import VIEWS, measure
from direction import CASE_DIRECTIONS


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("original source missing: "+path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def video(path,expected):
    if path.is_symlink() or not path.is_file():
        raise ValueError("original camera video missing: "+path.name)
    probe=subprocess.run(["ffprobe","-v","error","-count_frames","-select_streams","v:0",
        "-show_entries","stream=codec_name,width,height,nb_read_frames,avg_frame_rate",
        "-of","json",str(path)],capture_output=True,text=True,check=True)
    streams=json.loads(probe.stdout).get("streams",[])
    if len(streams)!=1 or int(streams[0].get("nb_read_frames",-1))!=expected:
        raise ValueError("camera full decode frame profile differs")
    decode=subprocess.run(["ffmpeg","-nostdin","-v","error","-xerror","-i",str(path),
        "-map","0:v:0","-f","null","-"],capture_output=True,text=True)
    if decode.returncode:
        raise ValueError("camera full decode failed: "+path.name)
    return {"sha256":sha(path),"decoded_frames":expected,
            "dimensions":[streams[0]["width"],streams[0]["height"]],
            "fps":streams[0]["avg_frame_rate"]}


def audit(attempt,case_id,plan):
    attempt=Path(attempt)
    selected={row["case_id"] for row in json.loads(Path(plan).read_text())["cases"]}
    if case_id not in CASE_DIRECTIONS or case_id not in selected:
        raise ValueError("exact roundabout delivery case differs")
    observed,trace,packet=measure(attempt)
    if observed["case_id"]!=case_id:
        raise ValueError("original history case differs")
    mapping=rows(attempt/"video_frames.jsonl")
    evidence=rows(attempt/"capture/evidence.jsonl")
    native=rows(attempt/"capture/native/frames.jsonl")
    history=json.loads((attempt/"history.json").read_text())
    count=len(mapping)
    if count not in (9,900) or any(len(items)!=count for items in (trace,evidence,native,history["frames"])):
        raise ValueError("original actor and video frame counts differ")
    if count==9 and not (attempt/"fixture-provenance.json").is_file():
        raise ValueError("short original capture lacks synthetic fixture provenance")
    for index,(join,actor,packet_row,graph_row,history_row) in enumerate(zip(
            mapping,trace,evidence,native,history["frames"])):
        number=join.get("carla_frame")
        if (join.get("video_frame")!=index or join.get("native_frame")!=number or
                actor.get("frame")!=number or packet_row.get("original_frame")!=number or
                graph_row.get("frame")!=number or history_row.get("frame")!=number or
                abs(float(join.get("time_s",-1))-float(actor.get("time_s",-2)))>.005 or
                abs(float(history_row.get("x"))-float(actor.get("position_m",[None])[0]))>.001):
            raise ValueError("original participant/time/video join differs")
    videos={name:video(attempt/(name+".mkv"),count) for name in VIEWS}
    return {"format":"c238432-independent-direction-delivery-audit-v1",
        "case_id":case_id,"source_measurement":observed,"map_name":packet["map_name"],
        "frame_count":count,"four_view_full_decode":videos,"source_video_join":True,
        "diagnostic_fixture":count==9,"actual_pixels_verified":False,
        "physical_acceptance":False,"legal_judgment":"unresolved"}


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--case-id",required=True)
    parser.add_argument("--attempt",type=Path,required=True)
    parser.add_argument("--plan",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise ValueError("refusing to overwrite audit")
    result=audit(args.attempt,args.case_id,args.plan)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
