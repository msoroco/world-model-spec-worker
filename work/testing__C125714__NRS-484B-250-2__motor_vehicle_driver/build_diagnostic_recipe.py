"""Build source-hashed synthetic inputs for the primary CPU compatibility check."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = "testing__C125714__NRS-484B-250-2__motor_vehicle_driver__source_verified_other_right_near_time"
FRAMES = 60


def dump(value):
    return json.dumps(value, indent=2, allow_nan=False) + "\n"


def lines(rows):
    return "".join(json.dumps(row, allow_nan=False) + "\n" for row in rows)


def box(x, y):
    return [[x-.3,y-.3], [x+.3,y-.3], [x+.3,y+.3], [x-.3,y+.3]]


def body3(x, y):
    return [[px,py,z] for px,py in box(x,y) for z in (0,1.5)]


def road(ident, name, x, y, heading, junction):
    return (f'<road name="{name}" length="30" id="{ident}" junction="{junction}"><link/>'
            f'<planView><geometry s="0" x="{x}" y="{y}" hdg="{heading}" length="30"><line/>'
            '</geometry></planView><elevationProfile><elevation s="0" a="0" b="0" c="0" d="0"/>'
            '</elevationProfile><lateralProfile/><lanes><laneOffset s="0" a="0" b="0" c="0" d="0"/>'
            '<laneSection s="0"><left><lane id="1" type="driving" level="false"><width sOffset="0" '
            'a="3.5" b="0" c="0" d="0"/></lane></left><center><lane id="0" type="none" '
            'level="false"/></center><right><lane id="-1" type="driving" level="false">'
            '<width sOffset="0" a="3.5" b="0" c="0" d="0"/></lane></right></laneSection>'
            '</lanes></road>')


def build():
    crossing, controller, mapping, trace, evidence = [], [], [], [], []
    native_frames, graphs = [], []
    for i in range(FRAMES):
        frame, t = 1000+i, i/20
        ex = -8 if i < 20 else min(8, -8 + .8*(i-20))
        oy = -8 if i < 10 else min(8, -8 + .8*(i-10))
        previous = -8 if i <= 10 else min(8, -8 + .8*(i-11))
        seen = previous >= -5.3
        crossing.append({"frame":frame,"time_s":t,"ego_vertices_m":box(ex,0),
                         "ego":{"position_xy_m":[ex,0],"body_vertices_xy_m":box(ex,0)},
                         "other":{"position_xy_m":[0,oy],"body_vertices_xy_m":box(0,oy)}})
        controller.append({"frame":frame,"time_s":t,"other_inside_before_tick":seen,
                           "other_entered_once":seen,"ego_control":{"hold":not seen}})
        mapping.append({"video_frame":i,"carla_frame":frame,"time_s":t})
        speed = 16 if 20 < i < 40 else 0
        trace.append({"frame":frame,"time_s":t,"position":{"x":ex,"y":0,"z":0},
                      "position_m":[ex,0,0],"heading_deg":0,"speed_mps":speed,
                      "speed_mph":speed/.44704,"velocity_mps":[speed,0,0],
                      "control":{"throttle":0,"steer":0,"brake":int(speed==0),
                                 "hand_brake":False,"reverse":False}})
        participants=[{"actor_id":aid,"blueprint":"vehicle.tesla.model3",
                       "position_m":[x,y,0],"heading_deg":heading,"speed_mps":v,
                       "velocity_mps":velocity,"body_vertices_m":body3(x,y),
                       "accel_longitudinal_mps2":0}
                      for aid,x,y,heading,v,velocity in
                      ((101,ex,0,0,speed,[speed,0,0]),
                       (102,0,oy,90,16 if 10<i<30 else 0,[0,16 if 10<i<30 else 0,0]))]
        observations={"frame":frame,"time_s":t,"participants":participants,"devices":[],
                      "relations":[],"participant_inventory":"synthetic two-actor diagnostic",
                      "map_context":{}}
        evidence.append({"original_frame":frame,"replay_frame":frame,"actor_id":101,
                         "recording_time_s":t,"replay_simulation_time_s":t,
                         "ego":{"position_m":[ex,0,0],"heading_deg":0,"speed_mps":speed,
                                "speed_provenance":"synthetic_native_sample",
                                "body_vertices_m":body3(ex,0)},
                         "world":{"weather":{"cloudiness":0,"precipitation":0,
                                              "precipitation_deposits":0,"fog_density":0,
                                              "sun_altitude_angle":45,"wetness":0},
                                  "road_projection":{"road_id":1,"section_id":0,"lane_id":-1,"s_m":ex+15}},
                         "original_observations":observations,
                         "timing":{},"visibility":{},"supporting_only":True})
        base=f"graphs/base/{frame:08d}.pkl"
        abstract=f"graphs/abstract/{frame:08d}.pkl"
        native_frames.append({"frame":frame,"simulation_time":t,"base":base,"abstract":abstract,
                              "nodes":0,"edges":0,"extraction_seconds":0,"capture_seconds":0})
        for path in (base,abstract):
            graphs.append({"path":"capture/native/"+path,
                           "attributes":{"frame":frame,"simulation_time_s":t,
                                         "units":{"position":"m"},"observed_evidence":observations},
                           "nodes":[],"edges":[]})
    geometry={"intersection_polygon_xy_m":[[-5,-5],[5,-5],[5,5],[-5,5]],
              "intersection_id":7,"ego_highway_id":1,"other_highway_id":2,
              "device_inventory_source":"synthetic device inventory; no physical claim",
              "device_review":{"official_device_controls_crossing":False,
                               "review_basis":"synthetic CPU fixture"},
              "approach_geometry_source":"synthetic orthogonal approach fixture",
              "ego_approach_heading_deg":0,"other_approach_heading_deg":90,
              "ego_approach_origin_xy_m":[-8,0],"other_approach_origin_xy_m":[0,-8]}
    xodr=('<OpenDRIVE><header revMajor="1" revMinor="4" name="synthetic C125714 orthogonal crossing" '
          'version="1" north="15" south="-15" east="15" west="-15" vendor="worker"/>'
          +road(1,"synthetic ego highway",-15,0,0,-1)
          +road(2,"synthetic other highway",0,-15,1.5707963267948966,7)
          +'<junction name="synthetic crossing" id="7"><connection id="0" incomingRoad="1" '
          'connectingRoad="2" contactPoint="start"><laneLink from="-1" to="-1"/></connection>'
          '</junction></OpenDRIVE>')
    files={"road_geometry.json":dump(geometry),"crossing_history.jsonl":lines(crossing),
           "controller_history.jsonl":lines(controller),"video_frames.jsonl":lines(mapping),
           "trace.jsonl":lines(trace),"capture/evidence.jsonl":lines(evidence),
           "capture/native/frames.jsonl":lines(native_frames),
           "capture/recorder_info.txt":"Version: 1\nMap: OpenDriveMap\n Create 101: vehicle.tesla.model3 (0) at (0, 0, 0)\n",
           "road.xodr":xodr}
    files["capture/manifest.json"]=dump({"status":"draft","acquisition":"synthetic_diagnostic",
        "case_id":CASE,"map":"Carla/Maps/OpenDriveMap","frames":FRAMES,
        "required_observations":["kin.position","kin.velocity","kin.speed","st.intersection","rel.bearing"],
        "extraction_confirmed":True,
        "sources":{"road.xodr":hashlib.sha256(xodr.encode()).hexdigest(),
                   "trace.jsonl":hashlib.sha256(files["trace.jsonl"].encode()).hexdigest()}})
    videos=[{"path":name+".mkv","frames":FRAMES,"width":width,"height":height,
             "fps":20,"color":"black"} for name,width,height in
            (("overview",1920,1080),("approach",1280,720),
             ("reference_corner",1280,720),("driver_reference",1280,720))]
    (HERE/"diagnostic.json").write_text(dump({"files":files,"graphs":graphs,"videos":videos}))
    origin=HERE/"fixture-origin.json"
    origin.write_text(dump({"format":"worker-synthetic-diagnostic-origin","case_id":CASE,
                            "physical_evidence":False,"purpose":"CPU compatibility only"}))
    def ref(path):
        return {"source":str(path.relative_to(ROOT)),
                "sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
    recipe={"format":"worker-fixture-recipe",
            "sources":[{"path":"fixture-origin.json",**ref(origin)}],
            "generator":ref(HERE/"diagnostic.json")}
    (HERE/"diagnostic-recipe.json").write_text(dump(recipe))
    proposals=HERE/"proposals"
    proposals.mkdir(exist_ok=True)
    construction=json.loads((HERE/"construction.json").read_text())
    (proposals/"cases.json").write_text(dump({"cell_id":"C125714","actor":"motor_vehicle_driver",
        "status":"draft","cases":[{"case_id":CASE,"target_law_id":"NRS-484B-250-2",
        "target_type":"delivery","rationale":"Source-verified right approach and first body entry, synthetic diagnostic only",
        "variable_assignments":{},"recording_description":construction["recording_description"],
        "unresolved_judgment_calls":["approximately same time","statutory right of way"]}],
        "sweep_specs":[],"sweeps_expanded":[]}))
    return recipe


if __name__ == "__main__":
    print(dump(build()))
