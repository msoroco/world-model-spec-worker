"""Synthetic 480-frame Native-shaped traversal fixture for exact package checks."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE / "native"))
from traversal import pose, body

spec = importlib.util.spec_from_file_location("core_fixture", HERE / "probe-core-synthetic.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


def write_rows(path, rows):
    path.write_text("".join(json.dumps(row,allow_nan=False)+"\n" for row in rows))


def make_attempt(destination: Path, suffix: str, full_resolution=True):
    if suffix not in ("traversal_reference","traversal_contrast"):
        raise ValueError("Unknown traversal case")
    core.make_attempt(destination,"reference",full_resolution=full_resolution)
    construction=json.loads((HERE/'draft-traversal-candidates'/suffix/'primary/construction.json').read_text())
    config=json.loads(next(item['content'] for item in construction['files'] if item['path']=='config.json'))
    (destination/'config.json').write_text(json.dumps(config))
    trace = core.rows(destination / "trace.jsonl")
    evidence = core.rows(destination / "capture/evidence.jsonl")
    samples = core.rows(destination / "native_samples.jsonl")
    history = core.rows(destination / "body_history.jsonl")
    if not all(len(rows)==480 for rows in (trace,evidence,samples,history)):
        raise ValueError("Base synthetic frame join differs")
    for index in range(480):
        x,y = pose(suffix,index)
        px,py = pose(suffix,max(0,index-1))
        speed = ((x-px)**2 + (y-py)**2)**.5 * 20
        corners = body(x,y)
        vertices = [[a,b,z] for a,b in corners for z in (0,1.5)]
        t,e,n,h = trace[index],evidence[index],samples[index],history[index]
        t["position"] = {"x":x,"y":y,"z":.5}
        t["position_m"] = [x,y,.5]
        t["speed_mps"] = speed
        t["speed_mph"] = speed/.44704
        e["ego"]["body_vertices_m"] = vertices
        e["ego"]["position_m"] = [x,y,.5]
        e["ego"]["speed_mps"] = speed
        n["native_center_xy_m"] = [x,y]
        n["native_body_xy_m"] = corners
        n["body_xy_m"] = corners
        n["speed_m_s"] = speed
        n["speed_mps"] = speed
        h["body_vertices_m"] = vertices
        e["world"]["road_projection"]["road_id"] = 1 if x < -7 else 13 if x < 7 else 2
    for name, rows in (("trace.jsonl",trace),("capture/evidence.jsonl",evidence),
                       ("native_samples.jsonl",samples),("body_history.jsonl",history)):
        write_rows(destination / name, rows)
    survey_path = destination / "road_geometry.json"
    survey = json.loads(survey_path.read_text())
    survey["intersection_polygon_xy_m"] = [[-7,-7],[7,-7],[7,7],[-7,7]]
    survey_path.write_text(json.dumps(survey))
    (destination / "context.json").write_text(json.dumps({"surveyed_two_way_intersection":survey}))
    channel_dir = destination / "channels"
    for path in channel_dir.glob("*.jsonl"):
        name = path.stem
        rows = core.rows(path)
        for index,row in enumerate(rows):
            sample = samples[index]
            if name == "drv.in_intersection":
                row["value"] = {"native_frame":sample["native_frame"],
                    "body_xy_m":sample["native_body_xy_m"]}
            elif name == "st.intersection": row["value"] = survey
            elif name == "rel.occupies": row["value"] = sample["native_body_xy_m"]
            elif name == "kin.position": row["value"] = sample["native_center_xy_m"]
            elif name == "rel.centre_distance":
                row["value"] = {"body_front_x_m":max(p[0] for p in sample["native_body_xy_m"]),
                    "intersection_entry_x_m":-7}
            elif name == "native_body_pose_control": row["value"] = sample
        write_rows(path,rows)
    manifest_path = destination / "capture/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["sources"]["trace.jsonl"] = hashlib.sha256((destination / "trace.jsonl").read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    return destination
