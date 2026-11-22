"""Synthetic full-decode positive/negative proof of the saved delivery auditor."""
from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
from pathlib import Path

from delivery_audit import audit
from saved_measurement import SOURCES,VIDEOS,sha

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def write(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+"\n")


def decode(path,count):
    probe=subprocess.check_output(["ffprobe","-v","error","-select_streams","v:0",
        "-count_frames","-show_entries","stream=nb_read_frames,width,height,r_frame_rate",
        "-of","json",str(path)],text=True)
    stream=json.loads(probe)["streams"][0]
    if int(stream["nb_read_frames"])!=count or stream["r_frame_rate"]!="20/1":
        raise ValueError("diagnostic camera frame identity differs")
    subprocess.run(["ffmpeg","-nostdin","-v","error","-xerror","-i",str(path),
                    "-f","null","-"],check=True,stdout=subprocess.DEVNULL,timeout=120)
    return {"sha256":sha(path),"frames_fully_decoded":count,
            "width":stream["width"],"height":stream["height"],"fps":20}


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--case",required=True)
    parser.add_argument("--output",required=True);parser.add_argument("--negative",action="store_true")
    args=parser.parse_args()
    manifest=json.loads((HERE/"execution-manifest.json").read_text())
    entry=next(e for e in manifest["cases"] if e["case_id"]==args.case)
    command=shlex.split(entry["compatibility"]["command"])
    source=Path(command[command.index("--output")+1]).resolve()
    output=Path(args.output).resolve()
    if not output.is_relative_to(ROOT/".runtime-work") or output.exists():
        raise ValueError("fresh diagnostic audit output under .runtime-work required")
    output.mkdir(parents=True)
    names=set((*SOURCES,*VIDEOS,"acquisition.json","acquisition-provenance.json","result.json"))
    for name in names:
        if name=="authored-road.xodr":
            shutil.copyfile(source/"road.xodr",output/name)
        else:shutil.copyfile(source/name,output/name)
    count=len((output/"video_frames.jsonl").read_text().splitlines())
    media={name:decode(output/name,count) for name in VIDEOS}
    seal={"format":"worker-sealed-capture","provenance_kind":"synthetic_fixture",
          "diagnostic_fixture":True,"restoration":{"restored":True},
          "frames":count,"sources":{name:sha(output/name) for name in names}}
    write(output/"capture-seal.json",seal)
    measured=json.loads((output/"result.json").read_text())["measured_values"]
    report={"format":"c135705-source-bound-standing-measurement","case_id":args.case,
        "provenance_kind":"synthetic_fixture","source_sha256":{
            name:sha(output/name) for name in (*SOURCES,*VIDEOS,"acquisition.json")},
        "capture_seal_sha256":sha(output/"capture-seal.json"),
        "media_full_decode":media,"measured":measured,"physical_acceptance_claimed":False}
    write(output/"standing-measurement.json",report)
    if args.negative:
        with (output/"standing-body-history.jsonl").open("a") as stream:stream.write("\n")
    receipt=audit(output,diagnostic_test=True)
    if not receipt["diagnostic_audit_test_passed"] or receipt["physical_acceptance_claimed"]:
        raise AssertionError("diagnostic source audit made a physical claim")
    print(json.dumps({"case_id":args.case,"diagnostic_audit_test_passed":True,
        "four_original_shaped_videos_fully_decoded":True,"actual_carla_capture_claimed":False},indent=2))


if __name__=="__main__":main()
