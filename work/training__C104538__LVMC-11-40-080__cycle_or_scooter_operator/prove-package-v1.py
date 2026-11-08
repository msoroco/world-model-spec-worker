"""Synthetic full-package probe for exact unselected mounted-bicycle bundles."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MOTOR = ROOT/"work/training__C104538__NRS-484B-403-2__motor_vehicle_driver"
sys.path.insert(0, str(ROOT/"runtime/pipeline/scenario_pipeline"))
from worker_exchange.package_compatibility import run, materialize_case
from worker_exchange.runtime_cli import execution_env

spec = importlib.util.spec_from_file_location("c104538_motor_synthetic_fixture", MOTOR/"probe-core-synthetic.py")
motor_fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(motor_fixture)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def write_rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(v, allow_nan=False)+"\n" for v in values))


def seed(source, kind, candidate):
    motor = motor_fixture.make_attempt(source.parent/"motor", "witness_1" if kind == "mounted_obey" else "witness_2", candidate)
    source.mkdir()
    for name in ("native_samples.jsonl", "video_frames.jsonl", "body_history.jsonl", "trace.jsonl",
                 "context.json", "road.xodr", "overview.mkv", "approach.mkv",
                 "sign_reference.mkv", "driver_reference.mkv"):
        shutil.copyfile(motor/name, source/name)
    shutil.copytree(motor/"capture", source/"capture")
    sample_source = HERE/"draft-native-sources"/(kind+"-"+candidate+".jsonl")
    rider = read_rows(sample_source)
    native = read_rows(source/"native_samples.jsonl")
    mapping = read_rows(source/"video_frames.jsonl")
    trace = read_rows(source/"trace.jsonl")
    evidence = read_rows(source/"capture/evidence.jsonl")
    history = read_rows(source/"body_history.jsonl")
    if any(len(x) != 480 for x in (rider, native, mapping, trace, evidence, history)):
        raise ValueError("Synthetic fixture lacks 480 frames")
    for i, (r, n, m, t, e, b) in enumerate(zip(rider, native, mapping, trace, evidence, history)):
        x, y = r["x_m"], r["y_m"]
        next_row = rider[min(479, i+1)]
        prior_row = rider[max(0, i-1)]
        dx, dy = next_row["x_m"]-prior_row["x_m"], next_row["y_m"]-prior_row["y_m"]
        length = math.hypot(dx, dy)
        forward = [dx/length, dy/length] if length > 1e-7 else [1.0, 0.0]
        corners = [[round(x+sx,6), round(y+sy,6)] for sx,sy in
                   ((-1,-.35),(-1,.35),(1,.35),(1,-.35))]
        body3 = [[a,b,z] for a,b in corners for z in (0,1.5)]
        r["time_s"] = n["time_s"]
        n.update(native_center_xy_m=[x,y], native_forward_xy=forward,
                 native_body_xy_m=corners, native_lane_id=-1 if y >= 0 else 1)
        t.update(position={"x":x,"y":y,"z":.5}, position_m=[x,y,.5],
                 heading_deg=math.degrees(math.atan2(forward[1],forward[0])))
        e["ego"].update(body_vertices_m=body3, position_m=[x,y,.5],
                        heading_deg=t["heading_deg"])
        e["world"]["road_projection"]["lane_id"] = n["native_lane_id"]
        b["body_vertices_m"] = body3
        assert m["native_frame"] == n["native_frame"]
    for name, values in (("rider_native_samples.jsonl",rider), ("native_samples.jsonl",native),
                         ("trace.jsonl",trace), ("capture/evidence.jsonl",evidence),
                         ("body_history.jsonl",history)):
        write_rows(source/name, values)
    (source/"authored-sign.json").write_bytes((HERE/"draft-native-sources/authored-sign.json").read_bytes())
    geometry_spec = importlib.util.spec_from_file_location("c104538_lvmc_geometry", HERE/"native/geometry.py")
    geometry = importlib.util.module_from_spec(geometry_spec)
    geometry_spec.loader.exec_module(geometry)
    (source/"road.xodr").write_text(geometry.open_drive())
    capture = json.loads((source/"capture/manifest.json").read_text())
    capture["sources"]["trace.jsonl"] = sha(source/"trace.jsonl")
    capture["sources"]["road.xodr"] = sha(source/"road.xodr")
    capture["synthetic_diagnostic"] = True
    (source/"capture/manifest.json").write_text(json.dumps(capture)+"\n")
    (source/"capture/recorder_info.txt").write_text("Create 107: vehicle.bh.crossbike\n")
    (source/"context.json").write_text(json.dumps({"signed_hill_crest":{
        "scope":"synthetic_native_shaped_diagnostic","sign_authorization_proven":False}})+"\n")
    source_manifest = {"source_kind":"synthetic_native_shaped_diagnostic", "case_suffix":kind,
        "candidate_id":candidate,"rider_samples_sha256":sha(source/"rider_native_samples.jsonl"),
        "sign_sha256":sha(source/"authored-sign.json"),"original_native_capture_executed":False}
    (source/"rider-source-manifest.json").write_text(json.dumps(source_manifest,indent=2)+"\n")
    config = json.loads((HERE/"draft-exact-candidates"/kind/candidate/"construction.json").read_text())
    config = json.loads(next(f["content"] for f in config["files"] if f["path"] == "config.json"))
    (source/"channels").mkdir()
    for channel in config["recording_description"]["channels"]:
        name = channel["name"]
        values = []
        for i, (r,n,m) in enumerate(zip(rider,native,mapping)):
            if name == "ru.bicycle": value = {"actor_id":"rider-1","blueprint":"vehicle.bh.crossbike","body_xy_m":n["native_body_xy_m"]}
            elif name == "ru.rider_posture": value = {"mounted_fixture":r["mounted"],"original_pixel_review":"pending"}
            elif name == "dev.regulatory_sign": value = {"code":"no_u_turn","authorization_proven":False}
            elif name == "dev.governs": value = {"road_id":1,"lane_id":-1,"synthetic_fixture":True}
            elif name == "dev.position": value = {"native_xy_m":[-8,4],"synthetic_fixture":True}
            elif name == "drv.u_turn": value = {"requested":kind=="mounted_turn","measured_from_saved_source":None}
            elif name == "kin.heading": value = n["native_forward_xy"]
            elif name == "rel.occupies": value = n["native_body_xy_m"]
            elif name == "native_body_pose_control": value = n
            elif name == "camera_frame_join": value = m
            else: raise ValueError("Unknown channel "+name)
            values.append({"time_s":n["time_s"],"value":value})
        write_rows(source/"channels"/(name+".jsonl"), values)
    shutil.copytree(source/"channels", source/"source_channels")
    return source


def probe(kind, candidate):
    scratch = Path(tempfile.mkdtemp(dir=ROOT/".runtime-work", prefix="c104538-lvmc-package-"))
    source = seed(scratch/"source", kind, candidate)
    case_id = HERE.name+("__controlled_1" if kind == "mounted_obey" else "__controlled_2")
    manifest = HERE/"draft-exact-execution-manifest.json"
    positive = scratch/"positive"
    receipt = run(manifest, case_id, source, positive,
        ROOT/"runtime/pipeline/library",
        ROOT/".runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck", candidate)
    negative = scratch/"negative"
    materialize_case(manifest, case_id, negative, source, candidate)
    (negative/"rider_native_samples.jsonl").unlink()
    failure = subprocess.run([sys.executable,str(negative/"finalize.py"),"--attempt",str(negative),
        "--output",str(negative/"analysis-report.json")],cwd=negative,env=execution_env(),
        text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
    (scratch/"negative-analysis.log").write_text(failure.stdout)
    if failure.returncode == 0 or "Missing required source: rider_native_samples.jsonl" not in failure.stdout:
        raise RuntimeError("Changed-source negative failed: "+failure.stdout)
    return {"case_id":case_id,"candidate_id":candidate,"positive":{k:v for k,v in receipt.items() if k!="fixture_manifest"},
            "negative":{"removed":"rider_native_samples.jsonl","rejected":True},
            "scratch":str(scratch),"scope":"synthetic v1 software diagnostic only"}


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--kind",choices=("mounted_obey","mounted_turn"),required=True)
    parser.add_argument("--candidate",choices=("primary","fallback1","fallback2","fallback3"),required=True)
    args=parser.parse_args()
    print(json.dumps(probe(args.kind,args.candidate),indent=2))
