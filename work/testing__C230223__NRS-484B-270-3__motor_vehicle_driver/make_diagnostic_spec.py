"""Small synthetic converter inputs; these never establish original evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cycle_lane_2703 import ASSIGNMENT

ROOT=Path(__file__).resolve().parent


def compact(value):
    return json.dumps(value,separators=(",",":"),ensure_ascii=False)


def lines(rows):
    return "".join(compact(row)+"\n" for row in rows)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(compact(value)+"\n",encoding="utf-8")


def build(case):
    slug=case["case_slug"]
    case_id=case["case_id"]
    facility=[[-1,-1],[5,-1],[5,1],[-1,1]]
    conflict=[[0,-1],[2,-1],[2,4],[0,4]]
    site={"assignment_id":ASSIGNMENT,"source_kind":"synthetic_cpu_fixture",
          "diagnostic_fixture":True,"map_id":"C230223 synthetic converter geometry",
          "facility_id":"synthetic-cycle-facility","designation_authority":"synthetic-only",
          "facility_designated_for":"mixed_cycle","facility_extent_source":"synthetic-only",
          "facility_polygon":facility,"conflict_polygon":conflict,
          "routes":{slug:{"ego":[[-3,0],[1,0],[5,0]],
                          "participant":[[-2,0],[1,0],[6,0]]}}}
    participant={"source_kind":"synthetic_cpu_fixture","diagnostic_fixture":True,
                 "road_user_kind":case["road_user_kind"],
                 "actor_blueprint_id":"synthetic-test-participant",
                 "identity_review":"synthetic-only","body_measurement_method":"synthetic polygon"}
    qualified=case["road_user_kind"]=="qualified_pedestrian"
    context={"source_kind":"synthetic_cpu_fixture","diagnostic_fixture":True,
             "law_id":"NRS-484B-270-3","exception_kind":case["exception_request"],
             "exception_source_review":"synthetic-only",
             "nrs_484b_297_6":{name:qualified for name in
                ("sidewalk_obstruction","adjacent_strip_impassable",
                 "immediately_adjacent_highway","near_side_route","return_when_practicable")}}
    history=[];trace=[];frame_map=[];evidence=[];graphs=[];index=[]
    def body(x,y):
        return [[x-.1,y-.1],[x+.1,y-.1],[x+.1,y+.1],[x-.1,y+.1]]
    for i in range(900):
        if case["ego_precedence_request"]=="proceed_first":
            ego_x=-3+min(i,899)*.015
            other_x=-2+max(i-150,0)*.015
        else:
            ego_x=-3+max(i-150,0)*.015
            other_x=-2+min(i,899)*.015
        ego_y=3 if case["ego_lane_action_request"]=="outside" else 0
        ebody,obody=body(ego_x,ego_y),body(other_x,0)
        row={"frame":i,"time_s":i/20,"ego_actor_id":1,"participant_actor_id":2,
             "ego_body_polygon":ebody,"participant_body_polygon":obody,
             "ego_control":{},"participant_control":{}}
        history.append(row)
        trace.append({"frame":i,"time_s":i/20,"position_m":[ego_x,ego_y,0],
                      "position":{"x":ego_x,"y":ego_y,"z":0},
                      "speed_mps":.3,"speed_mph":.3/.44704,
                      "velocity_mps":[.3,0,0],"heading_deg":0,"control":{}})
        frame_map.append({"video_frame":i,"carla_frame":i,"native_frame":i,"time_s":i/20})
        observed={"frame":i,"time_s":i/20,"participants":[{"actor_id":2,
                  "blueprint":"walker.pedestrian.0001" if case["road_user_kind"].endswith("pedestrian") else "vehicle.bh.crossbike",
                  "blueprint_attributes":{"base_type":"bicycle"} if not case["road_user_kind"].endswith("pedestrian") else {"age":"adult"},
                  "heading_deg":0,"speed_mps":.3,"velocity_mps":[.3,0,0],
                  "body_vertices_m":[[x,y,z] for x,y in obody for z in (0,1.5)]}],
                  "map_context":{"cycle_facility_id":"synthetic-cycle-facility"}}
        evidence.append({"original_frame":i,"replay_frame":i,"actor_id":1,
            "recording_time_s":i/20,"replay_simulation_time_s":i/20,
            "world":{"weather":{}},"ego":{"position_m":[ego_x,ego_y,0],
                "heading_deg":0,"speed_mps":.3,"speed_provenance":"synthetic_native_sample",
                "body_vertices_m":[[x,y,z] for x,y in ebody for z in (0,1.5)]},
            "original_observations":observed})
        rel=f"graphs/base/{i:08d}.adapter.json"
        graphs.append({"path":"capture/native/"+rel,
                       "attributes":{"frame":i,"observed_evidence":observed},
                       "nodes":[],"edges":[]})
        index.append({"frame":i,"simulation_time":i/20,"adapter_graph":rel})
    road_sha=sha(ROOT/"diagnostic-map.xodr")
    files={"site-source.json":compact(site)+"\n",
           "participant-source.json":compact(participant)+"\n",
           "context-source.json":compact(context)+"\n",
           "history.json":compact(history)+"\n",
           "trace.jsonl":lines(trace),"video_frames.jsonl":lines(frame_map),
           "capture/evidence.jsonl":lines(evidence),
           "capture/native/frames.jsonl":lines(index),
           "capture/recorder_info.txt":"Create 1: vehicle.tesla.model3 (diagnostic) at (0, 0, 0)\nCreate 2: vehicle.bh.crossbike (diagnostic) at (0, 0, 0)\n",
           "capture/manifest.json":compact({"status":"draft","acquisition":"synthetic_cpu_fixture",
               "case_id":case_id,"frames":900,"extraction_confirmed":True,
               "complete_driving_lanes":False,"sources":{"road.xodr":road_sha,
                   "trace.jsonl":hashlib.sha256(lines(trace).encode()).hexdigest()}})+"\n",
           "acquisition-provenance.json":compact({"provenance_kind":"synthetic_fixture",
                                                    "diagnostic_fixture":True})+"\n"}
    videos=[{"path":name+".mkv","frames":900,
             "width":1920 if i==0 else 1280,
             "height":1080 if i==0 else 720,"fps":20,"color":"black"}
            for i,name in enumerate(("overview","approach","reference_corner","driver_reference"))]
    rel=f"cases/{slug}/diagnostic-spec.json"
    write(ROOT/rel,{"files":files,"graphs":graphs,"videos":videos})
    recipe=f"cases/{slug}/diagnostic-recipe.json"
    write(ROOT/recipe,{"format":"worker-fixture-recipe",
        "sources":[{"path":"road.xodr","source":str((ROOT/"diagnostic-map.xodr").relative_to(ROOT.parents[1])),
                    "sha256":road_sha}],
        "generator":{"source":str((ROOT/rel).relative_to(ROOT.parents[1])),
                     "sha256":sha(ROOT/rel)}})
    return rel,(ROOT/rel).stat().st_size


if __name__=="__main__":
    plan=json.loads((ROOT/"case-plan.json").read_text())
    for case in plan["cases"]:
        print(case["case_slug"],*build(case))
