"""Small original-shaped software fixtures for exact C135705 saved processing."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def dumps(value):return json.dumps(value,sort_keys=True,allow_nan=False)+"\n"
def sha_bytes(value):return hashlib.sha256(value.encode()).hexdigest()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rectangle_vertices(rect):
    x0,y0,x1,y1=rect
    return [[x0,y0],[x1,y0],[x1,y1],[x0,y1]]
def body(x,y,hx=2.5,hy=1):return rectangle_vertices([x-hx,y-hy,x+hx,y+hy])
def body3(points):return [[x,y,z] for x,y in points for z in (0,1.5)]


def diagnostic(scene):
    files={};graphs=[];positions=[65,30,0,-30,-65]
    stop=scene["standing_body_xy_m"]
    standing_body=rectangle_vertices(stop)
    stopped_y=(stop[1]+stop[3])/2
    frame_map=[];standing=[];passing=[];props=[];mechanical=[];trace=[];evidence=[];graph_index=[]
    for i,x in enumerate(positions):
        t=round(i*.05,4)
        frame_map.append({"video_frame":i,"carla_frame":i,"time_s":t})
        standing.append({"frame":i,"time_s":t,"actor_id":7,"body_vertices_xy_m":standing_body,
                         "position_xy_m":[0,stopped_y],"heading_deg":0,
                         "velocity_xy_mps":[0,0],"speed_mps":0})
        passing.append({"frame":i,"time_s":t,"actor_id":8,"body_vertices_xy_m":body(x,2.2),
                        "position_xy_m":[x,2.2],"heading_deg":180,
                        "velocity_xy_mps":[-16,0],"speed_mps":16})
        prop_actors=[]
        for index,rect in enumerate(scene["sight_occluders_xy_m"]):
            prop_actors.append({"actor_id":31+index,"body_vertices_xy_m":rectangle_vertices(rect),
                "position_xy_m":[(rect[0]+rect[2])/2,(rect[1]+rect[3])/2],
                "heading_deg":0,"velocity_xy_mps":[0,0],"speed_mps":0})
        props.append({"frame":i,"time_s":t,"actors":prop_actors})
        mechanical.append({"frame":i,"time_s":t,"standing_actor_id":7,
            "engine_disabled_by_worker":True,"physics_disabled_by_worker":True,
            "brake_requested":1.,"hand_brake_requested":True,
            "duration_since_first_sample_s":t,"unavoidable_stop_verified":False})
        trace.append({"frame":i,"time_s":t,"position":{"x":0,"y":stopped_y,"z":0},
            "position_m":[0,stopped_y,0],"heading_deg":0,"speed_mps":0,"speed_mph":0,
            "velocity_mps":[0,0,0],"control":{}})
        observations={"frame":i,"time_s":t,"participants":[],
                      "map_context":{"declared_public_way_road_ids":[]}}
        evidence.append({"actor_id":7,"ego":{"body_vertices_m":body3(standing_body),
            "heading_deg":0,"position_m":[0,stopped_y,0],"speed_mps":0,
            "speed_provenance":"synthetic_native_sample"},"original_frame":i,
            "original_observations":observations,"recording_time_s":t,
            "replay_frame":i,"replay_simulation_time_s":t,"world":{"weather":{}}})
        graph_path=f"capture/native/graphs/base/{i:08d}.adapter.json"
        graph_index.append({"adapter_graph":graph_path.removeprefix("capture/native/"),
                            "frame":i,"simulation_time":t})
        graphs.append({"path":graph_path,"attributes":{"frame":i,"time_s":t,
                       "observed_evidence":observations},"nodes":[],"edges":[]})
    for name,values in (("video_frames.jsonl",frame_map),("standing-body-history.jsonl",standing),
        ("passing-body-history.jsonl",passing),("occluder-body-history.jsonl",props),
        ("mechanical-attempt-history.jsonl",mechanical),("trace.jsonl",trace),
        ("capture/evidence.jsonl",evidence),("capture/native/frames.jsonl",graph_index)):
        files[name]="".join(dumps(row) for row in values)
    files["acquisition-provenance.json"]=dumps({"provenance_kind":"synthetic_fixture",
        "diagnostic_fixture":True,"scope":"software-only; no physical or legal acceptance"})
    files["capture/recorder_info.txt"]="Create 7: vehicle.tesla.model3 (standing diagnostic) at (0, 0, 0)\nCreate 8: vehicle.tesla.model3 (passing diagnostic) at (65, 2.2, 0)\n"
    files["capture/manifest.json"]=dumps({"acquisition":"original_live_run",
        "case_id":scene["case_id"],"complete_driving_lanes":False,"extraction_confirmed":True,
        "frames":len(positions),"sources":{"road.xodr":scene["map_source_sha256"],
            "trace.jsonl":sha_bytes(files["trace.jsonl"])},"status":"draft"})
    files["acquisition.json"]=dumps({name:{"kind":"diagnostic_fixture","sha256":sha_bytes(files[name])}
        for name in ("trace.jsonl","video_frames.jsonl","standing-body-history.jsonl",
            "passing-body-history.jsonl","occluder-body-history.jsonl","mechanical-attempt-history.jsonl")})
    videos=[{"path":name+".mkv","frames":len(positions),"width":width,"height":height,
             "fps":20,"color":"black"} for name,width,height in (
        ("overview",1920,1080),("approach",1280,720),
        ("reference_corner",1280,720),("driver_reference",1280,720))]
    return {"files":files,"graphs":graphs,"videos":videos}


def main():
    for suffix in ("passage_clear_view","passage_blocked","view_occluded_both"):
        folder=HERE/"cases"/suffix
        scene=json.loads((folder/"scene.json").read_text())
        generator=folder/"diagnostic.json"
        generator.write_text(json.dumps(diagnostic(scene),sort_keys=True,allow_nan=False)+"\n")
        note=folder/"diagnostic-source-note.json"
        note.write_text(dumps({"case_id":scene["case_id"],
            "scope":"synthetic diagnostic fixture; no physical or legal acceptance"}))
        recipe={"format":"worker-fixture-recipe",
            "sources":[{"path":"diagnostic-source-note.json",
                        "source":str(note.relative_to(ROOT)),"sha256":sha(note)}],
            "generator":{"source":str(generator.relative_to(ROOT)),"sha256":sha(generator)}}
        (folder/"fixture-recipe.json").write_text(json.dumps(recipe,indent=2)+"\n")
        print(suffix,sha(generator))


if __name__=="__main__":main()
