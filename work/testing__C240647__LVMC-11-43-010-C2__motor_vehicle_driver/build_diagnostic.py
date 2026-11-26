"""Build nine-frame source-shaped fixtures; never physical/legal evidence."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
AID=HERE.name
VIEWS=("overview","approach","reference_corner","driver_reference")

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,sort_keys=True,indent=2)+"\n")

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def route(case):
    lane=case["roundabout_lane_request"]
    roles={"right":["right"]*4,"left":["left"]*4,
           "left_then_right":["left","left","right","right"],
           "right_then_left":["right","right","left","left"],
           "single_right":["right"]*4}[lane]
    points=[{"x":-8,"y":-4,"section":"approach","lane_id":"entry",
             "source_waypoint_id":"entry-0"}]
    coords=[(0,-4),(3,-3),(4,0),(3,3)]
    for i,(role,(x,y)) in enumerate(zip(roles,coords)):
        if role=="left":
            x,y=x*.5,y*.5
        points.append({"x":x,"y":y,"section":"circulating","lane_role":role,
                       "lane_id":"lane-"+role,"source_waypoint_id":f"{role}-{i}"})
    requested=case["actual_exit_request"]
    if requested!="no_exit":
        x,y=(6,2) if requested=="right_exit" else (0,6)
        points.append({"x":x,"y":y,"section":"exit","lane_id":"exit-"+requested,
                       "exit_connector_id":"connector-"+requested,
                       "source_waypoint_id":"exit-"+requested})
    return points

def map_packet(case):
    single=case["roundabout_lane_request"]=="single_right"
    lanes={"right":{"lane_id":"lane-right","source_waypoint_ids":["right-0","right-1","right-2","right-3"]}}
    if not single:
        lanes["left"]={"lane_id":"lane-left","source_waypoint_ids":["left-0","left-1","left-2","left-3"]}
    return {"source_kind":"native_map_readback","layout":"single_lane_roundabout" if single else "multilane_roundabout",
            "jurisdiction":"Las Vegas, Nevada","map_id":"diagnostic-single" if single else "diagnostic-multilane",
            "map_sha256":"a"*64,"lanes":lanes,
            "exit_connectors":{name:{"connector_id":"connector-"+name,"source_waypoint_ids":["exit-"+name]}
                               for name in ("right_exit","through_exit")},
            "routes":{case["case_id"]:route(case)}}

def build():
    scaffold=HERE/"diagnostic-scaffold.json"
    scaffold.write_bytes((REPO/"runtime/fixtures/example.json").read_bytes())
    plan=json.loads((HERE/"case-plan.json").read_text())
    manifest_path=HERE/"execution-manifest.json"
    manifest=json.loads(manifest_path.read_text())
    by_id={row["case_id"]:row for row in plan["cases"]}
    for entry in manifest["cases"]:
        case_id=entry["case_id"]
        case=by_id[case_id]
        name=case_id.removeprefix(AID+"__")
        folder=HERE/"cases"/name
        sources=folder/"diagnostic-sources"
        source_map=map_packet(case)
        lane_sequence=[point["lane_id"] for point in source_map["routes"][case_id]
                       if point["section"]=="circulating"]
        exit_id=None if case["actual_exit_request"]=="no_exit" else "connector-"+case["actual_exit_request"]
        frames=[]
        for i in range(9):
            section="approach" if i<2 else "circulating" if i<7 or exit_id is None else "exit"
            frames.append({"frame":i,"time_s":round(i*.05,4),"section":section,
              "lane_id":lane_sequence[min(max(i-2,0),len(lane_sequence)-1)] if section=="circulating" else "entry" if section=="approach" else "exit-"+case["actual_exit_request"],
              "exit_connector_id":exit_id if section=="exit" else None,
              "actor_id":"17","speed_mps":3.0})
        history={"source_kind":"sealed_native_original_history","case_id":case_id,
           "map_id":source_map["map_id"],"map_sha256":source_map["map_sha256"],
           "actor_role":"motor_vehicle_driver","actor_id":"17",
           "operator_intended_exit_role":case["operator_intent_request"],
           "independent_operator_intent_source_sha256":"e"*64,
           "vehicle_blueprint":"vehicle.fixture","entry_id":"south-entry",
           "controller_sha256":"b"*64,"weather_sha256":"c"*64,"camera_plan_sha256":"d"*64,
           "frames":frames}
        recipe_sources=[]
        refs={}
        for key,packet in (("map",source_map),("history",history)):
            path=sources/(key+".json")
            write(path,packet)
            refs[key]={"path":path.name,"sha256":sha(path)}
            recipe_sources.append({"path":path.name,"source":str(path.relative_to(REPO)),"sha256":sha(path)})
        inventory={"case_id":case_id,"source_kind":"original_native","frame_count":9,
                   "camera_views":list(VIEWS),"sources":refs}
        inventory_path=sources/"inventory.json"
        write(inventory_path,inventory)
        recipe_sources.append({"path":"inventory.json","source":str(inventory_path.relative_to(REPO)),
                               "sha256":sha(inventory_path)})
        recipe_path=folder/"fixture-recipe.json"
        write(recipe_path,{"format":"worker-fixture-recipe",
            "generator":{"source":str(scaffold.relative_to(REPO)),"sha256":sha(scaffold)},
            "sources":recipe_sources})
        requirements=[]
        for index,(name,method) in enumerate((("intent","measure_intent"),("lane_use","measure_lane_use"),
                                              ("actual_exit","measure_actual_exit"))):
            disposition=plan["requirement_dispositions"][index]
            requirements.append({"disposition_index":index,"requirement":disposition["requirement"],
              "source":disposition["source"],"output_key":name,"method":method,
              "value_type":"object","kind":"measured","inputs":["map.json","history.json"]})
        contract_path=folder/"measurement-contract.json"
        write(contract_path,{"format":"worker-measurement-contract","case_id":case_id,
          "requirements":requirements,"negative":{"remove":["history.json"],
          "error_contains":"Missing required source: history.json"}})
        entry["fixture_recipe"]=str(recipe_path.relative_to(REPO))
        entry["measurement_contract"]=str(contract_path.relative_to(HERE))
    write(manifest_path,manifest)
    return len(manifest["cases"])

if __name__ == "__main__":
    print(build())
