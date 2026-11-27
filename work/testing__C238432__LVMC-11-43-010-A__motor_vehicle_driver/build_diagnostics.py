"""Build source-shaped nine-frame direction fixtures and measurement contracts."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from direction import ASSIGNMENT, CASE_DIRECTIONS

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
VIEWS=("overview","approach","reference_corner","driver_reference")


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+"\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def map_packet():
    routes={}
    for name,sign in (("counterclockwise",1),("clockwise",-1)):
        ring=[{"x":7*math.cos(sign*math.radians(deg)),
               "y":7*math.sin(sign*math.radians(deg)),
               "lane_id":"ring","section":"ring"}
              for deg in (0,30,60,90,120,150)]
        routes[name]=([{"x":10,"y":0,"lane_id":"entry","section":"entry"}]
            +ring+[{"x":ring[-1]["x"]-1,"y":ring[-1]["y"]+sign,
                    "lane_id":"exit","section":"exit"}])
    return {"source_kind":"native_map_readback","jurisdiction":"Las Vegas, Nevada",
        "layout":"roundabout","map_name":"synthetic-fixture-map",
        "opendrive_sha256":"a"*64,"central_island":{"polygon":"synthetic"},
        "entry_yield_control":{"kind":"yield"},"outer_boundary":{"polygon":"synthetic"},
        "circulatory_roadway":{"lane_ids":["ring"]},"island_center":{"x":0,"y":0},
        "connected_routes":routes}


def build():
    base=json.loads((REPO/"runtime/fixtures/example.json").read_text())
    plan=json.loads((HERE/"case-plan.json").read_text())
    manifest_path=HERE/"execution-manifest.json"
    manifest=json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        case=entry["case_id"]
        sign=CASE_DIRECTIONS[case]
        name="counterclockwise" if sign==1 else "clockwise"
        folder=HERE/"cases"/name
        sources=folder/"diagnostic-sources"
        packet=map_packet()
        spec=json.loads(json.dumps(base))
        traces=[json.loads(line) for line in spec["files"]["trace.jsonl"].splitlines()]
        evidence_rows=[json.loads(line) for line in spec["files"]["capture/evidence.jsonl"].splitlines()]
        frames=[]
        for i,trace in enumerate(traces):
            ring=2<=i<=6
            angle=sign*math.radians(20)*max(0,min(4,i-2))
            x,y=7*math.cos(angle),7*math.sin(angle)
            section="ring" if ring else ("entry" if i<2 else "exit")
            lane="ring" if ring else section
            frames.append({"frame":trace["frame"],"time_s":trace["time_s"],
                "actor_id":205,"x":x,"y":y,"section":section,"lane_id":lane})
            dx=x-trace["position_m"][0]
            dy=y-trace["position_m"][1]
            evidence_rows[i]["ego"]["position_m"][0]=x
            evidence_rows[i]["ego"]["position_m"][1]=y
            for vertex in evidence_rows[i]["ego"]["body_vertices_m"]:
                vertex[0]+=dx
                vertex[1]+=dy
            for participant in evidence_rows[i]["original_observations"]["participants"]:
                if participant.get("actor_id")==205:
                    participant["position_m"][0]+=dx
                    participant["position_m"][1]+=dy
                    for vertex in participant["body_vertices_m"]:
                        vertex[0]+=dx
                        vertex[1]+=dy
            ego_node=next(node for node in spec["graphs"][i]["nodes"] if node["id"]=="ego")
            attributes=ego_node["attributes"]
            attributes["vertex"][0]+=dx
            attributes["vertex"][1]+=dy
            for vertex in attributes["threedbbox"]:
                vertex[0]+=dx
                vertex[1]+=dy
            original=attributes["original_observation"]
            original["position_m"][0]+=dx
            original["position_m"][1]+=dy
            for vertex in original["body_vertices_m"]:
                vertex[0]+=dx
                vertex[1]+=dy
            spec["graphs"][i]["attributes"]["observed_evidence"]=json.loads(
                json.dumps(evidence_rows[i]["original_observations"]))
            trace["position"]["x"]=x
            trace["position"]["y"]=y
            trace["position_m"][0]=x
            trace["position_m"][1]=y
        history={"source_kind":"sealed_native_original_history","case_id":case,
            "map_name":packet["map_name"],"opendrive_sha256":packet["opendrive_sha256"],
            "actor_role":"motor_vehicle_driver","actor_id":205,"frames":frames}
        spec["files"]["trace.jsonl"]="".join(json.dumps(row,allow_nan=False)+"\n" for row in traces)
        spec["files"]["capture/evidence.jsonl"]="".join(
            json.dumps(row,allow_nan=False)+"\n" for row in evidence_rows)
        capture_manifest=json.loads(spec["files"]["capture/manifest.json"])
        capture_manifest["sources"]["trace.jsonl"]=hashlib.sha256(
            spec["files"]["trace.jsonl"].encode()).hexdigest()
        spec["files"]["capture/manifest.json"]=json.dumps(capture_manifest)+"\n"
        scaffold=folder/"diagnostic.json"
        scaffold.parent.mkdir(parents=True,exist_ok=True)
        scaffold.write_text(json.dumps(spec,separators=(",",":"),allow_nan=False)+"\n")
        recipe_sources=[]
        refs={}
        for key,value in (("map",packet),("history",history)):
            path=sources/(key+".json")
            write(path,value)
            refs[key]={"path":path.name,"sha256":sha(path)}
            recipe_sources.append({"path":path.name,"source":str(path.relative_to(REPO)),
                                   "sha256":sha(path)})
        inventory={"case_id":case,"source_kind":"original_native",
                   "frame_count":9,"camera_views":list(VIEWS),"sources":refs}
        path=sources/"inventory.json"
        write(path,inventory)
        recipe_sources.append({"path":path.name,"source":str(path.relative_to(REPO)),
                               "sha256":sha(path)})
        recipe={"format":"worker-fixture-recipe",
            "generator":{"source":str(scaffold.relative_to(REPO)),"sha256":sha(scaffold)},
            "sources":recipe_sources}
        recipe_path=folder/"fixture-recipe.json"
        write(recipe_path,recipe)
        rows=[]
        for index,key,method,inputs in ((0,"roundabout_context","measure_roundabout",["map.json"]),
                                        (1,"motor_operator","measure_operator",["history.json"]),
                                        (2,"circulation_direction","measure_direction",["map.json","history.json"])):
            disposition=plan["requirement_dispositions"][index]
            rows.append({"disposition_index":index,"requirement":disposition["requirement"],
                         "source":disposition["source"],"output_key":key,
                         "method":method,"value_type":"object","kind":"measured",
                         "inputs":inputs})
        contract={"format":"worker-measurement-contract","case_id":case,
                  "requirements":rows,"negative":{"remove":["history.json"],
                  "error_contains":"Missing required source: history.json"}}
        contract_path=folder/"measurement-contract.json"
        write(contract_path,contract)
        entry["fixture_recipe"]=str(recipe_path.relative_to(REPO))
        entry["measurement_contract"]=str(contract_path.relative_to(HERE))
        entry["measurement_procedure"]={"entrypoint":"analysis.py",
                                          "method":"saved original source direction measurement"}
        entry["native_handoff"]={"python_env_var":"CARLA_PYTHON",
                                 "host_env_var":"CARLA_HOST","port_env_var":"CARLA_PORT"}
    write(manifest_path,manifest)


if __name__=="__main__":
    build()
