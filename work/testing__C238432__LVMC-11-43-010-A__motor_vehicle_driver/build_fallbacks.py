"""Prepare slower route tracking after measured primary tracking failure."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from direction import ASSIGNMENT

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+"\n")


def build():
    path=HERE/"execution-manifest.json"
    manifest=json.loads(path.read_text())
    for entry in manifest["cases"]:
        name=entry["case_id"].removeprefix(ASSIGNMENT+"__")
        folder=HERE/"cases"/name
        primary=json.loads((HERE/entry["construction"]).read_text())
        config=json.loads(next(f["content"] for f in primary["files"] if f["path"]=="config.json"))
        config["route_throttle"]=.25
        fallback_config=folder/"fallback1-config.json"
        write(fallback_config,config)
        for f in primary["files"]:
            if f["path"]=="config.json":
                f["content"]=fallback_config.read_text()
                f["source"]=str(fallback_config.relative_to(REPO))
        primary["mechanisms"].append("fallback1 measured cross-track failure throttle 0.25")
        fallback=folder/"fallback1-construction.json"
        write(fallback,primary)
        entry["candidate_risk"]={"status":"physical",
            "reason":"The route controller may overshoot a surveyed circular lane and lose the tracked corridor in a live Native attempt."}
        entry["candidates"]=[{"id":"fallback1",
            "construction":str(fallback.relative_to(HERE)),
            "construction_sha256":hashlib.sha256(fallback.read_bytes()).hexdigest(),
            "trigger":{"source":"original actor XY history and mapped ring corridor",
                       "metric":"maximum sampled cross-track deviation_m",
                       "failure_condition":"Primary route tracker exceeds 4 m from the mapped connected route before completing the ring arc"},
            "changed_knobs":["route_throttle 0.25 instead of 0.32; same surveyed route, source identity and comparison condition"]}]
    write(path,manifest)


if __name__=="__main__":
    build()
