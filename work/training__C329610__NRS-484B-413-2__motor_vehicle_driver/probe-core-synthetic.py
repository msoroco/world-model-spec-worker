"""800-frame synthetic saved capture through pinned Core, Lean and render."""
import hashlib
import json
from pathlib import Path
import pickle
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE / "native"))
sys.path.insert(0, str(REPO / "runtime/pipeline/scenario_pipeline"))
from geometry import open_drive
from finalize import finalize
from traffic_spec_adapter.adapter import load_graph
from worker_exchange.runtime_cli import process, render
from worker_exchange.media import audit


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def write_rows(path, items):
    path.write_text("".join(json.dumps(item, allow_nan=False) + "\n" for item in items))


def enrich(attempt):
    trace = rows(attempt / "trace.jsonl")
    evidence = rows(attempt / "capture/evidence.jsonl")
    samples = rows(attempt / "native_samples.jsonl")
    if len(trace) != len(evidence) or len(trace) != len(samples) or len(trace) != 800:
        raise ValueError("Expected 800 joined synthetic samples")
    graph = load_graph(REPO / "runtime/pipeline/fixtures/retained-speed/capture/native/graphs/base/00021714.pkl")
    graph_dir = attempt / "capture/native/graphs/base"
    graph_dir.mkdir(parents=True)
    frames = []
    for index, (t,e,n) in enumerate(zip(trace,evidence,samples)):
        frame = t["frame"]
        time = t["time_s"]
        x,y = n["native_center_xy_m"]
        graph.graph["frame"] = frame
        (graph_dir / f"{frame:08d}.pkl").write_bytes(pickle.dumps(graph, protocol=4))
        t.update(position_m=[x,y,.5],speed_mph=t["speed_mps"]/.44704,
                 control={"throttle":0,"brake":0,"hand_brake":False})
        e.update(replay_frame=frame,replay_simulation_time_s=time,actor_id=107)
        e["ego"].update(position_m=[x,y,.5],heading_deg=t["heading_deg"],
                        speed_mps=t["speed_mps"],
                        speed_provenance="original_trace_actor_get_velocity",
                        synthetic_diagnostic=True)
        road = 1 if index < 420 else 13 if index < 475 else 4
        e["world"] = {"weather":{"cloudiness":0,"precipitation":0,"wetness":0,"fog_density":0},
                      "road_projection":{"road_id":road,"section_id":0,"lane_id":-1,"s_m":x+120}}
        frames.append({"frame":frame,"simulation_time":time,"time_s":time,
                       "base":f"graphs/base/{frame:08d}.pkl",
                       "abstract":f"graphs/abstract/{frame:08d}.pkl",
                       "synthetic_diagnostic":True})
    write_rows(attempt / "trace.jsonl", trace)
    write_rows(attempt / "capture/evidence.jsonl", evidence)
    write_rows(attempt / "capture/native/frames.jsonl", frames)
    (attempt / "road.xodr").write_text(open_drive())
    (attempt / "capture/recorder_info.txt").write_text("Create 107: vehicle.lincoln.mkz_2020\n")
    manifest = json.loads((attempt / "capture/manifest.json").read_text())
    manifest.update(sources={"road.xodr":hashlib.sha256((attempt / "road.xodr").read_bytes()).hexdigest(),
                             "trace.jsonl":hashlib.sha256((attempt / "trace.jsonl").read_bytes()).hexdigest()},
                    synthetic_diagnostic=True)
    (attempt / "capture/manifest.json").write_text(json.dumps(manifest) + "\n")


def main():
    scratch = Path(tempfile.mkdtemp(dir=REPO / ".runtime-work", prefix="c329610-413-core-"))
    attempt = scratch / "attempt"
    shutil.copytree(REPO / ".runtime-work/c329610-413-saved-fixtures/at_100_ft-source", attempt)
    enrich(attempt)
    print("scratch", scratch, flush=True)
    report = finalize(attempt, attempt / "analysis-report.json")
    core = process(attempt, attempt / "converted", REPO / "runtime/pipeline/library",
                   REPO / ".runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck")
    config = json.loads((attempt / "config.json").read_text())
    video = render(attempt, attempt / "converted", config["case"])
    decoded = audit(video["video"], 800, mapping_sha256=video["frame_map_sha256"],
                    receipt=attempt / "final-decode.json")
    print(json.dumps({"analysis_format":report["format"],"core":core,
                      "render_frames":video["frames"],"final_decode_passed":decoded["passed"],
                      "synthetic":True,"accepted":False}))


if __name__ == "__main__":
    main()
