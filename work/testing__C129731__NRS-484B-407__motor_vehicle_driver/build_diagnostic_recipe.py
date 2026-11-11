"""Generate a textual, original-source shaped C129731 CPU diagnostic.

The generated videos and graph pickles belong only under ignored .runtime-work.
No physical visibility or legal outcome is inferred from this fixture.
"""
import hashlib
import json
import xml.etree.ElementTree as ET
import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(rows):
    return "".join(json.dumps(row, separators=(",", ":"), allow_nan=False)+"\n" for row in rows)


def body(x, y, height=0.):
    return [[x+dx, y+dy, height+z] for dx in (-1, 1) for dy in (-.8, .8) for z in (0, 1.5)]


def visibility(x, y, probe, height=0.):
    if probe == "short_of_500ft":
        bracket, clear = [150., 150.125], False
    elif probe == "at_500ft":
        bracket, clear = [152.4, 152.4], True
    elif probe == "beyond_500ft":
        bracket, clear = [160., 160.125], True
    else:
        raise ValueError("Unknown exact visibility probe")
    return {"visibility_criterion": "any_of_nine_body_samples",
            "distance_convention": "incoming driving-lane waypoint arc length to actor projected station",
            "eye_height_m": 1.4, "scan_step_m": 10., "horizon_tolerance_m": .25,
            "probe_distance_m": 152.4,
            "ego_body_samples_m": [[x+dx,y+dy,height+1.] for dx,dy in
                                   ((0,0),(-1,-.8),(-1,.8),(1,-.8),(1,.8),
                                    (-1,0),(1,0),(0,-.8),(0,.8))],
            "ego_projection":{"road_id":10,"section_id":0,"lane_id":-1},
            "required_lane_ids": [-1, 1],
            "approaches": [
                {"lane_id": -1, "any_sample_clear_at_probe": clear,
                 "any_body_sight_horizon": {"bound": "first_sampled_occlusion", "bracket_m": bracket}},
                {"lane_id": 1, "any_sample_clear_at_probe": True,
                 "any_body_sight_horizon": {"bound": "at_least", "distance_m": 160.}}]}


def build(variant="short_of_500ft", feature="curve"):
    if feature == "crest":
        suffix = "-crest-" + {"short_of_500ft": "short", "at_500ft": "at", "beyond_500ft": "beyond"}[variant]
    elif variant == "short_of_500ft":
        suffix = ""
    elif variant == "at_500ft":
        suffix = "-at"
    elif variant == "beyond_500ft":
        suffix = "-beyond"
    else:
        raise ValueError("Fixture source variant is not yet constructed")
    config = json.loads((HERE/("config"+suffix+".json")).read_text())
    case = config["selected_case_id"]
    site_path = HERE/("diagnostic-site"+suffix+".json")
    site = json.loads(site_path.read_text())
    site_sha = sha(site_path)
    if site["probe"] != variant or site["feature"] != feature or not case.endswith("__"+feature+"__"+variant):
        raise ValueError("Fixture case/site probe differs")
    target = HERE/("diagnostic-sources"+suffix)
    target.mkdir(exist_ok=True)
    motion, turns, maps, traces, evidence, frames = [], [], [], [], [], []
    graphs = []
    for i in range(1100):
        frame, time = i+1000, i/20
        fraction = min(1., i/400)
        x, y, yaw = -10+10*fraction, 2*min(1., max(0., (i-100)/300)), 180*fraction
        height = 8*(1-abs(x)/160) if feature == "crest" else 0.
        vertices = body(x, y, height)
        ego = {"location_xyz_m": [x,y,height], "yaw_deg": yaw,
               "velocity_xyz_mps": [0 if i>=400 else .5,0,0], "road_lane": [10,-1]}
        approaches = {name: {"location_xyz_m": [(-160+i*.05 if name=="approach_a" else 160-i*.05),0,
                                              (8*(1-abs(-160+i*.05 if name=="approach_a" else 160-i*.05)/160)
                                               if feature=="crest" else 0)],
                              "yaw_deg": 0 if name=="approach_a" else 180,
                              "velocity_xyz_mps": [1 if name=="approach_a" else -1,0,0],
                              "road_lane": [10,lane]}
                      for name,lane in (("approach_a",-1),("approach_b",1))}
        maps.append({"video_frame":i,"carla_frame":frame,"native_frame":frame,"time_s":time})
        motion.append({"video_frame":i,"native_frame":frame,"site_source_sha256":site_sha,
                       "ego":ego,"approaches":approaches})
        turns.append({"frame":frame,"time_s":time,"body_vertices_m":vertices,"heading_deg":yaw})
        traces.append({"frame":frame,"time_s":time,"position_m":[x,y,height],
                       "position":{"x":x,"y":y,"z":height},
                       "heading_deg":yaw,"speed_mps":ego["velocity_xyz_mps"][0],
                       "speed_mph":ego["velocity_xyz_mps"][0]/.44704,
                       "velocity_mps":ego["velocity_xyz_mps"],
                       "control":{"throttle":0,"steer":0,"brake":0 if i<400 else 1,
                                  "hand_brake":False,"reverse":False}})
        participant = {"actor_id":101,"blueprint":"vehicle.tesla.model3",
                       "position_m":[x,y,height],"heading_deg":yaw,
                       "velocity_mps":ego["velocity_xyz_mps"],
                       "speed_mps":ego["velocity_xyz_mps"][0],
                       "accel_longitudinal_mps2":0,
                       "body_vertices_m":vertices}
        original = {"frame":frame,"time_s":time,"participants":[participant],
                    "map_context":{"declared_public_way_road_ids":[10]}}
        evidence.append({"original_frame":frame,"replay_frame":frame,"actor_id":101,
                         "recording_time_s":time,"replay_simulation_time_s":time,
                         "ego":{"position_m":[x,y,height],"heading_deg":yaw,
                                "speed_mps":ego["velocity_xyz_mps"][0],
                                "speed_provenance":"synthetic_native_sample",
                                "body_vertices_m":vertices},
                         "world":{},
                         "original_observations":original,"visibility":visibility(x,y,variant,height)})
        base, abstract = (f"graphs/{kind}/{frame:08d}.pkl" for kind in ("base","abstract"))
        frames.append({"frame":frame,"simulation_time":time,"base":base,"abstract":abstract,
                       "nodes":0,"edges":0,"extraction_seconds":0,"capture_seconds":0})
        for path, attrs in ((base,{"observed_evidence":original}),(abstract,{})):
            graphs.append({"path":"capture/native/"+path,
                           "attributes":{"frame":frame,"simulation_time_s":time,
                                         "units":{"position":"m"},**attrs},
                           "nodes":[],"edges":[]})
    road = ET.fromstring(json.loads((ROOT/"runtime/fixtures/example.json").read_text())["files"]["road.xodr"])
    for source_road in road.findall("road"):
        source_road.set("id", "10")
        for geometry in source_road.findall("./planView/geometry"):
            geometry.set("x", "-200")
        for lane_group in source_road.findall("./lanes/laneSection/*"):
            for lane in list(lane_group.findall("lane")):
                if lane.get("id") not in ("-1","0","1"):
                    lane_group.remove(lane)
        if feature == "crest":
            elevation = source_road.find("elevationProfile")
            for old in list(elevation):
                elevation.remove(old)
            for distance, a, b in ((0,0,0),(40,0,.05),(200,8,-.05),(360,0,0)):
                ET.SubElement(elevation,"elevation",{"s":str(distance),"a":str(a),
                         "b":str(b),"c":"0","d":"0"})
    sources = {"motion_history.jsonl":lines(motion),"turn_history.jsonl":lines(turns),
               "video_frames.jsonl":lines(maps),"trace.jsonl":lines(traces),
               "capture/evidence.jsonl":lines(evidence),
               "capture/native/frames.jsonl":lines(frames),
               "curve_context.json":json.dumps({"site_source_sha256":site_sha,"feature":site["feature"],
                                                "turn_site_xyz_m":site["turn_site_xyz_m"],
                                                "incoming_lanes":site["incoming_lanes"],
                                                "visibility_proxy_only":True}),
               "capture/recorder_info.txt":"Create 101: vehicle.tesla.model3 (0) at (0, 0, 0)\nsynthetic diagnostic only\n",
               "road.xodr":ET.tostring(road, encoding="unicode")}
    sources["capture/manifest.json"] = json.dumps({"status":"draft","acquisition":"synthetic_diagnostic",
        "case_id":case,"map":"Carla/Maps/OpenDriveMap","frames":1100,
        "required_observations":["st.sight_distance"],"extraction_confirmed":True,
        "sources":{"road.xodr":hashlib.sha256(sources["road.xodr"].encode()).hexdigest(),
                   "trace.jsonl":hashlib.sha256(sources["trace.jsonl"].encode()).hexdigest()}})
    items=[]
    for name,content in sorted(sources.items()):
        path=target/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content)
        if path.stat().st_size>2*1024*1024:raise ValueError("Returned source exceeds 2 MiB: "+name)
        items.append({"path":name,"source":str(path.relative_to(ROOT)),"sha256":sha(path)})
    videos=[{"path":name+".mkv","frames":1100,"width":w,"height":h,"fps":20,"color":"black"}
            for name,w,h in (("overview",1920,1080),("approach",1280,720),
                             ("reference_corner",1280,720),("driver_reference",1280,720))]
    spec={"files":{},"graphs":graphs,"videos":videos}
    path=HERE/("diagnostic"+suffix+".json");path.write_text(json.dumps(spec,separators=(",", ":"))+"\n")
    if path.stat().st_size>2*1024*1024:raise ValueError("Returned fixture spec exceeds 2 MiB")
    relative=str(path.relative_to(ROOT))
    recipe={"format":"worker-fixture-recipe",
            "sources":items+[{"path":"diagnostic-input.json","source":relative,"sha256":sha(path)}],
            "generator":{"source":relative,"sha256":sha(path)}}
    (HERE/("diagnostic-recipe"+suffix+".json")).write_text(json.dumps(recipe,indent=2)+"\n")
    return {"spec_bytes":path.stat().st_size,
            "source_bytes":{name:len(content.encode()) for name,content in sources.items()}}


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--feature",choices=("curve","crest"),default="curve")
    parser.add_argument("--variant",choices=("short_of_500ft","at_500ft","beyond_500ft"),default="short_of_500ft")
    args=parser.parse_args()
    print(json.dumps(build(args.variant,args.feature),indent=2))
